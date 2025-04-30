#!/usr/bin/env python3

import os
import tarfile
import datetime
import boto3
from botocore.client import Config
from dotenv import load_dotenv
import requests

# Carrega variáveis do .env
load_dotenv()

# CONFIGURAÇÕES
MINECRAFT_DIR = os.getenv("MINECRAFT_DIR", "/opt/minecraft/src")  # Usando a variável do .env, com fallback
TMUX_SESSION = os.getenv("TMUX_SESSION", "minecraft")  # Usando a variável do .env
BACKUP_DIR = os.getenv("BACKUP_DIR", "/opt/minecraft/backups")  # Usando a variável do .env
FILES_TO_BACKUP = ["world", "world_nether", "world_the_end", "server.properties", "ops.json", "whitelist.json"]

# Cloudflare R2 - lidas do .env
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

MAX_BACKUPS = 5  # Número máximo de backups a serem mantidos

def clean_old_backups():
    # Lista os backups existentes no diretório
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".tar.gz")]
    backups.sort(reverse=True)  # Ordena de forma decrescente pela data de criação

    # Verifica se há mais de MAX_BACKUPS backups
    if len(backups) > MAX_BACKUPS:
        # Exclui os backups antigos (mantendo apenas os mais recentes)
        backups_to_remove = backups[MAX_BACKUPS:]
        for backup in backups_to_remove:
            backup_path = os.path.join(BACKUP_DIR, backup)
            os.remove(backup_path)
            print(f"❌ Backup antigo removido: {backup}")

def run_tmux_command(command):
    os.system(f'tmux send-keys -t {TMUX_SESSION} "{command}" Enter')

def create_backup():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"minecraft_backup_{timestamp}.tar.gz"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    with tarfile.open(backup_path, "w:gz") as tar:
        for item in FILES_TO_BACKUP:
            path = os.path.join(MINECRAFT_DIR, item)
            if os.path.exists(path):
                tar.add(path, arcname=item)
    
    return backup_name, backup_path

def send_discord_message(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Webhook do Discord não configurado.")
        return
    payload = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao enviar mensagem para o Discord: {e}")

def upload_to_r2(file_name, file_path):
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        endpoint_url=R2_ENDPOINT_URL,
        config=Config(signature_version='s3v4')
    )

    s3.upload_file(file_path, R2_BUCKET_NAME, file_name)

    # Gera URL pública com validade de 7 dias (604800 segundos)
    url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': R2_BUCKET_NAME, 'Key': file_name},
        ExpiresIn=604800
    )
    return url

def main():
    print("📦 Salvando mundo no tmux...")
    run_tmux_command("save-all")
    run_tmux_command("save-off")

    print("📁 Criando backup...")
    file_name, file_path = create_backup()

    print("☁️ Enviando para Cloudflare R2...")
    download_url = upload_to_r2(file_name, file_path)

    # Limpeza dos backups antigos
    print("🧹 Limpando backups antigos...")
    clean_old_backups()

    print("✅ Reativando salvamento automático...")
    run_tmux_command("save-on")

    success_message = f"✅ Backup Minecraft finalizado com sucesso!\n🔗 Link válido por 7 dias:\n{download_url}"
    print(success_message)
    send_discord_message(success_message)


if __name__ == "__main__":
    main()