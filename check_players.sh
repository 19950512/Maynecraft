#!/bin/bash

SESSION_NAME="minecraft"
SERVER_DIR="/opt/minecraft/src"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"

# Verifica se o arquivo de jogadores permitidos existe
if [ ! -f "$ALLOWED_PLAYERS_FILE" ]; then
    echo "❌ Arquivo de jogadores permitidos não encontrado. Criando novo arquivo..."
    touch "$ALLOWED_PLAYERS_FILE"
    echo "Lista criada. Adicione os jogadores permitidos ao arquivo $ALLOWED_PLAYERS_FILE."
    exit 1
fi

# Função para verificar e kickar jogadores não permitidos
check_players() {
    # Captura o log da última parte da sessão tmux
    tmux capture-pane -t "$SESSION_NAME" -pS -5 | grep "joined the game" | while read line; do
        # Extrai o nome do jogador usando awk
        player=$(echo "$line" | awk -F" " '{print $4}')
        
        # Verifica se o jogador está na lista de permitidos
        if ! grep -q "^$player$" "$ALLOWED_PLAYERS_FILE"; then
            echo "⚠️ Jogador $player não está na lista. Kickando..."
            # Envia o comando para kickar o jogador
            sudo tmux send-keys -t "$SESSION_NAME" "kick $player Jogador não permitido" C-m
        fi
    done
}

# Monitoramento contínuo de jogadores
while true; do
    check_players
    sleep 2  # Verifica a cada 2 segundos
done
