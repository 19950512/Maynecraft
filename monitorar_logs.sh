#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/opt/minecraft/src/logs/latest.log"

# Load .env
if [ -f "$SCRIPT_DIR/src/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/src/.env" | xargs)
else
    echo "❌ Arquivo .env não encontrado. Abortando."
    exit 1
fi

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
