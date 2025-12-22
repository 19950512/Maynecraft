import re
import html
import discord
from discord.ext import commands
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

intents = discord.Intents.default()
intents.message_content = True

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

# Configuração de logging
logging.basicConfig(level=logging.INFO)

def send_command_to_minecraft(cmd):
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
        await interaction.followup.send(f"❌ Erro ao tentar obter a lista de jogadores: {str(e)}")

@bot.tree.command(name="comandos", description="Lista os comandos disponíveis")
async def comandos(interaction: discord.Interaction):
    msg = (
        "**📜 Lista de Comandos Disponíveis**\n\n"
        "**👥 Informações de Jogadores**\n"
        "`/players` — Mostra os jogadores online\n"
        "`/estatisticas <jogador>` — Exibe estatísticas detalhadas\n"
        "**🔧 Administração (Operador do Nether)**\n"
        "`/addplayer <jogador> <ip>` — Adiciona jogador à whitelist (nome:ip)\n"
        "`/kick <jogador>` — Expulsa jogador\n"
        "`/give <jogador> <item> [quantidade]` — Dá item ao jogador\n"
    )
    await interaction.response.send_message(msg)

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
        await interaction.followup.send(f"❌ Erro ao tentar expulsar o jogador: `{str(e)}`")

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

    # Validação do IP
    if not re.fullmatch(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        await interaction.followup.send("❌ Endereço IP inválido. Formato esperado: 0.0.0.0")
        return

    # Sanitização de entradas
    player_name = html.escape(player_name)
    ip = html.escape(ip)

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
        await interaction.followup.send(f"❌ Ocorreu um erro ao tentar adicionar o jogador: `{str(e)}`")

# User ID do Maydaz
def has_permission(interaction: discord.Interaction, user_id=678217602023292940):
    return interaction.user.id == user_id

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

    # Valida nome do jogador
    if not is_valid_player_name(player_name):
        await interaction.followup.send("❌ Nome de jogador inválido.")
        return

    command = f"give {player_name} {item_name} {amount}"
    try:
        send_command_to_minecraft(command)
        await interaction.followup.send(f"🎁 O jogador `{player_name}` recebeu {amount} de {item_name}.")
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao dar item: {str(e)}")

# Inicia o bot com o token
bot.run(DISCORD_TOKEN)
