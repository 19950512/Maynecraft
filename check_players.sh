#!/bin/bash

SESSION_NAME="minecraft"
SERVER_DIR="/opt/minecraft/src"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"
ALLOWED_IPS_FILE="$SERVER_DIR/allowed_ips.txt"
TMP_PLAYER_IPS="/tmp/current_players_ips.txt"

mkdir -p /tmp
> "$TMP_PLAYER_IPS"

if [ ! -f "$ALLOWED_PLAYERS_FILE" ]; then
    echo "❌ Arquivo de jogadores permitidos não encontrado. Criando novo arquivo..."
    touch "$ALLOWED_PLAYERS_FILE"
    echo "Lista criada. Adicione os jogadores permitidos ao arquivo $ALLOWED_PLAYERS_FILE."
    exit 1
fi

if [ ! -f "$ALLOWED_IPS_FILE" ]; then
    touch "$ALLOWED_IPS_FILE"
fi

check_players() {
    # Lê os últimos 150 registros e salva IPs e jogadores temporariamente
    tmux capture-pane -t "$SESSION_NAME" -pS -150 | while read line; do
        if echo "$line" | grep -q "joined the game"; then
            player=$(echo "$line" | awk -F" " '{print $4}')
            # Verifica se está permitido
            if ! grep -q "^$player$" "$ALLOWED_PLAYERS_FILE"; then
                echo "⚠️ Jogador $player não está na lista. Kickando..."
                sudo tmux send-keys -t "$SESSION_NAME" "kick $player Jogador não permitido" C-m
            fi
        elif echo "$line" | grep -q "logged in with entity id"; then
            player=$(echo "$line" | grep -oP "\]: \K.*(?=\[)")
            ip=$(echo "$line" | grep -oP "(/[\d\.]+)" | tr -d '/')
            if [ -n "$player" ] && [ -n "$ip" ]; then
                echo "$player $ip" >> "$TMP_PLAYER_IPS"
            fi
        fi
    done
}

while true; do
    check_players
    sleep 1
done
