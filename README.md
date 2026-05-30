# 🎮 Maynecraft — Servidor do Heitor Maydana

Servidor Minecraft 1.21.4 em Docker, **pensado para crianças** e **privado por convite**, com bot Discord cheio de comandos divertidos, integração de chat nos dois sentidos, presença dinâmica e backups automáticos.

> ✨ Servidor do **Heitor Maydana** — saiba como entrar em **https://heitormaydana.com.br**

## 🔒 Acesso seguro (cargo Discord obrigatório)

O servidor é **fechado**: apenas quem tem o cargo `Maynecrafter` (configurável) no Discord do Heitor consegue:

1. **Usar os comandos do bot** (exceto `/comandos` e `/acesso`, públicos)
2. **Entrar no servidor Minecraft**

### Fluxo para um novo amigo do Heitor

1. Visita **https://heitormaydana.com.br** e segue as instruções de entrada no Discord
2. Recebe o cargo `Maynecrafter` no Discord
3. Usa `/registrar SeuNickMinecraft` — isso vincula Discord ↔ nick e libera na whitelist
4. Conecta no servidor 🎮

Se o cargo for **revogado**, o bot detecta automaticamente (`on_member_update`), remove o nick da whitelist e expulsa o jogador, se estiver online.

### Comandos de acesso

| Comando | Quem usa | Descrição |
|---------|----------|-----------|
| `/acesso` | Todos | Mostra como entrar no servidor |
| `/registrar <nick>` | Com cargo | Vincula seu Discord ao nick Minecraft |
| `/meu_nick` | Com cargo | Mostra seu nick registrado |
| `/desregistrar` | Com cargo | Remove seu nick da whitelist |
| `/remover_acesso <@user>` | Admin | Revoga acesso completo |

Os registros ficam em `server-data/discord_registrations.json` e a whitelist customizada em `server-data/allowed_players.txt` (já gateada por `check_players.sh`).

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

Use `/` no Discord para acessar os comandos slash. O bot mostra os jogadores online no status.

### 😄 Para todos
| Comando | Descrição |
|---------|-----------|
| `/oi` | Recebe uma saudação fofa |
| `/piada` | Conta uma piada infantil de Minecraft |
| `/dado [lados]` | Rola um dado (2 a 100 lados) |
| `/ranking` | Top 3 jogadores em tempo de jogo |
| `/players` | Mostra os jogadores online |
| `/conversar <mensagem>` | Envia recado direto pro chat in-game |
| `/comandos` | Lista todos os comandos |

### ☀️ Clima e Tempo (Operador do Nether)
| Comando | Efeito |
|---------|--------|
| `/dia` | Faz nascer o sol 🌞 |
| `/noite` | Cai a noite 🌙 |
| `/sol` | Tempo limpo ☀️ |
| `/chuva` | Faz chover 🌧️ |
| `/anunciar <msg>` | Anuncia mensagem destacada no servidor |

### 💎 Magias (custam diamantes do inventário do jogador)
| Comando | Custo | Efeito |
|---------|-------|--------|
| `/curar <jogador>` | 2 💎 | Cura vida e fome completamente |
| `/voar <jogador>` | 3 💎 | Habilita voo por 3 minutos |
| `/efeito <jogador> <efeito>` | 2 💎 | Força, velocidade, invisível, saltar alto, respirar água, visão noturna, imune ao fogo |
| `/mascote <jogador> <tipo>` | 5 💎 | Invoca lobo, gato, papagaio, cavalo selado ou raposa |
| `/foguete <jogador>` | 1 💎 | Lança o jogador pro céu (com slow falling) 🚀 |
| `/teleportar <jogador> <destino>` | 5 💎 | Coordenadas, `nether`, `end` ou `overworld` |

### 🔧 Administração
| Comando | Descrição |
|---------|-----------|
| `/addplayer <nome> <ip>` | Adiciona à whitelist customizada |
| `/kick <nome>` | Expulsa jogador |
| `/give <nome> <item> [qty]` | Dá item ao jogador |
| `/estatisticas <nome>` | Estatísticas detalhadas |
| `/kit_inicial <nome>` | Kit completo pra recomeçar |

## 💬 Chat bidirecional Discord ↔ Minecraft

- **In-game → Discord**: o monitor de logs já envia o chat para o webhook.
- **Discord → In-game**: defina `MINECRAFT_CHAT_CHANNEL_ID` no `.env` com o ID
  de um canal Discord. Toda mensagem nesse canal vira `[Discord] Autor: msg`
  no chat do jogo (filtrada e segura).

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
│   ├── server.properties   # Config do servidor (já personalizado p/ Heitor)
│   └── eula.txt
│
├── .env                    # Variáveis (NÃO commitar!)
├── env-exemplo
│
├── bot.py                  # Bot Discord (comandos divertidos)
├── backup.py               # Backup automático
├── check_players.sh        # Whitelist customizada
├── monitorar_logs.sh       # Eventos no Discord (embeds + saudação no jogo)
│
└── server-data/            # Dados persistentes
    ├── world/              # Mundo do Minecraft
    ├── logs/               # Logs do servidor
    └── allowed_players.txt # Whitelist customizada
```

## ⚙️ Configuração padrão (kid-friendly)

O `configs/server.properties` já vem com defaults pensados pra criançada:

- `motd` colorido **"✨ Servidor do Heitor Maydana ✨"**
- `difficulty=easy` — desafio sem ser cruel
- `gamemode=survival` — survival clássico (use `/give`, `/voar` etc. pra ajudar)
- `pvp=false` — sem brigas entre jogadores
- `spawn-protection=16` — área de spawn protegida contra grief
- `allow-flight=true` — permite voo (Elytra, magias)
- `announce-player-achievements=true`
- `whitelist-names=` — preencha com os amigos do Heitor

### `.env` (obrigatório)

```bash
DISCORD_TOKEN=seu_token_aqui
DISCORD_WEBHOOK_URL=seu_webhook_aqui
MINECRAFT_SERVER_URL=https://...server.jar
TMUX_SESSION=minecraft

# Opcional
DISCORD_GUILD_ID=seu_guild_id              # sync rápido de slash commands
MINECRAFT_CHAT_CHANNEL_ID=id_do_canal      # chat Discord → in-game
MINECRAFT_ROLE_NAME=Maynecrafter           # cargo Discord obrigatório
WEBSITE_URL=https://heitormaydana.com.br   # site do Heitor

# Opcional - Backups em R2
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=...
```

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

## 📊 Eventos no Discord (embeds bonitos)

O bot monitora e notifica automaticamente, com cores e emojis:
- 🚀 **Servidor online**
- 🔓 **Nova conexão** (com IP)
- 🟢 **Jogador entrou** (+ saudação aleatória no chat do jogo)
- 🔴 **Jogador saiu**
- 💀 **Morte** com causa traduzida em PT-BR
- 🎖️ **Conquista** desbloqueada
- 🏆 **Desafio** concluído
- 💬 **Chat** do servidor (sem loops Discord ↔ in-game)

## 💾 Backups

**Automáticos:** A cada 3 horas (via cron)
- Local: `./backups/`
- Opcional: Upload para Cloudflare R2

**Manual:**
```bash
make backup
```

## 🚨 Problemas Comuns

### Bot não responde
- Verifique `DISCORD_TOKEN` e `DISCORD_WEBHOOK_URL` no `.env`
- Convide o bot com escopos `bot` + `applications.commands`
- Habilite **Message Content Intent** no Discord Developer Portal (necessário para `/conversar` e ponte de chat)
- Reinicie: `make restart`

### Jogadores não conseguem entrar
- Verifique `allowed_players.txt` no `server-data/`
- Se vazio → todos bloqueados (adicione via `/addplayer`)

### Servidor não inicia
```bash
make logs
```

### Porta 25565 em uso
```bash
make stop-old
```

## 📌 Notas Importantes

- ⚠️ **NÃO commitar `.env`** (contém tokens sensíveis)
- ⚠️ Whitelist vazia = servidor fechado
- ⚠️ `online-mode=false` = qualquer nome de usuário entra
- ✅ Backups automáticos a cada 3 horas
- ✅ PvP desligado por padrão (kid-friendly)
- ✅ Bot mostra contagem de jogadores no status

## 🔗 Úteis

- [Server.jar Download](https://launcher.mojang.com/v1/objects)
- [Discord Developer Portal](https://discord.com/developers/applications)
- [Cloudflare R2](https://www.cloudflare.com/pt-br/products/r2/)

---

**Pronto, Heitor?** → `make up` e bom jogo! 🎮✨
