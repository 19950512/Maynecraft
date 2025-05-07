import re
import html
import discord
from discord.ext import commands
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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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

@bot.command()
async def players(ctx):
    try:
        send_command_to_minecraft("list")
        await asyncio.sleep(1.5)  # Pequeno delay para o servidor responder
        response = await get_last_output_from_minecraft()
        if response:
            await ctx.send(f"👥 {response}")
        else:
            await ctx.send("❌ Não foi possível obter a lista de jogadores.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao tentar obter a lista de jogadores: {str(e)}")

@bot.command()
async def comandos(ctx):
    msg = (
        "**📜 Lista de Comandos Disponíveis**\n\n"
        "**👥 Informações de Jogadores**\n"
        "`!players` — Mostra os jogadores online\n"
        "`!estatisticas <jogador>` — Exibe estatísticas detalhadas\n"
        "**🔧 Administração (Operador do Nether)**\n"
        "`!addplayer <jogador>` — Adiciona jogador à whitelist\n"
    )

    await ctx.send(msg)

@bot.command()
async def estatisticas(ctx, player_name: str):
    role_required = "Operador do Nether"
    if not any(role.name == role_required for role in ctx.author.roles):
        return await ctx.send("⛔ Você não tem permissão para ver as estatísticas.")

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        return await ctx.send("❌ Nome de jogador inválido.")

    stats = {}
    objetivos = {
        "mortes": "Mortes",
        "kills": "Assassinatos (PvP)",
        "mobkills": "Abates (Mobs)",
        "playtime": "Tempo de Jogo",
        "jumps": "Pulos",
        "joins": "Entradas no servidor"
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
                match = re.search(rf"{re.escape(player_name)} has (\d+)", line)
                if match:
                    stats[obj] = int(match.group(1))
                    break
        except Exception as e:
            logging.warning(f"Erro ao tentar obter estatísticas de {player_name} para o objetivo {obj}: {str(e)}")
            continue  # Se falhar um objetivo, ignora e segue

    if not stats:
        return await ctx.send(f"❌ Não foi possível encontrar estatísticas para `{player_name}`.")

    # Converte ticks em minutos
    playtime_ticks = stats.get("playtime", 0)
    playtime_minutes = round(playtime_ticks / 1200, 2)

    msg = f"📋 **Estatísticas de `{player_name}`**\n"
    msg += f"🩸 {objetivos['mortes']}: {stats.get('mortes', 0)}\n"
    msg += f"⚔️ {objetivos['kills']}: {stats.get('kills', 0)}\n"
    msg += f"🧟 {objetivos['mobkills']}: {stats.get('mobkills', 0)}\n"
    msg += f"🕒 {objetivos['playtime']}: {playtime_minutes} minutos\n"
    msg += f"🦘 {objetivos['jumps']}: {stats.get('jumps', 0)}\n"
    msg += f"🚪 {objetivos['joins']}: {stats.get('joins', 0)}"

    await ctx.send(msg)

@bot.command()
async def kick(ctx, player_name: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        await ctx.send("❌ Nome de jogador inválido.")
        return

    command = f"kick {player_name}"
    try:
        send_command_to_minecraft(command)
        await ctx.send(f"👢 O jogador `{player_name}` foi expulso do servidor com sucesso.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao tentar expulsar o jogador: `{str(e)}`")

@bot.command()
async def addplayer(ctx, player_name: str, ip: str):
    role_required = "Operador do Nether"

    if not any(role.name == role_required for role in ctx.author.roles):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    # Validação do nome do jogador
    if not is_valid_player_name(player_name):
        await ctx.send("❌ Nome de jogador inválido.")
        return

    # Validação do IP
    if not re.fullmatch(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        await ctx.send("❌ Endereço IP inválido. Formato esperado: 0.0.0.0")
        return

    # Sanitização de entradas
    player_name = html.escape(player_name)
    ip = html.escape(ip)

    file_path = "/opt/minecraft/src/allowed_players.txt"
    player_entry = f"{player_name}:{ip}"

    try:
        # Verifica se o player já está na whitelist
        with open(file_path, "r") as f:
            lines = f.read().splitlines()
            if any(line.startswith(f"{player_name}:") for line in lines):
                await ctx.send(f"⚠️ O jogador `{player_name}` já está na whitelist com IP `{ip}`.")
                return

        # Adiciona o player e IP ao arquivo
        with open(file_path, "a") as f:
            f.write(player_entry + "\n")

        await ctx.send(f"✅ O jogador `{player_name}` com IP `{ip}` foi adicionado à whitelist com sucesso.")
    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro ao tentar adicionar o jogador: `{str(e)}`")

# User ID do Maydaz
def has_permission(ctx, user_id=678217602023292940):
    return ctx.author.id == user_id

@bot.command()
async def give(ctx, player_name: str, item_name: str, amount_input: str = "1"):
    if not has_permission(ctx):
        return await ctx.send("⛔ Você não tem permissão para usar este comando.")

    # Verifica se amount é um número inteiro positivo
    if not amount_input.isdigit():
        return await ctx.send("❌ Quantidade inválida.")

    amount = int(amount_input)
    if amount <= 0:
        return await ctx.send("❌ A quantidade deve ser maior que zero.")

    # Valida nome do jogador
    if not is_valid_player_name(player_name):
        await ctx.send("❌ Nome de jogador inválido.")
        return

    command = f"give {player_name} {item_name} {amount}"
    try:
        send_command_to_minecraft(command)
        await ctx.send(f"🎁 O jogador `{player_name}` recebeu {amount} de {item_name}.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao dar item: {str(e)}")

# Inicia o bot com o token
bot.run(DISCORD_TOKEN)
