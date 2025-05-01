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

# Comando para kickar um jogador
@bot.command()
async def kick(ctx, player_name: str):
    if not has_permission(ctx):
        await ctx.send("⛔ Você não tem permissão para usar este comando.")
        return

    send_command_to_minecraft(f"kick {player_name}")
    await ctx.send(f"👢 {player_name} foi expulso do servidor.")

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

def has_permission(ctx, role_name="Arquimago Supremo do Código e do Caos"):
    return any(role.name == role_name for role in ctx.author.roles)

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
