#!/bin/bash

# Carrega variáveis do .env
if [ -f "/opt/minecraft/src/.env" ]; then
    export $(grep -v '^#' /opt/minecraft/src/.env | xargs)
else
    echo "❌ Arquivo .env não encontrado em /opt/minecraft/src. Abortando."
    exit 1
fi

SESSION_NAME="${TMUX_SESSION:-minecraft}"
SERVER_DIR="/opt/minecraft/src"
SERVER_JAR="server-1.21.4.jar"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"
JAVA_XMS="${JAVA_XMS:-1G}"  # fallback padrão
JAVA_XMX="${JAVA_XMX:-2G}"

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
    echo "🚀 Iniciando servidor Minecraft com ${JAVA_XMS} mínimo e ${JAVA_XMX} máximo de memória..."
    tmux new-session -d -s "$SESSION_NAME" "/usr/bin/java -Xms${JAVA_XMS} -Xmx${JAVA_XMX} -jar $SERVER_JAR nogui"
    sleep 2
    echo "✅ Servidor iniciado no tmux com sucesso!"
fi
