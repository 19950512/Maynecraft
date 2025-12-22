# Configurações do Servidor Minecraft (template)

Arquivos desta pasta são templates para `/minecraft/server`. Ajuste aqui e depois suba o servidor (Docker cuida de copiar/usar as configs montadas em `server-data/`).

## server.properties (principais campos)

- `online-mode` (true/false)
  - true: exige autenticação oficial da Mojang (mais seguro, precisa de conta paga)
  - false: modo offline/LAN (permite qualquer nome, ideal para testes/lan-house)
- `whitelist` (true/false)
  - true: só entra quem está na whitelist
  - false: qualquer jogador pode entrar
- `whitelist-names` (lista, separado por vírgula)
  - Ex.: `whitelist-names=fodska,Heitor,Amigo1`
  - Na subida do container, é gerado automaticamente o `whitelist.json` a partir desta lista (UUID offline é calculado para cada nome)
  - Se vazio, não altera o `whitelist.json`
- `max-players` (número)
  - Limite de jogadores simultâneos
- `motd`
  - Mensagem exibida na lista de servidores
- `server-name`
  - Nome interno do servidor
- `difficulty` (peaceful/easy/normal/hard)
  - Dificuldade do mundo

## Como funciona a whitelist automática
1. Edite `configs/server.properties` (ou `server-data/server.properties`) e preencha `whitelist-names` com os nomes separados por vírgula.
2. Certifique-se que `whitelist=true`.
3. Ao iniciar o container, o entrypoint:
   - Lê `whitelist-names`
   - Gera `whitelist.json` com UUIDs offline (compatível com `online-mode=false`)
   - Garante `whitelist=true` no `server.properties`

## Fluxo recomendado
- Ajuste `configs/server.properties` conforme necessidade.
- Suba com `make up` ou `docker compose up -d`.
- Os arquivos efetivos ficarão em `server-data/` (volume persistente). Se já existir `server-data/server.properties`, ele é usado; caso contrário, use o template de `configs/`.

## Dicas rápidas
- Para jogar com contas oficiais e impedir nomes falsos: `online-mode=true` e mantenha a whitelist se quiser controle.
- Para lan party/offline: `online-mode=false` e use `whitelist-names` para limitar quem entra.
- Sempre reinicie o servidor após alterar `server.properties`.
