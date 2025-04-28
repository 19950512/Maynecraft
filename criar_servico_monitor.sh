#!/bin/bash

MONITOR_SCRIPT="/opt/minecraft/monitorar_logs.sh"

# Copia o script de monitoramento para o diretório correto
echo "📄 Copiando script de monitoramento de logs para $MONITOR_SCRIPT..."
cp "$(dirname "$0")/monitorar_logs.sh" "$MONITOR_SCRIPT"

# Garantir permissões de execução no script copiado
echo "🔧 Garantindo permissões de execução no script..."
chmod +x "$MONITOR_SCRIPT"

# Cria o serviço no systemd
echo "🛠️ Criando o serviço minecraft-discord.service..."
sudo tee /etc/systemd/system/minecraft-discord.service > /dev/null <<EOL
[Unit]
Description=Minecraft Log Monitor for Discord
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/minecraft
ExecStart=$MONITOR_SCRIPT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

# Atualiza o systemd e reinicia o serviço
echo "🔄 Atualizando e iniciando o serviço..."
sudo systemctl daemon-reload
sudo systemctl enable minecraft-discord.service
sudo systemctl restart minecraft-discord.service

echo "✅ Serviço minecraft-discord.service criado e iniciado!"
