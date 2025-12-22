#!/bin/bash

# Script para iniciar o servidor Minecraft com Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐳 Iniciando Minecraft Server com Docker..."

# Verifica se o Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Docker não encontrado. Instalando..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker instalado. Por favor, faça logout e login novamente."
    exit 0
fi

# Verifica se o Docker Compose está instalado (plugin V2)
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose V2 não encontrado. Instalando..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    echo "✅ Docker Compose V2 instalado."
fi

# Verifica se o arquivo .env existe
if [ ! -f ".env" ]; then
    echo "❌ Arquivo .env não encontrado!"
    echo "📝 Copie o arquivo env-exemplo para .env e configure:"
    echo "   cp env-exemplo .env"
    exit 1
fi

# Cria diretórios necessários
echo "📂 Criando diretórios..."
mkdir -p server-data backups logs

# Constrói e inicia os containers
echo "🔨 Construindo imagens Docker..."
docker compose build

echo "🚀 Iniciando containers..."
docker compose up -d

echo "⏳ Aguardando containers iniciarem..."
sleep 5

# Mostra status
echo ""
echo "✅ Servidor iniciado!"
echo ""
echo "📊 Status dos containers:"
docker compose ps

echo ""
echo "📋 Comandos úteis:"
echo "  Ver logs:              docker compose logs -f"
echo "  Parar servidor:        docker compose down"
echo "  Reiniciar:             docker compose restart"
echo "  Acessar console:       docker exec -it minecraft-server tmux attach -t minecraft"
echo ""
echo "🌐 O servidor está rodando na porta 25565"
