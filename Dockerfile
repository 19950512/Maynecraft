FROM eclipse-temurin:21-jdk

# Instala dependências
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    wget \
    curl \
    cron \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Cria diretórios
RUN mkdir -p /minecraft/server \
    /minecraft/backups \
    /minecraft/logs \
    /minecraft/bot

# Cria ambiente virtual Python
RUN python3 -m venv /minecraft/venv

# Instala pacotes Python
RUN /minecraft/venv/bin/pip install --upgrade pip && \
    /minecraft/venv/bin/pip install discord.py python-dotenv requests boto3

# Define diretório de trabalho
WORKDIR /minecraft

# Copia configs (templates)
COPY configs/ /minecraft/configs/

# Copia scripts
COPY bot.py /minecraft/bot/
COPY backup.py /minecraft/
COPY check_players.sh /minecraft/
COPY monitorar_logs.sh /minecraft/

# Torna scripts executáveis
RUN chmod +x /minecraft/*.sh

# Copia script de inicialização
COPY docker-entrypoint.sh /minecraft/
RUN dos2unix /minecraft/docker-entrypoint.sh /minecraft/*.sh && \
    chmod +x /minecraft/docker-entrypoint.sh

# Expõe portas do Minecraft
EXPOSE 25565

# Volume para persistência de dados
VOLUME ["/minecraft/server", "/minecraft/backups"]

ENTRYPOINT ["/minecraft/docker-entrypoint.sh"]
