#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env
# Carrega variáveis do arquivo .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
else
    echo "❌ Arquivo .env não encontrado em $SCRIPT_DIR. Abortando."
    exit 1
fi

WEBHOOK_URL="$DISCORD_WEBHOOK_URL"

SESSION_NAME="minecraft"
SERVER_DIR="/opt/minecraft/src"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"
TMP_PLAYER_IPS="/tmp/current_players_ips.txt"

mkdir -p /tmp
> "$TMP_PLAYER_IPS"

if [ ! -f "$ALLOWED_PLAYERS_FILE" ]; then
    echo "❌ Arquivo de jogadores permitidos não encontrado. Criando novo arquivo..."
    touch "$ALLOWED_PLAYERS_FILE"
    echo "Lista criada. Adicione os jogadores permitidos ao arquivo $ALLOWED_PLAYERS_FILE."
    exit 1
fi

send_discord_log() {
    local player="$1"
    local ip="$2"
    local motivo="$3"

    json=$(cat <<EOF
{
  "embeds": [{
    "title": "🚫 Jogador bloqueado",
    "color": 16711680,
    "fields": [
      { "name": "Jogador", "value": "$player", "inline": true },
      { "name": "IP", "value": "$ip", "inline": true },
      { "name": "Motivo", "value": "$motivo" }
    ]
  }]
}
EOF
)
    curl -s -X POST -H "Content-Type: application/json" -d "$json" "$WEBHOOK_URL" > /dev/null
}

# Limpar entradas antigas de IPs no cache (mais de 1 hora, 3600 segundos)
clean_old_cache() {
    current_time=$(date +%s)
    temp_file=$(mktemp)

    while read player ip timestamp; do
        if [ $((current_time - timestamp)) -lt 3600 ]; then
            echo "$player $ip $timestamp" >> "$temp_file"
        fi
    done < "$TMP_PLAYER_IPS"

    mv "$temp_file" "$TMP_PLAYER_IPS"
}

check_players() {
    tmux capture-pane -t "$SESSION_NAME" -pS -150 | while read line; do
        if echo "$line" | grep -q "logged in with entity id"; then
            player=$(echo "$line" | grep -oP "\]: \K.*(?=\[)")
            ip=$(echo "$line" | grep -oP "(/[\d\.]+)" | tr -d '/')
            if [ -n "$player" ] && [ -n "$ip" ]; then
                timestamp=$(date +%s)  # Marca o tempo do IP
                echo "$player $ip $timestamp" >> "$TMP_PLAYER_IPS"
            fi
        elif echo "$line" | grep -q "joined the game"; then
            player=$(echo "$line" | awk -F" " '{print $4}')
            ip=$(grep "^$player " "$TMP_PLAYER_IPS" | awk '{print $2}' | tail -n 1)
            timestamp=$(grep "^$player " "$TMP_PLAYER_IPS" | awk '{print $3}' | tail -n 1)
            linha=$(grep "^$player:" "$ALLOWED_PLAYERS_FILE")
            
            if [ -z "$linha" ]; then
                echo "⚠️ Jogador $player não está na whitelist. Kickando..."
                sudo tmux send-keys -t "$SESSION_NAME" "kick $player Jogador não permitido" C-m
                send_discord_log "$player" "$ip" "Não está na whitelist"
            else
                allowed_ip=$(echo "$linha" | cut -d':' -f2)
                if [ "$ip" != "$allowed_ip" ]; then
                    echo "⚠️ IP diferente para $player. Kickando..."
                    sudo tmux send-keys -t "$SESSION_NAME" "kick $player IP não autorizado" C-m
                    send_discord_log "$player" "$ip" "IP não autorizado (esperado: $allowed_ip)"
                fi
            fi
        fi
    done
}

# Rodar a limpeza do cache de IPs a cada 15 minutos
clean_old_cache

while true; do
    check_players
    clean_old_cache
    sleep 1
done
