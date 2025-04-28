#!/bin/bash

SESSION_NAME="minecraft"
SERVER_DIR="/opt/minecraft/src"
SERVER_JAR="server-1.21.4.jar"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"

cd "$SERVER_DIR" || exit

# Verifica se o arquivo de jogadores permitidos existe
if [ ! -f "$ALLOWED_PLAYERS_FILE" ]; then
    echo "❌ Arquivo de jogadores permitidos não encontrado. Criando novo arquivo..."
    touch "$ALLOWED_PLAYERS_FILE"
    echo "Lista criada. Adicione os jogadores permitidos ao arquivo $ALLOWED_PLAYERS_FILE."
    exit 1
fi

# Inicia o servidor Minecraft no tmux
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "⚡ Servidor já está rodando."
else
    echo "🚀 Iniciando servidor Minecraft..."
    tmux new-session -d -s "$SESSION_NAME" "/usr/bin/java -Xms2G -Xmx4G -jar $SERVER_JAR nogui"
    sleep 2  # Aguarda 2 segundos para garantir que o tmux foi iniciado corretamente
    echo "✅ Servidor iniciado no tmux com sucesso!"
fi