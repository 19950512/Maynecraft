#!/bin/bash
set -e

# As variáveis de ambiente já vêm do docker-compose.yml via env_file
# Se precisar de debug, descomente:
# echo "DISCORD_WEBHOOK_URL: ${DISCORD_WEBHOOK_URL:0:50}..."
# echo "DISCORD_TOKEN: ${DISCORD_TOKEN:0:20}..."

# Define variáveis padrão
MINECRAFT_DIR=${MINECRAFT_DIR:-/minecraft/server}
TMUX_SESSION=${TMUX_SESSION:-minecraft}
MINECRAFT_SERVER_URL=${MINECRAFT_SERVER_URL:-https://piston-data.mojang.com/v1/objects/4707d00eb834b446575d89a61a11b5d548d8c001/server.jar}
TEMPLATE_DIR=/minecraft/configs
TARGET_PROPS="$MINECRAFT_DIR/server.properties"

# Se volume vazio ou incompleto, copia templates necessários
if [ ! -f "$TARGET_PROPS" ] && [ -f "$TEMPLATE_DIR/server.properties" ]; then
    echo "📄 Copiando template de server.properties..."
    cp "$TEMPLATE_DIR/server.properties" "$TARGET_PROPS"
fi

if [ ! -f "$MINECRAFT_DIR/eula.txt" ] && [ -f "$TEMPLATE_DIR/eula.txt" ]; then
    echo "📄 Copiando eula.txt..."
    cp "$TEMPLATE_DIR/eula.txt" "$MINECRAFT_DIR/eula.txt"
fi

# Ajusta server.properties (força algumas configs e preserva outras do template)
if [ -f "$TARGET_PROPS" ]; then
    echo "🔧 Ajustando server.properties..."
    export TARGET_PROPS
    export TEMPLATE_DIR
    python3 << 'PYEOF'
import os

props_file = os.environ['TARGET_PROPS']
template_file = os.path.join(os.environ['TEMPLATE_DIR'], 'server.properties')

# Lê props atuais
current = {}
if os.path.exists(props_file):
    with open(props_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                current[key] = val

# Lê template
template = {}
if os.path.exists(template_file):
    with open(template_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                template[key] = val

# Pega valores do template (ou defaults)
online_mode_value = template.get('online-mode', 'false')
whitelist_value = template.get('whitelist', 'false')
enforce_whitelist_value = template.get('enforce-whitelist', 'false')

# Configurações forçadas (respeita valores do template)
forced = {
    'online-mode': online_mode_value,
    'whitelist': whitelist_value,
    'white-list': whitelist_value, 
    'enforce-whitelist': enforce_whitelist_value
}

# Mescla: atual > template > forçadas (template tem prioridade sobre o volume)
final = {}
final.update(current)
final.update(template)
final.update(forced)

# Se há whitelist-names no template, adiciona ao final
if 'whitelist-names' in template:
    final['whitelist-names'] = template['whitelist-names']

# Escreve de volta
with open(props_file, 'w') as f:
    for key, val in sorted(final.items()):
        f.write(f'{key}={val}\n')
PYEOF
fi

# Cria diretório de logs se não existir
mkdir -p "$MINECRAFT_DIR/logs"

# Download do server.jar se não existir
if [ ! -f "$MINECRAFT_DIR/server.jar" ]; then
    echo "⬇️  Baixando servidor Minecraft..."
    cd "$MINECRAFT_DIR"
    wget -q "$MINECRAFT_SERVER_URL" -O server.jar
    echo "✅ Download concluído"
fi

# eula.txt já vem do template

# Gera whitelist.json e allowed_players.txt a partir de whitelist-names
if [ -f "$TARGET_PROPS" ]; then
    WHITELIST_NAMES=$(grep -E '^whitelist-names=' "$TARGET_PROPS" | cut -d'=' -f2 || echo "")

    if [ -n "$WHITELIST_NAMES" ]; then
        echo "👥 Gerando whitelist.json e allowed_players.txt a partir de: $WHITELIST_NAMES"

        export WHITELIST_NAMES
        export MINECRAFT_DIR
        python3 << PYEOF
import json
import uuid
import os

names_raw = os.environ.get('WHITELIST_NAMES', '')
tokens = [t.strip() for t in names_raw.split(',') if t.strip()]

# tokens aceitam "nome" ou "nome:ip"
players = []
for t in tokens:
    if ':' in t:
        name, ip = t.split(':', 1)
        name = name.strip()
        ip = ip.strip() or 'any'
        players.append({'name': name, 'ip': ip})
    else:
        players.append({'name': t, 'ip': 'any'})

# Gera whitelist.json (somente nomes)
whitelist = []
for p in players:
    offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{p['name']}"))
    whitelist.append({
        "uuid": offline_uuid,
        "name": p['name']
    })

whitelist_path = os.path.join(os.environ['MINECRAFT_DIR'], 'whitelist.json')
with open(whitelist_path, 'w') as f:
    json.dump(whitelist, f, indent=2)

# Gera allowed_players.txt para check_players.sh
allowed_players_path = os.path.join(os.environ['MINECRAFT_DIR'], 'allowed_players.txt')
with open(allowed_players_path, 'w') as f:
    for p in players:
        f.write(f"{p['name']}:{p['ip']}\n")

print(f"✅ Whitelist gerada com {len(whitelist)} jogadores")
print(f"✅ allowed_players.txt criado com {len(players)} jogadores")
PYEOF
    fi
fi

# Inicia tmux
echo "🎮 Iniciando servidor Minecraft no tmux..."
cd "$MINECRAFT_DIR"

# Cria sessão tmux e inicia servidor
tmux new-session -d -s "$TMUX_SESSION" "java -Xmx${MAX_RAM:-1024M} -Xms${MIN_RAM:-1024M} -jar server.jar nogui"

# Aguarda o servidor inicializar um pouco
sleep 5

# Inicializa objetivos de scoreboard para estatísticas usadas pelo bot
echo "📈 Inicializando objetivos de scoreboard..."
tmux send-keys -t "$TMUX_SESSION" "scoreboard objectives add playtime minecraft.custom:minecraft.play_time" Enter
tmux send-keys -t "$TMUX_SESSION" "scoreboard objectives add jumps minecraft.custom:minecraft.jump" Enter
tmux send-keys -t "$TMUX_SESSION" "scoreboard objectives add mortes minecraft.custom:minecraft.deaths" Enter
tmux send-keys -t "$TMUX_SESSION" "scoreboard objectives add kills minecraft.custom:minecraft.player_kills" Enter
tmux send-keys -t "$TMUX_SESSION" "scoreboard objectives add mobkills minecraft.custom:minecraft.mob_kills" Enter

# Inicia monitoramento de logs (em background)
echo "📊 Iniciando monitoramento de logs..."
nohup /minecraft/monitorar_logs.sh > /minecraft/logs/monitor.log 2>&1 &

# Inicia verificação de jogadores (em background)
echo "🛡️  Iniciando verificação de jogadores..."
nohup /minecraft/check_players.sh > /minecraft/logs/check_players.log 2>&1 &

# Inicia bot Discord (em background)
echo "🤖 Iniciando bot Discord..."
cd /minecraft/bot
nohup /minecraft/venv/bin/python bot.py > /minecraft/logs/bot.log 2>&1 &

# Configura cron para backup a cada 3 horas
echo "⏰ Configurando backups automáticos..."
cat << 'CRONTAB' | crontab -
MINECRAFT_DIR=/minecraft/server
BACKUP_DIR=/minecraft/backups
TMUX_SESSION=minecraft
0 */3 * * * /minecraft/venv/bin/python /minecraft/backup.py >> /minecraft/logs/backup.log 2>&1
CRONTAB
service cron start

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   ✅ Servidor Minecraft Iniciado com Sucesso   ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "📌 Comandos úteis:"
echo "   docker exec -it minecraft-server tmux attach -t $TMUX_SESSION"
echo "   docker logs -f minecraft-server"
echo "   docker exec minecraft-server cat /minecraft/server/logs/latest.log"
echo ""

# Mantém container rodando
tail -f /dev/null
