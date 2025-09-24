#!/usr/bin/env bash
set -e
STAMP=$(date +%F_%H-%M)
mkdir -p backup
echo "🗄️  Dumping PostgreSQL..."
docker exec telegram_bot_db_prod pg_dump -U bot_user telegram_bot \
  | gzip > backup/db_$STAMP.sql.gz
echo "📦 Archiving Redis dump..."
docker exec telegram_bot_redis_prod redis-cli save
docker cp telegram_bot_redis_prod:/data/dump.rdb backup/redis_$STAMP.rdb
echo "✅ Backup ready in backup/"
