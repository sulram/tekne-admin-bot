# Deploy no Dokploy

## Arquitetura de Persistência

O projeto usa **Redis** como única fonte de persistência:
- ✅ **Agent memory** (conversas do Agno) - persiste através de `RedisDb`
- ✅ **Cost tracking** (custos de API) - operações atômicas com `HINCRBY`

Redis usa **AOF (Append-Only File)** para durabilidade:
- Dados são salvos em `/data` dentro do container Redis
- Volume `redis-data` é criado automaticamente pelo docker-compose
- Configuração: `appendonly yes --appendfsync everysec`
- Persiste **automaticamente** entre deploys

**Não precisa criar volumes manualmente!** O `redis-data` é gerenciado pelo Docker Compose.

## Verificar volumes

```bash
# Listar volumes
docker volume ls | grep redis

# Deve mostrar:
# - redis-data (criado automaticamente)
```

## Acessar dados Redis

Para verificar os dados persistidos:

```bash
# Entrar no container Redis
docker exec -it tekne-redis redis-cli

# Ver todas as chaves
KEYS *

# Ver custo total
HGETALL cost:total

# Ver sessões
KEYS cost:session:*

# Ver custos diários
KEYS cost:daily:*

# Exemplo: ver custo de hoje
HGETALL cost:daily:2026-01-02
```

## Backup Redis

```bash
# Backup automático (AOF está sempre salvando)
# Para backup manual:
docker exec tekne-redis redis-cli BGSAVE

# Copiar dump.rdb para host
docker cp tekne-redis:/data/dump.rdb ./redis-backup.rdb

# Restaurar (parar container, copiar arquivo, iniciar container)
docker stop tekne-redis
docker cp ./redis-backup.rdb tekne-redis:/data/dump.rdb
docker start tekne-redis
```

## Resetar dados

```bash
# Resetar APENAS cost tracking (via bot)
# Use o comando /cost no Telegram e escolha "Reset"

# Resetar Redis completamente
docker exec tekne-redis redis-cli FLUSHDB

# Resetar volumes completamente (CUIDADO!)
docker compose down -v
docker volume rm redis-data
docker compose up -d
```

## Monitorar Redis

```bash
# Ver info do Redis
docker exec tekne-redis redis-cli INFO

# Monitorar comandos em tempo real
docker exec tekne-redis redis-cli MONITOR

# Ver uso de memória
docker exec tekne-redis redis-cli INFO memory
```
