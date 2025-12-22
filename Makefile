.PHONY: help build up down restart logs status clean backup console stop-old

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

stop-old: ## Para serviços antigos (não-Docker) e libera a porta
	@echo "🛑 Parando serviços antigos..."
	@sudo systemctl stop minecraft-bot minecraft-discord minecraft-check-players 2>/dev/null || true
	@tmux kill-session -t minecraft 2>/dev/null || true
	@sudo pkill -f "java.*server.*jar" 2>/dev/null || true
	@sleep 1
	@if sudo lsof -i :25565 >/dev/null 2>&1; then \
		echo "⚠️  Porta 25565 ainda em uso. Forçando..."; \
		sudo lsof -ti :25565 | xargs sudo kill -9 2>/dev/null || true; \
	fi
	@echo "✅ Porta 25565 liberada!"

build: ## Constrói as imagens Docker
	docker compose build

up: stop-old ## Inicia os containers
	docker compose up -d
	@echo "✅ Containers iniciados!"
	@make status

down: ## Para os containers
	docker compose down
	@echo "✅ Containers parados!"

restart: ## Reinicia os containers
	docker compose restart
	@echo "✅ Containers reiniciados!"

logs: ## Mostra logs dos containers
	docker compose logs -f

logs-minecraft: ## Mostra apenas logs do Minecraft
	docker compose logs -f minecraft

logs-bot: ## Mostra logs do bot dentro do container
	@echo "Mostrando /minecraft/logs/bot.log (Ctrl+C para sair)"
	docker exec -it minecraft-server tail -n +1 -f /minecraft/logs/bot.log || \
	  (echo "Arquivo de log não encontrado. Verifique se o bot está rodando." && exit 1)

status: ## Mostra status dos containers
	@docker compose ps

clean: ## Remove containers, volumes e dados (CUIDADO!)
	@echo "⚠️  Isso vai remover TODOS os dados do servidor!"
	@read -p "Tem certeza? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		rm -rf server-data backups logs; \
		echo "✅ Limpeza completa!"; \
	fi

backup: ## Executa backup manual
	docker exec minecraft-server /minecraft/venv/bin/python3 /minecraft/backup.py
	@echo "✅ Backup executado!"

console: ## Acessa o console do Minecraft
	@echo "Para sair: Ctrl+B e depois D"
	@sleep 2
	docker exec -it minecraft-server tmux attach -t minecraft

shell: ## Acessa shell do container
	docker exec -it minecraft-server /bin/bash

install: ## Instala Docker e Docker Compose
	@./iniciar-docker.sh

rebuild: ## Reconstrói e reinicia tudo
	docker compose down
	docker compose build --no-cache
	docker compose up -d
	@echo "✅ Reconstruído com sucesso!"

update: ## Atualiza e reinicia os containers
	git pull
	@make rebuild
