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
    send_command_to_minecraft(f"kick {player_name}")
    await ctx.send(f"👢 {player_name} foi expulso do servidor.")

@bot.command()
async def give(ctx, player_name: str, item_name: str, amount: int = 1):
    # Comando para dar um item ao jogador
    send_command_to_minecraft(f"give {player_name} {item_name} {amount}")
    await ctx.send(f"🎁 {amount}x {item_name} foi dado a {player_name}.")

# Comando para banir um jogador
@bot.command()
async def ban(ctx, player_name: str):
    send_command_to_minecraft(f"ban {player_name}")
    await ctx.send(f"🔨 {player_name} foi banido do servidor.")

# Comando para teleportar um jogador
@bot.command()
async def tp(ctx, player_name: str, target_name: str):
    send_command_to_minecraft(f"tp {player_name} {target_name}")
    await ctx.send(f"🧭 {player_name} foi teleportado para {target_name}.")

# Comando para mudar o modo de jogo
@bot.command()
async def gamemode(ctx, player_name: str, mode: str):
    send_command_to_minecraft(f"gamemode {mode} {player_name}")
    await ctx.send(f"🎮 {player_name} agora está em modo {mode}.")

# Comando simples de teste
@bot.command()
async def hello(ctx):
    await ctx.send('🌍 Hello, world!')

# Inicia o bot
bot.run(DISCORD_TOKEN)  # Usa o token do .env
