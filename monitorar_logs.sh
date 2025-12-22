#!/bin/bash

# As variáveis de ambiente vêm do docker-compose.yml e docker-entrypoint.sh
LOG_FILE="${MINECRAFT_DIR:-/minecraft/server}/logs/latest.log"
WEBHOOK_URL="${DISCORD_WEBHOOK_URL}"
KNOWN_LOGINS="/tmp/known_logins.txt"

# Verifica se WEBHOOK_URL está configurado
if [ -z "$WEBHOOK_URL" ]; then
    echo "❌ DISCORD_WEBHOOK_URL não configurado. Verifique o arquivo .env"
    exit 1
fi

echo "✅ Monitorando logs em: $LOG_FILE"
echo "📡 Webhook URL configurado"

> "$KNOWN_LOGINS"

WEBHOOK_URL="$DISCORD_WEBHOOK_URL"
KNOWN_LOGINS="/tmp/known_logins.txt"
> "$KNOWN_LOGINS"

tail -n0 -F "$LOG_FILE" | while read LINE; do
    if echo "$LINE" | grep -q "logged in with entity id"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?=\[)")
        IP=$(echo "$LINE" | grep -oP "(/[\d\.]+)" | tr -d '/')
        UNIQUE="$PLAYER-$IP"
        if ! grep -q "$UNIQUE" "$KNOWN_LOGINS"; then
            echo "$UNIQUE" >> "$KNOWN_LOGINS"
            curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🔓 **$PLAYER entrou no servidor com IP $IP**\"}" "$WEBHOOK_URL"
        fi
    elif echo "$LINE" | grep -q "joined the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= joined the game)")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🟢 **$PLAYER entrou no servidor.**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "left the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= left the game)")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🔴 **$PLAYER saiu do servidor.**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "has made the advancement"; then
        ADV=$(echo "$LINE" | grep -oP "\]: \K.*")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🎖️ **$ADV**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -E -q "was slain|was shot|was killed|fell from|tried to|drowned|burned|blew up|suffocated|starved|withered|froze"; then
        DEATH=$(echo "$LINE" | grep -oP "\]: \K.*")
        # Extrai jogador e causa
        PLAYER=$(echo "$DEATH" | grep -oP "^[^ ]+")
        CAUSE=$(echo "$DEATH" | sed "s/^$PLAYER //")
        
        # Traduz causas comuns
        case "$CAUSE" in
            *"fell from a high place"*) CAUSE_PT="caiu de um lugar alto 🪂" ;;
            *"was slain by"*) MOB=$(echo "$CAUSE" | sed 's/was slain by //'); CAUSE_PT="foi morto por $MOB ⚔️" ;;
            *"was shot by"*) MOB=$(echo "$CAUSE" | sed 's/was shot by //'); CAUSE_PT="foi alvejado por $MOB 🏹" ;;
            *"drowned"*) CAUSE_PT="morreu afogado 🌊" ;;
            *"tried to swim in lava"*) CAUSE_PT="tentou nadar na lava 🌋" ;;
            *"burned to death"*) CAUSE_PT="queimou até a morte 🔥" ;;
            *"blew up"*) CAUSE_PT="explodiu 💥" ;;
            *"suffocated"*) CAUSE_PT="sufocou em uma parede 🧱" ;;
            *"starved to death"*) CAUSE_PT="morreu de fome 🍖" ;;
            *) CAUSE_PT="$CAUSE" ;;
        esac
        
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"💀 **$PLAYER** $CAUSE_PT\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "\[Not Secure\]"; then
        PLAYER=$(echo "$LINE" | grep -oP "\[Not Secure\] <\K.*(?=>)")
        MESSAGE=$(echo "$LINE" | grep -oP "\[Not Secure\] <.*> \K.*")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"💬 *$PLAYER*: $MESSAGE\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "Done"; then
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🚀 **Servidor inicializado com sucesso!**\"}" "$WEBHOOK_URL"
    fi
done
