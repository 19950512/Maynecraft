import discord
from discord.ext import commands
import subprocess
import asyncio
from dotenv import load_dotenv
import os

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém o token e a sessão do tmux a partir do .env
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TMUX_SESSION = os.getenv("TMUX_SESSION", "minecraft")  # Valor padrão 'minecraft' caso não esteja no .env

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def send_command_to_minecraft(cmd):
    subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, cmd, 'Enter'])

async def get_last_output_from_minecraft():
    # Captura as últimas 100 linhas do pane do tmux
    result = subprocess.run(['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-100'],
                            capture_output=True, text=True)
    output = result.stdout.splitlines()

    # Procura pela última linha que contenha "There are" ou "Jogadores"
    for line in reversed(output):
        if "There are" in line or "Jogadores conectados" in line or "players" in line:
            return line.strip()
    return "❌ Não foi possível encontrar a saída do comando."

@bot.command()
async def players(ctx):
    send_command_to_minecraft("list")
    await asyncio.sleep(1.5)  # Pequeno delay para o servidor responder
    response = await get_last_output_from_minecraft()
    await ctx.send(f"👥 {response}")

@bot.command()
async def estatisticas(ctx, player_name: str):
    
    role_required = "Operador do Nether"
    if not any(role.name == role_required for role in ctx.author.roles):
        return await ctx.send("⛔ Você não tem permissão para ver o ranking.")

    stats = {}
    objetivos = {
        "mortes": "Mortes",
        "kills": "Assassinatos",
        "mobkills": "Abates",
        "playtime": "Tempo de Jogo",
        "jumps": "Pulos",
        "joins": "Saídas"
    }

    for obj in objetivos:
        send_command_to_minecraft(f"scoreboard players get {player_name} {obj}")
        await asyncio.sleep(0.5)  # pequena pausa entre comandos

        result = subprocess.run(['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-10'],
                                capture_output=True, text=True)
        output = result.stdout.splitlines()

        for line in reversed(output):
            if f"{player_name} has" in line or f"{player_name} has" in line:
                parts = line.split("has")
                if len(parts) > 1:
                    value = ''.join(filter(str.isdigit, parts[1]))
                    stats[obj] = int(value) if value else 0
                    break

    if not stats:
        return await ctx.send(f"❌ Não foi possível encontrar estatísticas para `{player_name}`.")

    # Converte tempo de jogo (ticks) para minutos
    playtime_ticks = stats.get("playtime", 0)
    playtime_minutes = round(playtime_ticks / 1200, 2)

    msg = f"📋 **Estatísticas de `{player_name}`**\n"
    msg += f"🩸 Mortes: {stats.get('mortes', 0)}\n"
    msg += f"⚔️ Assassinatos (PvP): {stats.get('kills', 0)}\n"
    msg += f"🧟 Abates (Mobs): {stats.get('mobkills', 0)}\n"
    msg += f"🕒 Tempo de jogo: {playtime_minutes} minutos\n"
    msg += f"🦘 Pulos: {stats.get('jumps', 0)}\n"
    msg += f"🚪 Saídas do servidor: {stats.get('joins', 0)}"

    await ctx.send(msg)

# Comando para kickar um jogador
@bot.command()
async def kick(ctx, player_name: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    send_command_to_minecraft(f"kick {player_name}")
    await ctx.send(f"👢 {player_name} foi expulso do servidor.")

objective_labels = {
    "mortes": "Mortes",
    "kills": "Assassinatos",
    "mobkills": "Abates",
    "playtime": "Tempo de Jogo",
    "jumps": "Pulos",
    "joins": "Saídas"
}

@bot.command()
async def rank(ctx, objetivo: str):
    if objetivo not in objective_labels:
        return await ctx.send(f"❌ Objetivo inválido. Escolha um: {', '.join(objective_labels.keys())}")

    role_required = "Operador do Nether"
    if not any(role.name == role_required for role in ctx.author.roles):
        return await ctx.send("⛔ Você não tem permissão para ver o ranking.")

    send_command_to_minecraft(f"scoreboard objectives setdisplay sidebar {objetivo}")
    await asyncio.sleep(2)

    result = subprocess.run(['tmux', 'capture-pane', '-t', TMUX_SESSION, '-p', '-S', '-30'],
                            capture_output=True, text=True)
    output = result.stdout.splitlines()

    lines = [line for line in output if " - " in line and any(char.isdigit() for char in line)]
    if not lines:
        return await ctx.send("❌ Não foi possível obter o ranking.")

    ranking = []
    for line in lines:
        try:
            parts = line.split("INFO]:")[-1].strip()
            if " - " in parts:
                value, name = parts.split(" - ")
                ranking.append((int(value.strip()), name.strip()))
        except:
            continue

    ranking.sort(reverse=True)

    msg = f"📊 **Ranking de {objective_labels[objetivo]}**\n"
    for i, (value, name) in enumerate(ranking, 1):
        msg += f"{i}. {name} — {value}\n"

    await ctx.send(msg)

@bot.command()
async def addplayer(ctx, player_name: str):
    role_required = "Operador do Nether"

    # Verifica se o autor tem o cargo necessário
    if any(role.name == role_required for role in ctx.author.roles):
        file_path = "/opt/minecraft/src/allowed_players.txt"
        try:
            # Verifica se o player já está na whitelist
            with open(file_path, "r") as f:
                lines = f.read().splitlines()
                if player_name in lines:
                    await ctx.send(f"⚠️ O jogador `{player_name}` já está na whitelist.")
                    return

            # Adiciona o player ao arquivo
            with open(file_path, "a") as f:
                f.write(player_name + "\n")

            await ctx.send(f"✅ O jogador `{player_name}` foi adicionado à whitelist com sucesso.")
        except Exception as e:
            await ctx.send(f"❌ Ocorreu um erro ao tentar adicionar o jogador: {e}")
    else:
        await ctx.send("⛔ Você não tem permissão para usar este comando.")

# User ID do Maydaz
def has_permission(ctx, user_id=678217602023292940):
    return ctx.author.id == user_id

@bot.command()
async def give(ctx, player_name: str, item_name: str, amount: int = 1):
    if not has_permission(ctx):
        return await ctx.send("⛔ Você não tem permissão para usar este comando.")

    send_command_to_minecraft(f"give {player_name} {item_name} {amount}")
    await ctx.send(f"🎁 {amount}x {item_name} foi dado a {player_name}.")

# Comando para banir um jogador
@bot.command()
async def ban(ctx, player_name: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    send_command_to_minecraft(f"ban {player_name}")
    await ctx.send(f"🔨 {player_name} foi banido do servidor.")

# Comando para teleportar um jogador
@bot.command()
async def tp(ctx, player_name: str, target_name: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    send_command_to_minecraft(f"tp {player_name} {target_name}")
    await ctx.send(f"🧭 {player_name} foi teleportado para {target_name}.")

# Comando para mudar o modo de jogo
@bot.command()
async def gamemode(ctx, player_name: str, mode: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    send_command_to_minecraft(f"gamemode {mode} {player_name}")
    await ctx.send(f"🎮 {player_name} agora está em modo {mode}.")

# Inicia o bot
bot.run(DISCORD_TOKEN)  # Usa o token do .env
