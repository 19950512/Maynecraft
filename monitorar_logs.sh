#!/bin/bash

# Caminho onde este script está
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Carrega variáveis do arquivo .env
if [ -f "$SCRIPT_DIR/src/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/src/.env" | xargs)
else
    echo "❌ Arquivo .env não encontrado em $SCRIPT_DIR. Abortando."
    exit 1
fi

LOG_FILE="/opt/minecraft/src/logs/latest.log"
WEBHOOK_URL="$DISCORD_WEBHOOK_URL"

tail -n0 -F "$LOG_FILE" | while read LINE; do
    if echo "$LINE" | grep -q "joined the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= joined the game)")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🟢 **$PLAYER entrou no servidor.**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "left the game"; then
        PLAYER=$(echo "$LINE" | grep -oP "\]: \K.*(?= left the game)")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🔴 **$PLAYER saiu do servidor.**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "has made the advancement"; then
        ADV=$(echo "$LINE" | grep -oP "\]: \K.*")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🎖️ **$ADV**\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -E -q "was slain|was shot|was killed|fell from|tried to|drowned|burned|blew up"; then
        DEATH=$(echo "$LINE" | grep -oP "\]: \K.*")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"💀 $DEATH\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "\[Not Secure\]"; then
        PLAYER=$(echo "$LINE" | grep -oP "\[Not Secure\] <\K.*(?=>)")
        MESSAGE=$(echo "$LINE" | grep -oP "\[Not Secure\] <.*> \K.*")
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"💬 *$PLAYER*: $MESSAGE\"}" "$WEBHOOK_URL"
    elif echo "$LINE" | grep -q "Done"; then
        curl -s -H "Content-Type: application/json" -X POST -d "{\"content\": \"🚀 **Servidor inicializado com sucesso!**\"}" "$WEBHOOK_URL"
    fi
done
