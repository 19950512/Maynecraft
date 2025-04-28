#!/bin/bash

set -e

# Caminho onde este script está
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Carrega variáveis do arquivo .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
else
    echo "❌ Arquivo .env não encontrado em $SCRIPT_DIR. Abortando."
    exit 1
fi

# Cria diretórios necessários
echo "📂 Criando diretórios em /opt/minecraft..."
sudo mkdir -p /opt/minecraft/src
sudo mkdir -p /opt/minecraft/logs
sudo mkdir -p /opt/minecraft/bot

# Instala tmux e Java 21 se necessário
if ! command -v tmux &> /dev/null; then
    echo "🛠️ Instalando tmux..."
    sudo apt update
    sudo apt install -y tmux
else
    echo "✅ tmux já instalado."
fi

if ! java -version 2>&1 | grep -q '21'; then
    echo "🛠️ Instalando OpenJDK 21..."
    sudo apt update
    sudo apt install -y openjdk-21-jdk
else
    echo "✅ Java 21 já instalado."
fi

# Instalar o Python e discord.py para o bot
# Verificar se o Python3 está instalado
if ! command -v python3 &> /dev/null; then
    echo "🛠️ Instalando Python 3..."
    sudo apt update
    sudo apt install -y python3
else
    echo "✅ Python 3 já instalado."
fi

# Verificar se o pip3 está instalado
if ! command -v pip3 &> /dev/null; then
    echo "🛠️ Instalando pip3..."
    sudo apt install -y python3-pip
else
    echo "✅ pip3 já instalado."
fi

# Verificar se o discord.py está instalado
if ! pip3 show discord &> /dev/null; then
    echo "🛠️ Instalando discord.py..."
    pip3 install discord
else
    echo "✅ discord.py já instalado."
fi

# Verificar e instalar python-dotenv se necessário
if ! pip3 show python-dotenv &> /dev/null; then
    echo "🛠️ Instalando python-dotenv..."
    pip3 install python-dotenv
else
    echo "✅ python-dotenv já instalado."
fi


# Copia arquivos de configuração do Minecraft
echo "📄 Copiando arquivos de configuração..."
sudo cp "$SCRIPT_DIR/.env" /opt/minecraft/src/.env
sudo cp "$SCRIPT_DIR/configs/eula.txt" /opt/minecraft/src/eula.txt
sudo cp "$SCRIPT_DIR/configs/server.properties" /opt/minecraft/src/server.properties

# Baixa o servidor Minecraft se necessário
cd /opt/minecraft/src
if [ ! -f server-1.21.4.jar ]; then
    echo "🌐 Baixando servidor Minecraft 1.21.4..."
    sudo wget -O server-1.21.4.jar "$MINECRAFT_SERVER_URL"
else
    echo "✅ Servidor já baixado."
fi

# Verifica se o arquivo bot.py está presente no diretório correto, e se não, pede para colocar
if [ ! -f "$SCRIPT_DIR/bot.py" ]; then
    echo "❌ bot.py não encontrado. Por favor, coloque o arquivo bot.py no diretório de instalação."
    exit 1
fi

# Adiciona o jogador "19950512" na lista de jogadores permitidos
ALLOWED_PLAYERS_FILE="/opt/minecraft/src/allowed_players.txt"
if ! grep -q "19950512" "$ALLOWED_PLAYERS_FILE"; then
    echo "19950512" >> "$ALLOWED_PLAYERS_FILE"
    echo "📄 Adicionando jogador '19950512' à lista de jogadores permitidos."
else
    echo "✅ Jogador '19950512' já está na lista de jogadores permitidos."
fi

# Copia o código do bot para o diretório correto
echo "📄 Copiando bot Python..."
sudo cp "$SCRIPT_DIR/bot.py" /opt/minecraft/bot/bot.py

# Cria o script para rodar o bot
echo "📄 Criando script para iniciar o bot..."
cat <<EOL > /opt/minecraft/bot/start_bot.sh
#!/bin/bash
cd /opt/minecraft/bot
python3 bot.py
EOL

# Torna o script executável
chmod +x /opt/minecraft/bot/start_bot.sh

# Verifica e cria o serviço systemd para o bot, se necessário
SERVICE_PATH="/etc/systemd/system/minecraft-bot.service"
if [ ! -f "$SERVICE_PATH" ]; then
    echo "📄 Criando serviço systemd para o bot..."
    sudo tee "$SERVICE_PATH" > /dev/null <<EOL
[Unit]
Description=Minecraft Discord Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/minecraft/bot
ExecStart=/opt/minecraft/bot/start_bot.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL
    echo "🔄 Atualizando daemon e habilitando serviço do bot..."
    sudo systemctl daemon-reload
    sudo systemctl enable minecraft-bot.service
else
    echo "✅ Serviço minecraft-bot.service já existe. Pulando criação."
fi

echo "▶️ Iniciando ou reiniciando serviço do bot..."
sudo systemctl restart minecraft-bot.service

# Inicia o servidor Minecraft
echo "🚀 Iniciando servidor Minecraft com tmux..."
bash "$SCRIPT_DIR/iniciar_minecraft.sh"

# Inicia o monitoramento dos logs
echo "👀 Iniciando monitoramento de logs..."
bash "$SCRIPT_DIR/criar_servico_monitor.sh"

# Verifica e cria o serviço systemd para o monitoramento, se necessário
SERVICE_MONITOR="/etc/systemd/system/minecraft-discord.service"
if [ ! -f "$SERVICE_MONITOR" ]; then
    echo "📄 Criando serviço systemd para monitoramento de logs..."
    sudo tee "$SERVICE_MONITOR" > /dev/null <<EOL
[Unit]
Description=Minecraft Log Monitor for Discord
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/minecraft
ExecStart=/opt/minecraft/monitorar_logs.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL
    echo "🔄 Atualizando daemon e habilitando serviço de monitoramento..."
    sudo systemctl daemon-reload
    sudo systemctl enable minecraft-discord.service
else
    echo "✅ Serviço minecraft-discord.service já existe. Pulando criação."
fi

echo "▶️ Iniciando ou reiniciando serviço de monitoramento..."
sudo systemctl restart minecraft-discord.service



# Copia o script check_players.sh para o diretório correto
echo "📄 Copiando script check_players.sh..."
sudo cp "$SCRIPT_DIR/check_players.sh" /opt/minecraft/src/check_players.sh

# Torna o script check_players.sh executável
chmod +x /opt/minecraft/src/check_players.sh

# **Adiciona o serviço de verificação de jogadores não permitidos (check_players.sh)**
echo "📄 Criando serviço systemd para verificação de jogadores..."
SERVICE_PLAYER_CHECK="/etc/systemd/system/minecraft-check-players.service"
if [ ! -f "$SERVICE_PLAYER_CHECK" ]; then
    sudo tee "$SERVICE_PLAYER_CHECK" > /dev/null <<EOL
[Unit]
Description=Minecraft Player Checker Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/minecraft/src
ExecStart=/opt/minecraft/src/check_players.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL
    echo "🔄 Atualizando daemon e habilitando serviço de verificação de jogadores..."
    sudo systemctl daemon-reload
    sudo systemctl enable minecraft-check-players.service
else
    echo "✅ Serviço minecraft-check-players.service já existe. Pulando criação."
fi

echo "▶️ Iniciando ou reiniciando serviço de verificação de jogadores..."
sudo systemctl restart minecraft-check-players.service

echo "✅ Tudo pronto!"
