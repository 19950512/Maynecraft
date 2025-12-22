# 🎮 Maynecraft - Servidor Minecraft Automatizado com Bot Discord

Servidor Minecraft completo, dockerizado, com bot Discord integrado, backups automáticos e documentação abrangente.

## 🚀 Início Rápido (2 minutos)

```bash
# 1. Configurar
cp env-exemplo .env
nano .env  # Preencha DISCORD_TOKEN e DISCORD_WEBHOOK_URL

# 2. Iniciar
make up

# 3. Conectar
# Minecraft → Multiplayer → Add Server → localhost:25565
```

## 📚 Documentação

### 🎯 Para Iniciantes
- **[SETUP.md](SETUP.md)** ⭐ - Guia passo a passo completo de configuração
- **[INICIO-RAPIDO.md](INICIO-RAPIDO.md)** - Resumo em 3 passos

### ⚙️ Configurações
- **[BOT-DISCORD.md](BOT-DISCORD.md)** - Como criar e configurar o bot
- **[SERVIDOR-CONFIG.md](SERVIDOR-CONFIG.md)** - Configurar server.properties
- **[WHITELIST.md](WHITELIST.md)** - Gerenciar lista de jogadores permitidos

### 🐳 Docker
- **[README-DOCKER.md](README-DOCKER.md)** - Documentação Docker completa
- **[DOCKER-MIGRATION.md](DOCKER-MIGRATION.md)** - Migrar de shell scripts
- **[ESTRUTURA.md](ESTRUTURA.md)** - Estrutura do projeto

### 🎨 Referência
- **[env-exemplo](env-exemplo)** - Exemplo de arquivo .env com comentários

## ✨ Funcionalidades

- 🐳 **Docker**: Containerizado e isolado
- 🤖 **Bot Discord**: Controle completo via Discord
- 💾 **Backups Automáticos**: A cada 3 horas (local ou R2)
- 📊 **Monitoring**: Logs centralizados
- 🔒 **Whitelist**: Controle de acesso
- ⚙️ **Configurável**: Tudo documentado
- 🎯 **Fácil de Usar**: Um comando para tudo

## 📋 Checklist de Configuração

- [ ] Arquivo `.env` preenchido
- [ ] DISCORD_TOKEN configurado
- [ ] DISCORD_WEBHOOK_URL configurado
- [ ] `configs/eula.txt` com `eula=true`
- [ ] `configs/server.properties` personalizado (opcional)
- [ ] Server iniciado: `make up`
- [ ] Conexão testada: `localhost:25565`
- [ ] Bot testado: `!status` no Discord

## 🎮 Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `!status` | Status do servidor |
| `!list` | Jogadores online |
| `!start` | Inicia o servidor |
| `!stop` | Para o servidor |
| `!restart` | Reinicia o servidor |
| `!backup` | Backup manual |
| `!say <msg>` | Envia mensagem no chat |

## 🛠️ Comandos Make (Terminal)

| Comando | Descrição |
|---------|-----------|
| `make up` | Inicia (para serviços antigos) |
| `make down` | Para |
| `make logs` | Ver logs |
| `make console` | Acessar console do Minecraft |
| `make backup` | Backup manual |
| `make restart` | Reiniciar |
| `make help` | Ver todos os comandos |

## 📂 Estrutura de Arquivos

```
Maynecraft/
├── 📖 Documentação
│   ├── SETUP.md              ⭐ COMECE AQUI
│   ├── BOT-DISCORD.md
│   ├── SERVIDOR-CONFIG.md
│   ├── WHITELIST.md
│   ├── README-DOCKER.md
│   ├── DOCKER-MIGRATION.md
│   └── ESTRUTURA.md
│
├── 🐳 Docker
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-entrypoint.sh
│   └── .dockerignore
│
├── ⚙️ Configuração
│   ├── env-exemplo           (copie para .env)
│   ├── .env                  (seu arquivo)
│   └── configs/
│       ├── eula.txt
│       └── server.properties
│
├── 🎮 Dados do Servidor
│   ├── server-data/          (mundo, configs do servidor)
│   ├── backups/              (backups automáticos)
│   └── logs/                 (logs)
│
├── 🤖 Bot e Scripts
│   ├── bot.py               (bot Discord)
│   ├── backup.py            (sistema de backup)
│   └── *.sh                 (scripts utilitários)
│
└── 🔧 Utilitários
    ├── Makefile             (comandos make)
    ├── iniciar-docker.sh    (setup Docker)
    └── README.md            (este arquivo)
```

## ⚠️ Primeiros Passos IMPORTANTE

1. **Leia [SETUP.md](SETUP.md)** - Guia completo
2. **Configure o bot Discord** - Ver [BOT-DISCORD.md](BOT-DISCORD.md)
3. **Preencha o `.env`** - Baseado em [env-exemplo](env-exemplo)
4. **Execute `make up`** - Inicia o servidor
5. **Teste a conexão** - Minecraft: localhost:25565

## 🔒 Segurança

- 🔐 Nunca compartilhe seu `DISCORD_TOKEN`
- 🔐 Nunca faça commit do `.env` no Git
- 🔐 Use whitelist se servidor é privado
- 🔐 Backups regulares!

## 🐛 Problemas Comuns

### Porta em uso?
```bash
make stop-old
```

### Bot não responde?
Ver [BOT-DISCORD.md](BOT-DISCORD.md) → Troubleshooting

### Servidor não inicia?
```bash
make logs
```

### Mais problemas?
Ver documentação específica ou abra uma issue

## 💡 Dicas Úteis

1. **Personalizar MOTD:**
   - Edite `configs/server.properties`
   - Veja [SERVIDOR-CONFIG.md](SERVIDOR-CONFIG.md) para cores

2. **Adicionar Jogadores:**
   - Use whitelist em [WHITELIST.md](WHITELIST.md)

3. **Configurar Backups:**
   - Local: automático em `./backups/`
   - R2: configure em `.env` e [BOT-DISCORD.md](BOT-DISCORD.md)

4. **Acessar Console:**
   ```bash
   make console
   ```

## 📞 Suporte

1. Veja a documentação relevante
2. Procure em Troubleshooting
3. Verifique os logs: `make logs`
4. Abra uma issue com detalhes

## 📝 Licença

MIT - Sinta-se à vontade para usar e modificar!

## 🎓 Próximos Passos

1. ✅ Configurar segundo [SETUP.md](SETUP.md)
2. ✅ Testar funcionalidades
3. ✅ Personalizar servidor
4. ✅ Convidar jogadores
5. ✅ Aproveitar! 🎮

---

**Pronto para começar?** → [Leia SETUP.md](SETUP.md) ⭐
