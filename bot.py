import re
import json
import random
import discord
from discord.ext import commands, tasks
from discord import app_commands
import subprocess
import asyncio
from dotenv import load_dotenv
import os
import logging

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém o token e a sessão do tmux a partir do .env
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TMUX_SESSION = os.getenv("TMUX_SESSION", "minecraft")  # Valor padrão 'minecraft' caso não esteja no .env
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

# ── Segurança: cargo do Discord obrigatório para usar comandos / entrar no jogo
MINECRAFT_ROLE_NAME = os.getenv("MINECRAFT_ROLE_NAME", "Maynecrafter")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://heitormaydana.com.br")

# Caminhos dos arquivos persistentes (dentro do volume server-data)
MINECRAFT_SERVER_DIR = os.getenv("MINECRAFT_DIR", "/minecraft/server")
ALLOWED_PLAYERS_FILE = os.path.join(MINECRAFT_SERVER_DIR, "allowed_players.txt")
REGISTRATIONS_FILE = os.path.join(MINECRAFT_SERVER_DIR, "discord_registrations.json")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # necessário para detectar mudanças de cargo (revogar whitelist)

class MayneBot(commands.Bot):
    async def setup_hook(self):
        # Sincroniza os comandos slash na inicialização
        try:
            if GUILD_ID:
                guild = discord.Object(id=int(GUILD_ID))
                await self.tree.sync(guild=guild)
                logging.info(f"Slash commands sincronizados para guild {GUILD_ID}")
            else:
                await self.tree.sync()
                logging.info("Slash commands sincronizados globalmente")
        except Exception as e:
            logging.error(f"Falha ao sincronizar slash commands: {e}")

bot = MayneBot(command_prefix='!', intents=intents)

# ──────────────────────────────────────────────
# Camada de segurança: cargo Discord obrigatório
# ──────────────────────────────────────────────
# Comandos que QUALQUER pessoa pode usar (sem cargo). Servem para orientar
# novos visitantes sobre como obter acesso.
COMANDOS_PUBLICOS = {"comandos", "acesso"}


def tem_cargo_minecraft(member: discord.abc.User) -> bool:
    """True se o membro do Discord tem o cargo configurado em MINECRAFT_ROLE_NAME."""
    if not isinstance(member, discord.Member):
        return False
    return any(role.name == MINECRAFT_ROLE_NAME for role in member.roles)


async def _global_interaction_check(interaction: discord.Interaction) -> bool:
    """Executado antes de qualquer slash command. Bloqueia quem não tem o cargo."""
    cmd_name = interaction.command.name if interaction.command else ""
    if cmd_name in COMANDOS_PUBLICOS:
        return True
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "⛔ Esses comandos só funcionam dentro do servidor Discord do Heitor.",
            ephemeral=True,
        )
        return False
    if not tem_cargo_minecraft(interaction.user):
        await interaction.response.send_message(
            f"🔒 **Acesso restrito!** Você precisa do cargo `{MINECRAFT_ROLE_NAME}` para usar os comandos.\n"
            f"👉 Veja como conseguir em: {WEBSITE_URL}\n"
            f"💡 Use `/acesso` para mais informações.",
            ephemeral=True,
        )
        return False
    return True


bot.tree.interaction_check = _global_interaction_check


# ──────────────────────────────────────────────
# Registro Discord ↔ Minecraft (whitelist)
# ──────────────────────────────────────────────

def _carregar_registros() -> dict:
    try:
        with open(REGISTRATIONS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salvar_registros(data: dict) -> None:
    os.makedirs(os.path.dirname(REGISTRATIONS_FILE), exist_ok=True)
    tmp = REGISTRATIONS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, REGISTRATIONS_FILE)


def _whitelist_add(player_name: str) -> bool:
    """Adiciona 'nome:any' ao allowed_players.txt se ainda não estiver lá."""
    os.makedirs(os.path.dirname(ALLOWED_PLAYERS_FILE), exist_ok=True)
    linhas = []
    if os.path.exists(ALLOWED_PLAYERS_FILE):
        with open(ALLOWED_PLAYERS_FILE) as f:
            linhas = f.read().splitlines()
    for linha in linhas:
        if linha.split(":", 1)[0].strip().lower() == player_name.lower():
            return False
    with open(ALLOWED_PLAYERS_FILE, "a") as f:
        f.write(f"{player_name}:any\n")
    return True


def _whitelist_remove(player_name: str) -> bool:
    if not os.path.exists(ALLOWED_PLAYERS_FILE):
        return False
    with open(ALLOWED_PLAYERS_FILE) as f:
        linhas = f.read().splitlines()
    novas = [l for l in linhas if l.split(":", 1)[0].strip().lower() != player_name.lower()]
    if len(novas) == len(linhas):
        return False
    with open(ALLOWED_PLAYERS_FILE, "w") as f:
        f.write("\n".join(novas) + ("\n" if novas else ""))
    return True


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Se o cargo Minecraft for revogado, remove o nick da whitelist e kicka."""
    tinha = any(r.name == MINECRAFT_ROLE_NAME for r in before.roles)
    tem = any(r.name == MINECRAFT_ROLE_NAME for r in after.roles)
    if tinha and not tem:
        regs = _carregar_registros()
        nick = regs.get(str(after.id))
        if nick:
            if _whitelist_remove(nick):
                logging.info(f"Removido {nick} da whitelist (cargo revogado de {after})")
                try:
                    send_command_to_minecraft(f"kick {nick} Acesso removido")
                except Exception:
                    pass


@bot.event
async def on_ready():
    try:
        # Copia comandos globais e sincroniza em cada guild do bot (sync instantâneo)
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logging.info(f"Slash commands sincronizados via on_ready para guild {guild.id} ({guild.name})")
    except Exception as e:
        logging.error(f"Falha ao sincronizar slash commands em on_ready: {e}")

    # Inicia atualização periódica da presença mostrando jogadores online
    if not atualizar_presenca.is_running():
        atualizar_presenca.start()


@tasks.loop(seconds=60)
async def atualizar_presenca():
    """Atualiza a presença do bot a cada minuto mostrando os jogadores online."""
    try:
        send_command_to_minecraft("list")
        await asyncio.sleep(1.2)
        output = await get_last_output_from_minecraft()
        # Tenta extrair número de jogadores online de saídas tipo
        # "There are 2 of a max of 18 players online: ..."
        match = re.search(r"There are\s+(\d+)\s+of\s+a\s+max\s+of\s+(\d+)", output)
        if match:
            online = int(match.group(1))
            maximo = int(match.group(2))
            if online == 0:
                texto = "esperando o Heitor chegar 💤"
            elif online == 1:
                texto = f"com {online} jogador no servidor 🎮"
            else:
                texto = f"com {online}/{maximo} jogadores 🎮"
        else:
            texto = "no Maynecraft do Heitor 🟢"
        await bot.change_presence(activity=discord.Game(name=texto))
    except Exception as e:
        logging.debug(f"Falha ao atualizar presença: {e}")


@atualizar_presenca.before_loop
async def _esperar_pronto():
    await bot.wait_until_ready()


# ──────────────────────────────────────────────
# Encaminhamento Discord → Minecraft (chat in-game)
# ──────────────────────────────────────────────
# Se a variável MINECRAFT_CHAT_CHANNEL_ID estiver definida com o ID de um canal
# Discord, toda mensagem nesse canal é repassada ao chat in-game como [Discord].
CHAT_CHANNEL_ID = os.getenv("MINECRAFT_CHAT_CHANNEL_ID")
try:
    CHAT_CHANNEL_ID = int(CHAT_CHANNEL_ID) if CHAT_CHANNEL_ID else None
except ValueError:
    CHAT_CHANNEL_ID = None


@bot.event
async def on_message(message: discord.Message):
    # Evita loops com o próprio bot e webhooks
    if message.author.bot:
        return
    if CHAT_CHANNEL_ID and message.channel.id == CHAT_CHANNEL_ID and message.content:
        autor = sanitize_for_minecraft(message.author.display_name)[:20] or "Discord"
        texto = sanitize_for_minecraft(message.content)[:200]
        if texto:
            try:
                # tellraw para colorir e diferenciar do chat normal
                tellraw = (
                    f'tellraw @a ["",'
                    f'{{"text":"[Discord] ","color":"aqua","bold":true}},'
                    f'{{"text":"{autor}","color":"yellow"}},'
                    f'{{"text":": ","color":"white"}},'
                    f'{{"text":"{texto}","color":"white"}}]'
                )
                send_command_to_minecraft(tellraw)
            except Exception as e:
                logging.warning(f"Falha ao encaminhar mensagem para o jogo: {e}")
    await bot.process_commands(message)

# Configuração de logging
logging.basicConfig(level=logging.INFO)

def send_command_to_minecraft(cmd):
    """Envia um comando ao console do Minecraft via tmux.
    O comando é sanitizado para evitar injeção."""
    # Sanitiza o comando inteiro como camada final de defesa
    cmd = sanitize_for_minecraft(cmd)
    if not cmd:
        raise ValueError("Comando vazio após sanitização.")
    # Limita tamanho do comando (comandos Minecraft não excedem ~256 chars)
    if len(cmd) > 300:
        raise ValueError("Comando excede o tamanho máximo permitido.")
    try:
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, cmd, 'Enter'], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao enviar comando para o Minecraft: {e}")
        raise

async def get_last_output_from_minecraft():
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-100'],
            capture_output=True, text=True, timeout=5
        )
        result.check_returncode()
        output = result.stdout.splitlines()

        # Procura pela última linha que contenha "There are" ou "Jogadores"
        for line in reversed(output):
            if "There are" in line or "Jogadores conectados" in line or "players" in line:
                return line.strip()
        return "❌ Não foi possível encontrar a saída do comando."
    except subprocess.CalledProcessError as e:
        logging.error(f"Erro ao capturar o painel do tmux: {e}")
        return "❌ Erro ao capturar informações do servidor."
    except Exception as e:
        logging.error(f"Erro inesperado ao obter a saída do Minecraft: {e}")
        return "❌ Erro inesperado."

def is_valid_player_name(player_name: str) -> bool:
    return bool(re.fullmatch(r"^[a-zA-Z0-9_]{3,16}$", player_name))

def is_valid_item_name(item_name: str) -> bool:
    """Valida nomes de itens do Minecraft (ex: minecraft:diamond, stone).
    Aceita apenas letras minúsculas, números, underscores, e opcionalmente
    um namespace com ':' (ex: minecraft:diamond_sword)."""
    return bool(re.fullmatch(r"^[a-z][a-z0-9_]*(:[a-z][a-z0-9_]*)?$", item_name))

def sanitize_for_minecraft(value: str) -> str:
    """Remove caracteres perigosos que podem ser usados para injeção de
    comandos via tmux send-keys (newlines, ;, &&, ||, etc.)."""
    # Remove qualquer caractere de controle (newlines, tabs, etc.)
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)
    # Remove caracteres que podem encadear comandos no shell ou no Minecraft
    value = re.sub(r"[;|&`$\\\"'{}\[\]()!#]", "", value)
    return value.strip()

def safe_error_message(e: Exception) -> str:
    """Retorna mensagem de erro segura sem expor caminhos ou detalhes internos."""
    error_str = str(e)
    # Remove caminhos absolutos do sistema
    error_str = re.sub(r"/[\w/.-]+", "[path]", error_str)
    # Limita tamanho
    if len(error_str) > 150:
        error_str = error_str[:150] + "..."
    return error_str

@bot.tree.command(name="players", description="Mostra os jogadores online")
async def players(interaction: discord.Interaction):
    try:
        await interaction.response.defer(thinking=True)
        send_command_to_minecraft("list")
        await asyncio.sleep(1.5)
        response = await get_last_output_from_minecraft()
        if response:
            await interaction.followup.send(f"👥 {response}")
        else:
            await interaction.followup.send("❌ Não foi possível obter a lista de jogadores.")
    except Exception as e:
        logging.error(f"Erro no comando players: {e}")
        await interaction.followup.send("❌ Erro ao tentar obter a lista de jogadores.")

@bot.tree.command(name="comandos", description="Lista os comandos disponíveis")
async def comandos(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Comandos do Servidor do Heitor Maydana",
        description=(
            f"Servidor privado por convite — saiba mais em **{WEBSITE_URL}** ✨\n"
            f"Precisa do cargo `{MINECRAFT_ROLE_NAME}` para usar a maioria dos comandos."
        ),
        color=0x00BFFF,
    )
    embed.add_field(
        name="🔒 Acesso (todos podem usar)",
        value=(
            "`/acesso` — Como entrar no servidor\n"
            "`/registrar <nick>` — Vincula seu Discord ao nick Minecraft\n"
            "`/meu_nick` — Mostra seu nick registrado\n"
            "`/desregistrar` — Remove seu nick da whitelist\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="😄 Diversão (para todos)",
        value=(
            "`/oi` — Receba uma saudação fofa\n"
            "`/piada` — Conta uma piada infantil\n"
            "`/dado [lados]` — Rola um dado (padrão 6)\n"
            "`/ranking` — Top 3 em tempo de jogo\n"
            "`/players` — Mostra jogadores online\n"
            "`/conversar <mensagem>` — Manda recado pro chat do jogo\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="☀️ Clima e tempo (Operador do Nether)",
        value=(
            "`/dia` — Faz nascer o sol 🌞\n"
            "`/noite` — Cai a noite 🌙\n"
            "`/sol` — Tempo limpo ☀️\n"
            "`/chuva` — Faz chover 🌧️\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="💎 Magias (custam diamantes do inventário)",
        value=(
            "`/curar <jogador>` — Cura tudo (2 💎)\n"
            "`/voar <jogador>` — Habilita voo por 3 min (3 💎)\n"
            "`/efeito <jogador> <efeito>` — Aplica efeito mágico (2 💎)\n"
            "`/mascote <jogador> <tipo>` — Invoca bichinho dócil (5 💎)\n"
            "`/foguete <jogador>` — Lança um foguetão 🚀 (1 💎)\n"
            "`/teleportar <jogador> <destino>` — Teleporta (5 💎)\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Outros",
        value=(
            "`/estatisticas <jogador>` — Estatísticas detalhadas\n"
            "`/kit_inicial <jogador>` — Kit completo para recomeçar\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔧 Administração",
        value=(
            "`/addplayer <jogador> <ip>` — Adiciona à whitelist\n"
            "`/kick <jogador>` — Expulsa jogador\n"
            "`/give <jogador> <item> [qty]` — Dá item ao jogador\n"
            "`/anunciar <mensagem>` — Anuncia no servidor\n"
            "`/remover_acesso <@usuário>` — Revoga acesso total\n"
        ),
        inline=False,
    )
    embed.set_footer(text="Servidor do Heitor Maydana • bom jogo!")
    await interaction.response.send_message(embed=embed)


# ──────────────────────────────────────────────
# Acesso (público) e Registro de nick Minecraft
# ──────────────────────────────────────────────

@bot.tree.command(name="acesso", description="Como ganhar acesso ao servidor Minecraft do Heitor")
async def acesso(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔒 Como entrar no Maynecraft do Heitor",
        description=(
            f"O servidor é **privado** — só amigos do Heitor entram! 💚\n\n"
            f"**Passo a passo:**\n"
            f"1️⃣ Acesse **{WEBSITE_URL}** e siga as instruções para entrar no Discord.\n"
            f"2️⃣ Peça o cargo **`{MINECRAFT_ROLE_NAME}`** ao Heitor ou aos pais dele.\n"
            f"3️⃣ Com o cargo, use `/registrar <seu_nick_minecraft>` aqui no Discord.\n"
            f"4️⃣ Pronto! Conecte no servidor Minecraft 🎮"
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name="❓ Já tenho o cargo, e agora?",
        value="Use `/registrar SeuNick` para liberar seu nick na whitelist.",
        inline=False,
    )
    embed.add_field(
        name="🌐 Site oficial",
        value=WEBSITE_URL,
        inline=False,
    )
    embed.set_footer(text="Servidor do Heitor Maydana • acesso por convite")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="registrar", description="Registra seu nick Minecraft e libera entrada no servidor")
@app_commands.describe(nick="Seu nome de usuário no Minecraft (3-16 caracteres)")
async def registrar(interaction: discord.Interaction, nick: str):
    await interaction.response.defer(thinking=True, ephemeral=True)

    if not is_valid_player_name(nick):
        return await interaction.followup.send(
            "❌ Nick inválido. Use 3-16 caracteres (letras, números, underscore).",
            ephemeral=True,
        )

    regs = _carregar_registros()
    user_id = str(interaction.user.id)

    # Já existe registro para este Discord?
    if user_id in regs and regs[user_id].lower() != nick.lower():
        nick_antigo = regs[user_id]
        # Remove o antigo da whitelist
        _whitelist_remove(nick_antigo)
        logging.info(f"{interaction.user} mudou o nick de {nick_antigo} para {nick}")

    # Verifica se nick já está em uso por OUTRO usuário
    for uid, n in regs.items():
        if uid != user_id and n.lower() == nick.lower():
            return await interaction.followup.send(
                f"⛔ O nick `{nick}` já foi registrado por outra pessoa no Discord. "
                f"Use um nick diferente ou peça ao Heitor para resolver.",
                ephemeral=True,
            )

    regs[user_id] = nick
    _salvar_registros(regs)
    novo = _whitelist_add(nick)

    msg = (
        f"✅ Nick `{nick}` registrado com sucesso!\n"
        f"{'🆕 Adicionado à whitelist.' if novo else '♻️ Já estava na whitelist.'}\n"
        f"🎮 Conecte agora no Minecraft."
    )
    await interaction.followup.send(msg, ephemeral=True)


@bot.tree.command(name="meu_nick", description="Mostra qual nick Minecraft está vinculado ao seu Discord")
async def meu_nick(interaction: discord.Interaction):
    regs = _carregar_registros()
    nick = regs.get(str(interaction.user.id))
    if nick:
        await interaction.response.send_message(
            f"🎮 Seu nick registrado é: **`{nick}`**", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "ℹ️ Você ainda não registrou. Use `/registrar <seu_nick>`.", ephemeral=True
        )


@bot.tree.command(name="desregistrar", description="Remove seu nick Minecraft do servidor (você pode registrar outro depois)")
async def desregistrar(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    regs = _carregar_registros()
    user_id = str(interaction.user.id)
    nick = regs.pop(user_id, None)
    if not nick:
        return await interaction.followup.send("ℹ️ Você não tinha nick registrado.", ephemeral=True)
    _salvar_registros(regs)
    _whitelist_remove(nick)
    try:
        send_command_to_minecraft(f"kick {nick} Voce se desregistrou")
    except Exception:
        pass
    await interaction.followup.send(
        f"🗑️ Nick `{nick}` removido da whitelist. Você pode registrar outro com `/registrar`.",
        ephemeral=True,
    )


@bot.tree.command(name="remover_acesso", description="(Admin) Remove o acesso de um usuário do Discord ao Minecraft")
@app_commands.describe(membro="Usuário do Discord que perderá o acesso")
async def remover_acesso(interaction: discord.Interaction, membro: discord.Member):
    await interaction.response.defer(thinking=True, ephemeral=True)
    if not has_permission(interaction):
        return await interaction.followup.send("⛔ Apenas o Heitor ou o pai podem usar este comando.", ephemeral=True)
    regs = _carregar_registros()
    nick = regs.pop(str(membro.id), None)
    if nick:
        _salvar_registros(regs)
        _whitelist_remove(nick)
        try:
            send_command_to_minecraft(f"kick {nick} Acesso removido por admin")
        except Exception:
            pass
    # Remove o cargo, se possível
    role = discord.utils.get(membro.guild.roles, name=MINECRAFT_ROLE_NAME)
    if role and role in membro.roles:
        try:
            await membro.remove_roles(role, reason="Acesso revogado via /remover_acesso")
        except discord.Forbidden:
            pass
    await interaction.followup.send(
        f"🚫 Acesso de {membro.mention} removido."
        + (f" Nick `{nick}` retirado da whitelist." if nick else ""),
        ephemeral=True,
    )

@bot.tree.command(name="estatisticas", description="Exibe estatísticas de um jogador")
@app_commands.describe(player_name="Nome do jogador (3-16 chars)")
async def estatisticas(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)
    role_required = "Operador do Nether"
    member = interaction.user
    if isinstance(member, discord.Member):
        if not any(role.name == role_required for role in member.roles):
            return await interaction.followup.send("⛔ Você não tem permissão para ver as estatísticas.")
    else:
        return await interaction.followup.send("⛔ Comando disponível apenas em servidores.")

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")

    stats = {}
    objetivos = {
        "playtime": "Tempo de Jogo",
        "jumps": "Pulos",
        "mortes": "Mortes",
        "kills": "Assassinatos (PvP)",
        "mobkills": "Abates (Mobs)"
    }

    for obj in objetivos:
        try:
            send_command_to_minecraft(f"scoreboard players get {player_name} {obj}")
            await asyncio.sleep(0.5)

            result = subprocess.run(
                ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-10'],
                capture_output=True, text=True, timeout=3
            )
            result.check_returncode()
            output = result.stdout.splitlines()

            for line in reversed(output):
                # Procura por "Heitor has 123 [objetivo]"
                match = re.search(rf"{re.escape(player_name)} has (\d+) \[{re.escape(obj)}\]", line)
                if match:
                    stats[obj] = int(match.group(1))
                    break
                # Também aceita "none is set" para não adicionar ao dict
                if "none is set" in line.lower() or "can't get value" in line.lower():
                    break
        except Exception as e:
            logging.warning(f"Erro ao tentar obter estatísticas de {player_name} para o objetivo {obj}: {str(e)}")
            continue

    if not stats:
        return await interaction.followup.send(f"❌ Não foi possível encontrar estatísticas para `{player_name}`.")

    # Converte ticks em minutos para playtime
    playtime_ticks = stats.get("playtime", 0)
    playtime_minutes = round(playtime_ticks / 1200, 2)

    msg = f"📋 **Estatísticas de `{player_name}`**\n"
    if "playtime" in stats:
        msg += f"🕒 {objetivos['playtime']}: {playtime_minutes} minutos\n"
    if "jumps" in stats:
        msg += f"🦘 {objetivos['jumps']}: {stats['jumps']}\n"
    if "mortes" in stats:
        msg += f"🩸 {objetivos['mortes']}: {stats['mortes']}\n"
    if "kills" in stats:
        msg += f"⚔️ {objetivos['kills']}: {stats['kills']}\n"
    if "mobkills" in stats:
        msg += f"🧟 {objetivos['mobkills']}: {stats['mobkills']}"

    await interaction.followup.send(msg)

@bot.tree.command(name="kick", description="Expulsa um jogador do servidor")
@app_commands.describe(player_name="Nome do jogador")
async def kick(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)
    if not has_permission(interaction):
        await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
        return

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        await interaction.followup.send("❌ Nome de jogador inválido.")
        return

    command = f"kick {player_name}"
    try:
        send_command_to_minecraft(command)
        await interaction.followup.send(f"👢 O jogador `{player_name}` foi expulso do servidor com sucesso.")
    except Exception as e:
        logging.error(f"Erro no comando kick: {e}")
        await interaction.followup.send(f"❌ Erro ao tentar expulsar o jogador: `{safe_error_message(e)}`")

@bot.tree.command(name="addplayer", description="Adiciona jogador e IP à whitelist personalizada")
@app_commands.describe(player_name="Nome do jogador", ip="Endereço IP (ex: 172.21.0.1)")
async def addplayer(interaction: discord.Interaction, player_name: str, ip: str):
    await interaction.response.defer(thinking=True)
    role_required = "Operador do Nether"
    member = interaction.user
    if isinstance(member, discord.Member):
        if not any(role.name == role_required for role in member.roles):
            await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
            return
    else:
        return await interaction.followup.send("⛔ Comando disponível apenas em servidores.")

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        await interaction.followup.send("❌ Nome de jogador inválido.")
        return

    # Validação do IP (formato + octetos 0-255)
    if not re.fullmatch(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        await interaction.followup.send("❌ Endereço IP inválido. Formato esperado: 0.0.0.0")
        return
    octets = ip.split(".")
    if not all(0 <= int(o) <= 255 for o in octets):
        await interaction.followup.send("❌ Endereço IP inválido. Cada octeto deve estar entre 0 e 255.")
        return

    file_path = "/minecraft/server/allowed_players.txt"
    player_entry = f"{player_name}:{ip}"

    try:
        # Verifica se o player já está na whitelist
        with open(file_path, "r") as f:
            lines = f.read().splitlines()
            if any(line.startswith(f"{player_name}:") for line in lines):
                await interaction.followup.send(f"⚠️ O jogador `{player_name}` já está na whitelist com IP `{ip}`.")
                return

        # Adiciona o player e IP ao arquivo
        with open(file_path, "a") as f:
            f.write(player_entry + "\n")

        await interaction.followup.send(f"✅ O jogador `{player_name}` com IP `{ip}` foi adicionado à whitelist com sucesso.")
    except Exception as e:
        logging.error(f"Erro no comando addplayer: {e}")
        await interaction.followup.send(f"❌ Ocorreu um erro ao tentar adicionar o jogador: `{safe_error_message(e)}`")

# User ID do Maydaz
def has_permission(interaction: discord.Interaction, user_id=678217602023292940):
    return interaction.user.id == user_id or interaction.user.id == 270987753640951808

@bot.tree.command(name="give", description="Dá um item ao jogador")
@app_commands.describe(player_name="Nome do jogador", item_name="Item (ex: minecraft:diamond)", amount_input="Quantidade (padrão 1)")
async def give(interaction: discord.Interaction, player_name: str, item_name: str, amount_input: str = "1"):
    await interaction.response.defer(thinking=True)
    if not has_permission(interaction):
        return await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")

    # Verifica se amount é um número inteiro positivo
    if not amount_input.isdigit():
        return await interaction.followup.send("❌ Quantidade inválida.")

    amount = int(amount_input)
    if amount <= 0:
        return await interaction.followup.send("❌ A quantidade deve ser maior que zero.")
    if amount > 6400:
        return await interaction.followup.send("❌ Quantidade máxima permitida: 6400.")

    # Valida nome do jogador
    if not is_valid_player_name(player_name):
        await interaction.followup.send("❌ Nome de jogador inválido.")
        return

    # Valida nome do item (previne injeção de comandos)
    if not is_valid_item_name(item_name):
        return await interaction.followup.send(
            "❌ Nome de item inválido. Use o formato `minecraft:nome_do_item` "
            "(apenas letras minúsculas, números e underscores)."
        )

    command = f"give {player_name} {item_name} {amount}"
    try:
        send_command_to_minecraft(command)
        await interaction.followup.send(f"🎁 O jogador `{player_name}` recebeu {amount} de `{item_name}`.")
    except Exception as e:
        logging.error(f"Erro no comando give: {e}")
        await interaction.followup.send(f"❌ Erro ao dar item: {safe_error_message(e)}")

# ──────────────────────────────────────────────
# Teleporte (custa 5 diamantes)
# ──────────────────────────────────────────────

@bot.tree.command(name="teleportar", description="Teleporta um jogador para coordenadas ou para o Nether (custa 5 diamantes)")
@app_commands.describe(
    player_name="Nome do jogador que será teleportado",
    destino="Coordenadas (x y z) ou 'nether' para ir ao Nether"
)
async def teleportar(interaction: discord.Interaction, player_name: str, destino: str):
    await interaction.response.defer(thinking=True)

    # Apenas quem tem a role ou o dono pode usar
    role_required = "Operador do Nether"
    member = interaction.user
    if isinstance(member, discord.Member):
        if not (any(role.name == role_required for role in member.roles) or has_permission(interaction)):
            return await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
    else:
        return await interaction.followup.send("⛔ Comando disponível apenas em servidores.")

    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")

    # Limita tamanho do destino para evitar abuso
    if len(destino) > 50:
        return await interaction.followup.send("❌ Destino muito longo.")

    # ── Determinar destino ANTES de cobrar (para não cobrar se o destino for inválido) ──
    destino_lower = destino.strip().lower()

    if destino_lower == "nether":
        # spreadplayers encontra um local seguro na superfície
        # "under 120" garante que fique abaixo do teto de bedrock do Nether (Y=128)
        tp_cmd = f"execute as {player_name} in minecraft:the_nether run spreadplayers 0 0 0 50 under 120 false @s"
        destino_display = "🔥 Nether (posição segura)"
    elif destino_lower == "end":
        # Plataforma de obsidian do End — sempre segura
        tp_cmd = f"execute as {player_name} in minecraft:the_end run tp @s 100 49 0"
        destino_display = "🌌 End (plataforma de obsidian)"
    elif destino_lower == "overworld":
        # spreadplayers no Overworld para posição segura na superfície
        tp_cmd = f"execute as {player_name} in minecraft:overworld run spreadplayers 0 0 0 50 false @s"
        destino_display = "🌍 Overworld (posição segura)"
    else:
        # Espera coordenadas x y z
        coords = destino.strip().split()
        if len(coords) != 3:
            return await interaction.followup.send(
                "❌ Destino inválido. Use coordenadas `x y z` ou uma dimensão: `nether`, `end`, `overworld`."
            )
        # Valida se são números (aceita negativos e ~)
        for c in coords:
            if c != "~" and not re.fullmatch(r"^~?-?\d+\.?\d*$", c):
                return await interaction.followup.send(f"❌ Coordenada inválida: `{c}`")
        tp_cmd = f"tp {player_name} {coords[0]} {coords[1]} {coords[2]}"
        destino_display = f"📍 ({coords[0]}, {coords[1]}, {coords[2]})"

    # ── Passo 1: Cobrar 5 diamantes e verificar se a cobrança foi completa ──
    clear_cmd = f"clear {player_name} minecraft:diamond 5"
    send_command_to_minecraft(clear_cmd)
    await asyncio.sleep(2.0)

    # Captura a saída do servidor para verificar quantos diamantes foram removidos
    diamonds_removed = 0
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-20'],
            capture_output=True, text=True, timeout=5
        )
        result.check_returncode()
        output = result.stdout

        for line in reversed(output.splitlines()):
            # Formato: "Removed 5 item(s) from player 19950512"
            match = re.search(r"[Rr]emoved\s+(\d+)\s+item", line)
            if match:
                diamonds_removed = int(match.group(1))
                logging.info(f"Teleporte: removidos {diamonds_removed} diamantes de {player_name}")
                break
            # Jogador não tem nenhum diamante
            if "No items were found" in line:
                diamonds_removed = 0
                break
    except Exception as e:
        logging.warning(f"Erro ao verificar pagamento de teleporte: {e}")
        return await interaction.followup.send(
            "❌ Não foi possível verificar o pagamento. Tente novamente."
        )

    # Se não removeu nenhum diamante
    if diamonds_removed == 0:
        return await interaction.followup.send(
            f"💎 O jogador `{player_name}` não possui **diamantes** para pagar o teleporte!"
        )

    # Se removeu menos de 5, devolve o que foi cobrado e cancela
    if diamonds_removed < 5:
        try:
            send_command_to_minecraft(f"give {player_name} minecraft:diamond {diamonds_removed}")
        except Exception:
            pass
        return await interaction.followup.send(
            f"💎 O jogador `{player_name}` tem apenas **{diamonds_removed} diamante(s)**. "
            f"São necessários **5** para teleportar!\n"
            f"🔄 Seus {diamonds_removed} diamante(s) foram devolvidos."
        )

    # ── Passo 2: Teleportar ──
    try:
        send_command_to_minecraft(tp_cmd)
        logging.info(f"Teleporte enviado: {tp_cmd}")
        await asyncio.sleep(0.5)
        await interaction.followup.send(
            f"✈️ `{player_name}` foi teleportado para {destino_display}\n"
            f"💎 Custo: **5 diamantes** (cobrados do inventário)"
        )
    except Exception as e:
        # Se o teleporte falha, devolve os diamantes
        logging.error(f"Erro no comando teleportar, devolvendo diamantes: {e}")
        try:
            send_command_to_minecraft(f"give {player_name} minecraft:diamond 5")
        except Exception:
            pass
        await interaction.followup.send(
            f"❌ Erro ao teleportar: {safe_error_message(e)}\n"
            f"💎 Seus 5 diamantes foram devolvidos."
        )


# ──────────────────────────────────────────────
# Helpers de permissão e cobrança em diamantes
# ──────────────────────────────────────────────

ROLE_OPERADOR = "Operador do Nether"


def tem_role_operador(interaction: discord.Interaction) -> bool:
    """True se o usuário é Operador do Nether OU é o dono (has_permission)."""
    member = interaction.user
    if has_permission(interaction):
        return True
    if isinstance(member, discord.Member):
        return any(role.name == ROLE_OPERADOR for role in member.roles)
    return False


async def cobrar_diamantes(player_name: str, quantidade: int) -> tuple[bool, int, str]:
    """Tenta remover ``quantidade`` diamantes do inventário do jogador.

    Retorna (sucesso, removidos, mensagem_erro). Em caso de removidos<quantidade,
    devolve o que foi cobrado antes de retornar.
    """
    try:
        send_command_to_minecraft(f"clear {player_name} minecraft:diamond {quantidade}")
        await asyncio.sleep(1.5)
        result = subprocess.run(
            ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-20'],
            capture_output=True, text=True, timeout=5,
        )
        result.check_returncode()
        removidos = 0
        for line in reversed(result.stdout.splitlines()):
            m = re.search(r"[Rr]emoved\s+(\d+)\s+item", line)
            if m:
                removidos = int(m.group(1))
                break
            if "No items were found" in line:
                removidos = 0
                break
    except Exception as e:
        logging.warning(f"Falha ao cobrar diamantes de {player_name}: {e}")
        return False, 0, "❌ Não foi possível verificar o pagamento. Tente novamente."

    if removidos == 0:
        return False, 0, f"💎 `{player_name}` não tem **nenhum diamante** no inventário!"
    if removidos < quantidade:
        # devolve o que foi cobrado
        try:
            send_command_to_minecraft(f"give {player_name} minecraft:diamond {removidos}")
        except Exception:
            pass
        return (
            False,
            removidos,
            f"💎 `{player_name}` tem só **{removidos} diamante(s)**, precisa de **{quantidade}**. "
            f"Devolvi o que cobrei. 🔄",
        )
    return True, removidos, ""


# ──────────────────────────────────────────────
# Comandos divertidos (para todos)
# ──────────────────────────────────────────────

SAUDACOES = [
    "Oiêêê, {user}! 👋 Bora minerar?",
    "Eaí {user}! 🎮 Pega a picareta e vem!",
    "Salveeee {user}! ⚒️ Que bom te ver no servidor do Heitor!",
    "{user}, você é demais! 💚 Bom jogo!",
    "Oi {user}! 🐷🐮 Os bichinhos estão te esperando!",
]

PIADAS = [
    ("Por que o Creeper não usa elevador?", "Porque ele sempre **explode** no caminho! 💥"),
    ("O que o zumbi disse ao Steve?", "Para de me **assustar**, eu acabei de acordar! 🧟"),
    ("Como o Enderman atende o telefone?", "**Teleporta** e diz alô! 📞"),
    ("O que a vaca do Minecraft come?", "Bloco de **rações**! 🐄"),
    ("Por que o esqueleto não foi à festa?", "Porque ele não tinha **corpo** pra ir! 💀"),
    ("Qual o lanche favorito do Steve?", "Um **bloco** de queijo! 🧀"),
    ("Por que o porco virou bacon?", "Porque caiu um **raio** nele! ⚡🐖"),
    ("O que o Aldeão disse pro outro?", "**Hmmmm!** 🧑\u200d🌾"),
    ("Por que o lobo é amigo do Steve?", "Porque ele deu um **osso** de presente! 🦴🐺"),
    ("Qual o bloco mais educado?", "O **TNT**, porque sempre se **apresenta** com estrondo! 🧨"),
]


@bot.tree.command(name="oi", description="Receba uma saudação fofa do bot")
async def oi(interaction: discord.Interaction):
    nome = interaction.user.display_name
    msg = random.choice(SAUDACOES).format(user=nome)
    await interaction.response.send_message(msg)


@bot.tree.command(name="piada", description="Conta uma piada infantil de Minecraft")
async def piada(interaction: discord.Interaction):
    pergunta, resposta = random.choice(PIADAS)
    embed = discord.Embed(title="😂 Piada do Maynecraft", color=0xFFD700)
    embed.add_field(name="🤔 " + pergunta, value="||" + resposta + "||", inline=False)
    embed.set_footer(text="Clique no borrão pra ver a resposta!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="dado", description="Rola um dado")
@app_commands.describe(lados="Número de lados do dado (2-100, padrão 6)")
async def dado(interaction: discord.Interaction, lados: int = 6):
    if lados < 2 or lados > 100:
        return await interaction.response.send_message("❌ O dado precisa ter entre 2 e 100 lados.")
    valor = random.randint(1, lados)
    await interaction.response.send_message(
        f"🎲 {interaction.user.display_name} rolou um **D{lados}** e tirou **{valor}**!"
    )


@bot.tree.command(name="ranking", description="Top 3 jogadores em tempo de jogo")
async def ranking(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        # Lista jogadores online + offline na whitelist
        nomes = set()
        try:
            with open("/minecraft/server/allowed_players.txt") as f:
                for linha in f:
                    n = linha.split(":")[0].strip()
                    if n and is_valid_player_name(n):
                        nomes.add(n)
        except FileNotFoundError:
            pass
        if not nomes:
            return await interaction.followup.send("❌ Nenhum jogador na whitelist ainda.")

        stats = []
        for nome in nomes:
            try:
                send_command_to_minecraft(f"scoreboard players get {nome} playtime")
                await asyncio.sleep(0.4)
                result = subprocess.run(
                    ['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-10'],
                    capture_output=True, text=True, timeout=3,
                )
                output = result.stdout.splitlines()
                for line in reversed(output):
                    m = re.search(rf"{re.escape(nome)} has (\d+) \[playtime\]", line)
                    if m:
                        stats.append((nome, int(m.group(1))))
                        break
            except Exception:
                continue

        if not stats:
            return await interaction.followup.send("❌ Nenhuma estatística encontrada ainda. Joguem mais! 🎮")

        stats.sort(key=lambda x: x[1], reverse=True)
        medalhas = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="🏆 Top jogadores — Tempo de jogo", color=0xFFD700)
        for i, (nome, ticks) in enumerate(stats[:3]):
            minutos = round(ticks / 1200, 1)
            embed.add_field(
                name=f"{medalhas[i]} {nome}",
                value=f"{minutos} minutos jogados",
                inline=False,
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logging.error(f"Erro no ranking: {e}")
        await interaction.followup.send(f"❌ Erro no ranking: {safe_error_message(e)}")


@bot.tree.command(name="conversar", description="Manda recado pro chat do jogo")
@app_commands.describe(mensagem="Mensagem para aparecer no chat in-game")
async def conversar(interaction: discord.Interaction, mensagem: str):
    autor = sanitize_for_minecraft(interaction.user.display_name)[:20] or "Discord"
    texto = sanitize_for_minecraft(mensagem)[:200]
    if not texto:
        return await interaction.response.send_message("❌ Mensagem vazia após filtragem.")
    tellraw = (
        f'tellraw @a ["",'
        f'{{"text":"[Discord] ","color":"aqua","bold":true}},'
        f'{{"text":"{autor}","color":"yellow"}},'
        f'{{"text":": ","color":"white"}},'
        f'{{"text":"{texto}","color":"white"}}]'
    )
    try:
        send_command_to_minecraft(tellraw)
        await interaction.response.send_message(f"💬 Enviado pro chat: *{texto}*")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {safe_error_message(e)}")


# ──────────────────────────────────────────────
# Comandos de Clima e Tempo (Operador)
# ──────────────────────────────────────────────

async def _comando_simples_op(interaction: discord.Interaction, comando_mc: str, mensagem_ok: str):
    await interaction.response.defer(thinking=True)
    if not tem_role_operador(interaction):
        return await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
    try:
        send_command_to_minecraft(comando_mc)
        await interaction.followup.send(mensagem_ok)
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


@bot.tree.command(name="dia", description="Faz nascer o sol no servidor 🌞")
async def dia(interaction: discord.Interaction):
    await _comando_simples_op(interaction, "time set day", "🌞 O sol nasceu! Bom dia, Maynecraft!")


@bot.tree.command(name="noite", description="Cai a noite no servidor 🌙")
async def noite(interaction: discord.Interaction):
    await _comando_simples_op(interaction, "time set night", "🌙 A noite chegou... cuidado com os monstros!")


@bot.tree.command(name="sol", description="Limpa o tempo (sem chuva) ☀️")
async def sol(interaction: discord.Interaction):
    await _comando_simples_op(interaction, "weather clear", "☀️ Tempo limpo! Dia perfeito pra construir!")


@bot.tree.command(name="chuva", description="Faz chover no servidor 🌧️")
async def chuva(interaction: discord.Interaction):
    await _comando_simples_op(interaction, "weather rain", "🌧️ Está chovendo! Hora de pegar uma capa!")


@bot.tree.command(name="anunciar", description="Anuncia uma mensagem no servidor")
@app_commands.describe(mensagem="Mensagem para anunciar a todos")
async def anunciar(interaction: discord.Interaction, mensagem: str):
    await interaction.response.defer(thinking=True)
    if not tem_role_operador(interaction):
        return await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
    texto = sanitize_for_minecraft(mensagem)[:200]
    if not texto:
        return await interaction.followup.send("❌ Mensagem vazia após filtragem.")
    tellraw = f'tellraw @a [{{"text":"📢 ","color":"gold","bold":true}},{{"text":"{texto}","color":"yellow"}}]'
    try:
        send_command_to_minecraft(tellraw)
        await interaction.followup.send(f"📢 Anunciado: *{texto}*")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


# ──────────────────────────────────────────────
# Magias (custam diamantes)
# ──────────────────────────────────────────────

@bot.tree.command(name="curar", description="Cura o jogador (custa 2 diamantes)")
@app_commands.describe(player_name="Jogador que será curado")
async def curar(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")
    ok, _, erro = await cobrar_diamantes(player_name, 2)
    if not ok:
        return await interaction.followup.send(erro)
    try:
        send_command_to_minecraft(f"effect give {player_name} minecraft:instant_health 1 5 true")
        send_command_to_minecraft(f"effect give {player_name} minecraft:saturation 5 5 true")
        send_command_to_minecraft(
            f'tellraw {player_name} [{{"text":"💖 Você foi curado! Vida e fome cheias!","color":"light_purple"}}]'
        )
        await interaction.followup.send(f"💖 `{player_name}` foi curado completamente! (2 💎)")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


@bot.tree.command(name="voar", description="Habilita voo por 3 minutos (custa 3 diamantes)")
@app_commands.describe(player_name="Jogador que ganhará o voo")
async def voar(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")
    ok, _, erro = await cobrar_diamantes(player_name, 3)
    if not ok:
        return await interaction.followup.send(erro)
    try:
        # levitation dura 180s (3 min); slow_falling pra não morrer ao acabar
        send_command_to_minecraft(f"effect give {player_name} minecraft:levitation 180 1 true")
        send_command_to_minecraft(f"effect give {player_name} minecraft:slow_falling 200 0 true")
        send_command_to_minecraft(
            f'tellraw {player_name} [{{"text":"🪽 Você pode voar por 3 minutos!","color":"aqua"}}]'
        )
        await interaction.followup.send(f"🪽 `{player_name}` está flutuando! (3 💎)")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


EFEITOS_DISPONIVEIS = {
    "forca": ("minecraft:strength", 60, 1, "💪 Força máxima!"),
    "velocidade": ("minecraft:speed", 120, 2, "💨 Super veloz!"),
    "invisivel": ("minecraft:invisibility", 60, 0, "👻 Invisível!"),
    "saltar": ("minecraft:jump_boost", 120, 2, "🦘 Pula alto!"),
    "respiracao": ("minecraft:water_breathing", 180, 0, "🐟 Respira na água!"),
    "noturna": ("minecraft:night_vision", 300, 0, "🌃 Visão noturna!"),
    "fogo": ("minecraft:fire_resistance", 120, 0, "🔥 Imune ao fogo!"),
}


@bot.tree.command(name="efeito", description="Aplica um efeito mágico (custa 2 diamantes)")
@app_commands.describe(
    player_name="Jogador",
    efeito="Tipo de efeito",
)
@app_commands.choices(efeito=[
    app_commands.Choice(name="💪 Força", value="forca"),
    app_commands.Choice(name="💨 Velocidade", value="velocidade"),
    app_commands.Choice(name="👻 Invisível", value="invisivel"),
    app_commands.Choice(name="🦘 Saltar alto", value="saltar"),
    app_commands.Choice(name="🐟 Respirar água", value="respiracao"),
    app_commands.Choice(name="🌃 Visão noturna", value="noturna"),
    app_commands.Choice(name="🔥 Imune ao fogo", value="fogo"),
])
async def efeito(interaction: discord.Interaction, player_name: str, efeito: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")
    if efeito.value not in EFEITOS_DISPONIVEIS:
        return await interaction.followup.send("❌ Efeito desconhecido.")
    ok, _, erro = await cobrar_diamantes(player_name, 2)
    if not ok:
        return await interaction.followup.send(erro)
    mc_id, duracao, nivel, mensagem = EFEITOS_DISPONIVEIS[efeito.value]
    try:
        send_command_to_minecraft(f"effect give {player_name} {mc_id} {duracao} {nivel} true")
        send_command_to_minecraft(
            f'tellraw {player_name} [{{"text":"✨ {mensagem}","color":"light_purple"}}]'
        )
        await interaction.followup.send(
            f"✨ `{player_name}` recebeu **{efeito.name}** por {duracao}s! (2 💎)"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


MASCOTES = {
    "lobo": ("minecraft:wolf", "{Tame:1b,CollarColor:14}", "🐺 Um lobinho dócil aparece!"),
    "gato": ("minecraft:cat", "{Tame:1b}", "🐱 Um gatinho ronrona perto de você!"),
    "papagaio": ("minecraft:parrot", "{Tame:1b,Variant:0}", "🦜 Um papagaio colorido pousa no seu ombro!"),
    "cavalo": ("minecraft:horse", "{Tame:1b,SaddleItem:{id:\"minecraft:saddle\",Count:1b}}", "🐴 Um cavalo selado aparece!"),
    "raposa": ("minecraft:fox", "{Trusted:[I;0,0,0,0]}", "🦊 Uma raposinha bondosa aparece!"),
}


@bot.tree.command(name="mascote", description="Invoca um bichinho dócil (custa 5 diamantes)")
@app_commands.describe(player_name="Dono do bichinho", tipo="Tipo de bichinho")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🐺 Lobo", value="lobo"),
    app_commands.Choice(name="🐱 Gato", value="gato"),
    app_commands.Choice(name="🦜 Papagaio", value="papagaio"),
    app_commands.Choice(name="🐴 Cavalo", value="cavalo"),
    app_commands.Choice(name="🦊 Raposa", value="raposa"),
])
async def mascote(interaction: discord.Interaction, player_name: str, tipo: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")
    if tipo.value not in MASCOTES:
        return await interaction.followup.send("❌ Bichinho desconhecido.")
    ok, _, erro = await cobrar_diamantes(player_name, 5)
    if not ok:
        return await interaction.followup.send(erro)
    mob_id, nbt, mensagem = MASCOTES[tipo.value]
    try:
        send_command_to_minecraft(
            f"execute at {player_name} run summon {mob_id} ~ ~ ~ {nbt}"
        )
        send_command_to_minecraft(
            f'tellraw {player_name} [{{"text":"{mensagem}","color":"green"}}]'
        )
        await interaction.followup.send(
            f"🐾 Um(a) **{tipo.name}** apareceu pertinho de `{player_name}`! (5 💎)"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


@bot.tree.command(name="foguete", description="Lança um foguetão no jogador (custa 1 diamante)")
@app_commands.describe(player_name="Jogador a ser lançado")
async def foguete(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)
    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")
    ok, _, erro = await cobrar_diamantes(player_name, 1)
    if not ok:
        return await interaction.followup.send(erro)
    try:
        # slow_falling impede dano da queda; impulso vertical
        send_command_to_minecraft(f"effect give {player_name} minecraft:slow_falling 30 0 true")
        await asyncio.sleep(0.2)
        # aplica motion via tag NBT (funciona em 1.20+)
        send_command_to_minecraft(f"data merge entity {player_name} {{Motion:[0.0,3.0,0.0]}}")
        send_command_to_minecraft(
            f'tellraw {player_name} [{{"text":"🚀 LÁ VAI VOCÊ!","color":"red","bold":true}}]'
        )
        await interaction.followup.send(f"🚀 `{player_name}` foi lançado pro céu! (1 💎)")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro: {safe_error_message(e)}")


# ──────────────────────────────────────────────
# Kit Inicial (itens de recomeço após morrer)
# ──────────────────────────────────────────────

KIT_INICIAL = [
    # Armadura de diamante
    ("minecraft:diamond_helmet", 1),
    ("minecraft:diamond_chestplate", 1),
    ("minecraft:diamond_leggings", 1),
    ("minecraft:diamond_boots", 1),
    # Ferramentas
    ("minecraft:diamond_pickaxe", 1),
    ("minecraft:diamond_axe", 1),
    ("minecraft:diamond_shovel", 1),
    ("minecraft:diamond_sword", 1),
    # Escudo
    ("minecraft:shield", 1),
    # Comida
    ("minecraft:cooked_beef", 64),
    ("minecraft:cooked_beef", 36),
    # Tochas
    ("minecraft:torch", 64),
    # Barco
    ("minecraft:oak_boat", 1),
    # Extras úteis
    ("minecraft:red_bed", 1),
    ("minecraft:crafting_table", 1),
    ("minecraft:furnace", 1),
    ("minecraft:bed", 1),
    ("minecraft:bucket", 1),
]

@bot.tree.command(name="kit_inicial", description="Dá o kit completo de recomeço a um jogador (após morrer)")
@app_commands.describe(player_name="Nome do jogador que receberá o kit")
async def kit_inicial(interaction: discord.Interaction, player_name: str):
    await interaction.response.defer(thinking=True)

    # Permissão: role ou dono
    role_required = "Operador do Nether"
    member = interaction.user
    if isinstance(member, discord.Member):
        if not (any(role.name == role_required for role in member.roles) or has_permission(interaction)):
            return await interaction.followup.send("⛔ Você não tem permissão para usar este comando.")
    else:
        return await interaction.followup.send("⛔ Comando disponível apenas em servidores.")

    if not is_valid_player_name(player_name):
        return await interaction.followup.send("❌ Nome de jogador inválido.")

    erros = []
    for item, qty in KIT_INICIAL:
        try:
            send_command_to_minecraft(f"give {player_name} {item} {qty}")
            await asyncio.sleep(0.3)  # Pequeno delay para não sobrecarregar
        except Exception as e:
            erros.append(f"{item}: {e}")

    if erros:
        await interaction.followup.send(
            f"⚠️ Kit entregue a `{player_name}` com alguns erros:\n"
            + "\n".join(f"  • {err}" for err in erros)
        )
    else:
        itens_msg = "\n".join(f"  • {qty}× `{item}`" for item, qty in KIT_INICIAL)
        await interaction.followup.send(
            f"🎒 **Kit Inicial entregue a `{player_name}`!**\n\n"
            f"{itens_msg}\n\n"
            f"Bom recomeço! 💪"
        )


# Inicia o bot com o token
bot.run(DISCORD_TOKEN)
