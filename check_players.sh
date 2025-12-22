#!/bin/bash

# As variáveis de ambiente já vêm do docker-compose.yml
WEBHOOK_URL="$DISCORD_WEBHOOK_URL"

SESSION_NAME="minecraft"
SERVER_DIR="/minecraft/server"
ALLOWED_PLAYERS_FILE="$SERVER_DIR/allowed_players.txt"
TMP_PLAYER_IPS="/tmp/current_players_ips.txt"
LAST_BLOCKED_FILE="/tmp/last_blocked_players.txt"

mkdir -p /tmp
> "$TMP_PLAYER_IPS"
> "$LAST_BLOCKED_FILE"

if [ ! -f "$ALLOWED_PLAYERS_FILE" ]; then
    echo "❌ Arquivo de jogadores permitidos não encontrado. Criando novo arquivo..."
    touch "$ALLOWED_PLAYERS_FILE"
    echo "⚠️ Lista vazia criada. Todos os jogadores serão bloqueados até que sejam adicionados."
fi

send_discord_log() {
    local player="$1"
    local ip="$2"
    local motivo="$3"

    # Verificar se já foi enviado uma mensagem para o mesmo jogador nos últimos 5 minutos
    last_blocked_time=$(grep "^$player:" "$LAST_BLOCKED_FILE" | cut -d':' -f2)
    current_time=$(date +%s)
    if [ -z "$last_blocked_time" ] || [ $((current_time - last_blocked_time)) -gt 300 ]; then
        # Se não foi enviado ou o tempo foi maior que 5 minutos, envia a notificação
        json=$(cat <<EOF
{
  "embeds": [{
    "title": "🚫 Jogador bloqueado",
    "color": 16711680,
    "fields": [
      { "name": "Jogador", "value": "$player", "inline": true },
      { "name": "IP", "value": "$ip", "inline": true },
      { "name": "Motivo", "value": "$motivo" }
    ]
  }]
}
EOF
)
        curl -s -X POST -H "Content-Type: application/json" -d "$json" "$WEBHOOK_URL" > /dev/null

        # Atualiza o tempo da última notificação para este jogador
        echo "$player:$current_time" > "$LAST_BLOCKED_FILE"
    fi
}

# Limpar entradas antigas de IPs no cache (mais de 1 hora, 3600 segundos)
clean_old_cache() {
    current_time=$(date +%s)
    temp_file=$(mktemp)

    while read player ip timestamp; do
        if [ $((current_time - timestamp)) -lt 3600 ]; then
            echo "$player $ip $timestamp" >> "$temp_file"
        fi
    done < "$TMP_PLAYER_IPS"

    mv "$temp_file" "$TMP_PLAYER_IPS"
}

check_players() {
    tail -F "$SERVER_DIR/logs/latest.log" 2>/dev/null | while read line; do
        echo "Linha do log: $line"  # Depuração: Mostra a linha do log sendo processada

        # Verifica se a linha contém a informação de que um jogador se conectou
        if echo "$line" | grep -q "logged in with entity id"; then
            # Extrai o nome do jogador (antes do colchete)
            player=$(echo "$line" | grep -oP '\[Server thread/INFO\]: \K[^[]+(?=\[)')

            # Extrai o IP do jogador (entre / e :)
            ip=$(echo "$line" | grep -oP '\[/\K[0-9.]+(?=:)')

            echo "Jogador: $player, IP: $ip"  # Depuração: Mostra o jogador e o IP extraído

            # Verifica se o nome do jogador e o IP foram extraídos corretamente
            if [ -n "$player" ] && [ -n "$ip" ]; then
                timestamp=$(date +%s)  # Marca o tempo do IP
                echo "$player $ip $timestamp" >> "$TMP_PLAYER_IPS"  # Armazena no arquivo temporário
            else
                echo "Erro: Jogador ou IP não encontrados na linha do log."
            fi
        fi

        # Verifica quando um jogador entrou no jogo
        if echo "$line" | grep -q "joined the game"; then
            # Extrai o nome do jogador que entrou no jogo
            player=$(echo "$line" | grep -oP '\[Server thread/INFO\]: \K[^ ]+(?= joined the game)')

            # Encontra o IP correspondente ao jogador
            ip=$(grep "^$player " "$TMP_PLAYER_IPS" | awk '{print $2}' | tail -n 1)

            # Encontra o timestamp do IP correspondente
            timestamp=$(grep "^$player " "$TMP_PLAYER_IPS" | awk '{print $3}' | tail -n 1)

            echo "Verificando jogador: $player, IP: $ip"  # Depuração: Mostra o jogador e o IP

            # Verifica se o jogador está na lista de permitidos
            linha=$(grep "^$player:" "$ALLOWED_PLAYERS_FILE")
            if [ -z "$linha" ]; then
                echo "⚠️ Jogador $player não está na whitelist. Kickando..."
                tmux send-keys -t "$SESSION_NAME" "kick $player Jogador não permitido" C-m
                send_discord_log "$player" "$ip" "Não está na whitelist"
            else
                # Verifica se o IP corresponde ao permitido
                allowed_ip=$(echo "$linha" | cut -d':' -f2)
                
                # Se IP for "any", aceita e atualiza com o IP real
                if [ "$allowed_ip" = "any" ]; then
                    echo "✅ Primeira conexão de $player, registrando IP: $ip"
                    sed -i "s/^$player:any$/$player:$ip/" "$ALLOWED_PLAYERS_FILE"
                elif [ "$ip" != "$allowed_ip" ]; then
                    echo "⚠️ IP diferente para $player. Kickando..."
                    tmux send-keys -t "$SESSION_NAME" "kick $player IP não autorizado" C-m
                    send_discord_log "$player" "$ip" "IP não autorizado (esperado: $allowed_ip)"
                fi
            fi
        fi
    done
}


# Rodar a limpeza do cache de IPs a cada 15 minutos
clean_old_cache

while true; do
    check_players
    clean_old_cache
    sleep 1
done
