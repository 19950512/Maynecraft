#!/bin/bash

# Monitora o log do servidor Minecraft e envia eventos formatados para o Discord
# via webhook (mensagens com embeds, traduzidas para português e amigáveis às crianças).

LOG_FILE="${MINECRAFT_DIR:-/minecraft/server}/logs/latest.log"
WEBHOOK_URL="${DISCORD_WEBHOOK_URL}"
SESSION_NAME="${TMUX_SESSION:-minecraft}"
KNOWN_LOGINS="/tmp/known_logins.txt"

if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ DISCORD_WEBHOOK_URL não configurado. Verifique o arquivo .env"
    exit 1
fi

echo "✅ Monitorando logs em: $LOG_FILE"
echo "📡 Webhook URL configurado"

mkdir -p /tmp
> "$KNOWN_LOGINS"

# Cores Discord (decimais)
COR_VERDE=5763719       # entrada
COR_VERMELHO=15548997   # saída
COR_AMARELO=16776960    # avanço
COR_AZUL=3447003        # chat
COR_ROXO=10181046       # morte
COR_LARANJA=15105570    # servidor iniciado
COR_CINZA=9807270       # info

# Envia um embed para o Discord
send_embed() {
    local title="$1"
    local description="$2"
    local color="$3"
    title=$(echo "$title" | sed 's/"/\\"/g')
    description=$(echo "$description" | sed 's/"/\\"/g' | tr '\n' ' ')
    local json
    json=$(cat <<EOF
{
  "embeds": [{
    "title": "$title",
    "description": "$description",
    "color": $color,
    "footer": { "text": "Servidor do Heitor Maydana" },
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
  }]
}
EOF
)
    curl -s -H "Content-Type: application/json" -X POST -d "$json" "$WEBHOOK_URL" > /dev/null
}

# Envia uma mensagem de boas-vindas no chat do jogo
saudar_no_jogo() {
    local player="$1"
    local saudacoes=(
        "Bem-vindo(a) ao servidor do Heitor, $player! 🎮"
        "Oiêêê $player! Boa diversão! ✨"
        "Salve $player! Pega a picareta e vem! ⛏️"
        "$player chegou! A festa começou! 🎉"
        "Que bom te ver, $player! 💚"
    )
    local idx=$((RANDOM % ${#saudacoes[@]}))
    local msg="${saudacoes[$idx]}"
    tmux send-keys -t "$SESSION_NAME" \
        "tellraw @a [{\"text\":\"$msg\",\"color\":\"gold\",\"bold\":true}]" Enter 2>/dev/null || true
}

tail -n0 -F "$LOG_FILE" | while read LINE; do
    if echo "$LINE" | grep -q "logged in with entity id"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?=\[)")
        IP=$(echo "$LINE" | grep -oP "(/[\d\.]+)" | tr -d '/')
        UNIQUE="$PLAYER-$IP"
        if ! grep -q "$UNIQUE" "$KNOWN_LOGINS"; then
            echo "$UNIQUE" >> "$KNOWN_LOGINS"
            send_embed "🔓 Nova conexão" "**$PLAYER** se conectou pelo IP \`$IP\`" "$COR_CINZA"
        fi
    elif echo "$LINE" | grep -q "joined the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= joined the game)")
        send_embed "🟢 Jogador entrou" "**$PLAYER** está online! 🎮" "$COR_VERDE"
        ( sleep 2; saudar_no_jogo "$PLAYER" ) &
    elif echo "$LINE" | grep -q "left the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= left the game)")
        send_embed "🔴 Jogador saiu" "**$PLAYER** desconectou. Até logo! 👋" "$COR_VERMELHO"
    elif echo "$LINE" | grep -q "has made the advancement"; then
        ADV=$(echo "$LINE" | grep -oP "\]: \K.*")
        PLAYER=$(echo "$ADV" | awk '{print $1}')
        AVANCO=$(echo "$ADV" | grep -oP '\[\K[^\]]+(?=\])')
        send_embed "🎖️ Conquista desbloqueada!" "**$PLAYER** conseguiu **$AVANCO**! Parabéns! 🎉" "$COR_AMARELO"
    elif echo "$LINE" | grep -q "has completed the challenge"; then
        ADV=$(echo "$LINE" | grep -oP "\]: \K.*")
        PLAYER=$(echo "$ADV" | awk '{print $1}')
        AVANCO=$(echo "$ADV" | grep -oP '\[\K[^\]]+(?=\])')
        send_embed "🏆 Desafio concluído!" "**$PLAYER** completou **$AVANCO**! Que demais! 💪" "$COR_AMARELO"
    elif echo "$LINE" | grep -E -q "was slain|was shot|was killed|fell from|tried to|drowned|burned|blew up|suffocated|starved|withered|froze|hit the ground|was pricked|was squished|was impaled"; then
        DEATH=$(echo "$LINE" | grep -oP "\]: \K.*")
        PLAYER=$(echo "$DEATH" | grep -oP "^[^ ]+")
        CAUSE=$(echo "$DEATH" | sed "s/^$PLAYER //")
        case "$CAUSE" in
            *"fell from a high place"*) CAUSE_PT="caiu de um lugar alto 🪂" ;;
            *"hit the ground too hard"*) CAUSE_PT="bateu no chão com força demais 💥" ;;
            *"was slain by"*) MOB=$(echo "$CAUSE" | sed 's/was slain by //'); CAUSE_PT="foi morto(a) por **$MOB** ⚔️" ;;
            *"was shot by"*) MOB=$(echo "$CAUSE" | sed 's/was shot by //'); CAUSE_PT="foi flechado(a) por **$MOB** 🏹" ;;
            *"was killed by"*) MOB=$(echo "$CAUSE" | sed 's/was killed by //'); CAUSE_PT="foi derrotado(a) por **$MOB** ☠️" ;;
            *"was pricked to death"*) CAUSE_PT="morreu espetado(a) num cacto 🌵" ;;
            *"was squished"*) CAUSE_PT="foi esmagado(a) 🪨" ;;
            *"was impaled"*) CAUSE_PT="foi atingido(a) por um tridente 🔱" ;;
            *"drowned"*) CAUSE_PT="morreu afogado(a) 🌊" ;;
            *"tried to swim in lava"*) CAUSE_PT="tentou nadar na lava 🌋" ;;
            *"burned to death"*) CAUSE_PT="queimou até a morte 🔥" ;;
            *"blew up"*) CAUSE_PT="explodiu 💥" ;;
            *"was blown up"*) CAUSE_PT="foi explodido(a) 💣" ;;
            *"suffocated"*) CAUSE_PT="sufocou numa parede 🧱" ;;
            *"starved to death"*) CAUSE_PT="morreu de fome 🍖" ;;
            *"withered away"*) CAUSE_PT="murchou e morreu 💀" ;;
            *"froze to death"*) CAUSE_PT="congelou ❄️" ;;
            *) CAUSE_PT="$CAUSE" ;;
        esac
        send_embed "💀 $PLAYER" "$CAUSE_PT" "$COR_ROXO"
    elif echo "$LINE" | grep -q "\[Not Secure\]"; then
        PLAYER=$(echo "$LINE" | grep -oP "\[Not Secure\] <\K.*(?=>)")
        MESSAGE=$(echo "$LINE" | grep -oP "\[Not Secure\] <.*> \K.*")
        # Ignora mensagens vindas do próprio bot ([Discord]) para evitar loop
        if echo "$MESSAGE" | grep -q "^\[Discord\]"; then
            continue
        fi
        send_embed "💬 $PLAYER" "$MESSAGE" "$COR_AZUL"
    elif echo "$LINE" | grep -q "Done ("; then
        send_embed "🚀 Servidor online!" "O Maynecraft do Heitor está pronto pra brincar! 🎮✨" "$COR_LARANJA"
    fi
done
