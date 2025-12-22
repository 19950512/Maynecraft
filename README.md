# 🎮 Maynecraft - Servidor Minecraft com Bot Discord

Servidor Minecraft 1.21.4 em Docker com bot Discord, controle de acesso e backups automáticos.

## 🚀 Início Rápido

```bash
# 1. Configurar variáveis
cp env-exemplo .env
nano .env  # Adicione DISCORD_TOKEN e DISCORD_WEBHOOK_URL

# 2. Iniciar servidor
make up

# 3. Conectar no Minecraft
# localhost:25565
```

## 🎮 Comandos do Bot (Discord)

Use `/` para acessar os comandos slash:

| Comando | Descrição |
|---------|-----------|
| `/players` | Mostra jogadores online |
| `/estatisticas <nome>` | Estatísticas do jogador |
| `/comandos` | Lista de comandos |
| `/addplayer <nome> <ip>` | Adiciona à whitelist |
| `/kick <nome>` | Expulsa jogador |
| `/give <nome> <item> [qty]` | Dá item ao jogador |

## 🛠️ Comandos Make (Terminal)

```bash
make up              # Inicia servidor
make down            # Para servidor
make restart         # Reinicia
make logs            # Ver logs
make logs-minecraft  # Logs do Minecraft
make logs-bot        # Logs do bot
make console         # Acesso ao console
make backup          # Backup manual
make help            # Lista todos os comandos
```

## 📁 Estrutura

```
Maynecraft/
├── Dockerfile              # Imagem Docker
├── docker-compose.yml      # Orquestração
├── docker-entrypoint.sh    # Inicialização
├── Makefile                # Atalhos úteis
│
├── configs/                # Templates de configuração
│   ├── server.properties   # Config do servidor
│   └── eula.txt           # Aceitar EULA
│
├── .env                    # Variáveis (NÃO commitar!)
├── env-exemplo            # Exemplo de .env
│
├── bot.py                 # Bot Discord
├── backup.py              # Backup automático
├── check_players.sh       # Whitelist customizada
├── monitorar_logs.sh      # Notificações Discord
│
└── server-data/           # Dados persistentes
    ├── world/             # Mundo do Minecraft
    ├── logs/              # Logs do servidor
    └── allowed_players.txt # Whitelist customizada
```

## ⚙️ Configuração

### `.env` (obrigatório)

```bash
DISCORD_TOKEN=seu_token_aqui
DISCORD_WEBHOOK_URL=seu_webhook_aqui
MINECRAFT_SERVER_URL=https://...server.jar
TMUX_SESSION=minecraft

# Opcional - Backups em R2
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=...

# Opcional - Guild ID para sync rápido de slash commands
DISCORD_GUILD_ID=seu_guild_id
```

### `configs/server.properties`

Edite para customizar:
- `motd=Pintu!` - Nome do servidor
- `max-players=18` - Máximo de jogadores
- `difficulty=hard` - Dificuldade
- `whitelist-names=19950512:any,Heitor:172.21.0.1` - Lista de acesso

**Formato whitelist-names:**
- `nome` - Aceita qualquer IP (registra na primeira conexão)
- `nome:ip` - Aceita apenas do IP específico
- `nome:any` - Igual ao primeiro (compatibilidade)

## 🔐 Whitelist Customizada

O servidor usa whitelist customizada via `check_players.sh` (não a do Minecraft).

**Fluxo:**
1. Jogador tenta conectar → log capturado
2. `check_players.sh` valida nome + IP contra `allowed_players.txt`
3. Se inválido → kick automático
4. Se válido com IP "any" → registra IP real

**Adicionar jogador:**
```bash
# Via bot Discord
/addplayer Heitor 172.21.0.1

# Ou manualmente
echo "Heitor:172.21.0.1" >> server-data/allowed_players.txt
```

## 📊 Eventos no Discord

O bot monitora e notifica automaticamente:
- ✅ Servidor iniciado
- 🔓 Entrada (com IP)
- 🟢 Entrou no jogo
- 🔴 Saiu do servidor
- 💀 Morte (causa traduzida)
- 🎖️ Avanço desbloqueado
- 💬 Chat do servidor

## 💾 Backups

**Automáticos:** A cada 3 horas (via cron)
- Local: `./backups/`
- Opcional: Upload para Cloudflare R2

**Manual:**
```bash
make backup
# ou
/backup (no Discord)
```

## 🚨 Problemas Comuns

### Bot não responde
- Verifique `DISCORD_TOKEN` e `DISCORD_WEBHOOK_URL` no `.env`
- Convide o bot com escopos `bot` + `applications.commands`
- Reinicie: `make restart`

### Jogadores não conseguem entrar
- Verifique `allowed_players.txt` no `server-data/`
- Se vazio → todos bloqueados (adicione via `/addplayer`)
- Verifique se `check_players.sh` está rodando: `docker exec minecraft-server ps aux | grep check_players`

### Servidor não inicia
```bash
make logs
# Procure por erros
```

### Porta 25565 em uso
```bash
make stop-old
# Mata processos antigos
```

## 📌 Notas Importantes

- ⚠️ **NÃO commitar `.env`** (contém tokens sensíveis)
- ⚠️ Whitelist vazia = servidor fechado (ninguém entra)
- ⚠️ `online-mode=false` = servidor offline (qualquer nome de usuário)
- ✅ Backups automáticos a cada 3 horas
- ✅ Logs centralizados em `./logs/`
- ✅ Stats de jogadores via `/estatisticas`

## 🔗 Úteis

- [Server.jar Download](https://launcher.mojang.com/v1/objects)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Cloudflare R2](https://www.cloudflare.com/pt-br/products/r2/)

---

**Pronto?** → `make up` e bom jogo! 🎮
