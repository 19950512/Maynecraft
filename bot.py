import re
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
    msg = (
        "**📜 Lista de Comandos Disponíveis**\n\n"
        "**👥 Informações de Jogadores**\n"
        "`/players` — Mostra os jogadores online\n"
        "`/estatisticas <jogador>` — Exibe estatísticas detalhadas\n\n"
        "**✈️ Teleporte (custa 💎 5 diamantes)**\n"
        "`/teleportar <jogador> <destino>` — Teleporta jogador\n"
        "  • Destino pode ser: coordenadas `x y z`, `nether`, `end` ou `overworld`\n\n"
        "**🎒 Kit**\n"
        "`/kit_inicial <jogador>` — Entrega kit completo para recomeçar após morrer\n\n"
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
