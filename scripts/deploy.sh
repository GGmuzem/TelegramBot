#!/bin/bash

# Скрипт деплоя Telegram AI Bot
# Использование: ./deploy.sh [development|production]

set -e

ENVIRONMENT=${1:-development}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "🚀 Деплой Telegram AI Bot в режиме: $ENVIRONMENT"

# Проверяем наличие необходимых файлов
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Скопируйте .env.example в .env и настройте переменные окружения"
    exit 1
fi

if [ ! -d "ssl" ]; then
    echo "⚠️ Папка ssl не найдена. Создаем SSL сертификаты..."
    mkdir -p ssl
    ./scripts/init_ssl.sh localhost
fi

# Создаем необходимые директории
echo "📁 Создание директорий..."
mkdir -p logs/{nginx,bot,webhook,generator}
mkdir -p data/{postgres,redis,minio,prometheus,grafana}
mkdir -p backup
mkdir -p models
mkdir -p static

# Устанавливаем права доступа
echo "🔒 Настройка прав доступа..."
chmod -R 755 data/
chmod -R 755 logs/
chmod 600 ssl/key.pem 2>/dev/null || true
chmod 644 ssl/cert.pem 2>/dev/null || true

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    exit 1
fi

# Останавливаем существующие контейнеры
echo "🛑 Остановка существующих сервисов..."
if [ "$ENVIRONMENT" == "production" ]; then
    docker-compose -f docker-compose.prod.yml down --remove-orphans || true
else
    docker-compose down --remove-orphans || true
fi

# Очищаем Docker кеш
echo "🧹 Очистка Docker кеша..."
docker system prune -f

# Пересобираем образы
echo "🔨 Сборка Docker образов..."
if [ "$ENVIRONMENT" == "production" ]; then
    docker-compose -f docker-compose.prod.yml build --no-cache
else
    docker-compose build --no-cache
fi

# Проверяем RTX 5080 и CUDA
echo "🔍 Проверка GPU..."
if command -v nvidia-smi &> /dev/null; then
    echo "GPU статус:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
else
    echo "⚠️ NVIDIA драйверы не обнаружены"
fi

# Запускаем сервисы
echo "▶️ Запуск сервисов..."
if [ "$ENVIRONMENT" == "production" ]; then
    docker-compose -f docker-compose.prod.yml up -d
else
    docker-compose up -d
fi

# Ожидаем запуска сервисов
echo "⏳ Ожидание запуска сервисов..."
sleep 30

# Проверяем статус сервисов
echo "✅ Проверка статуса сервисов..."
if [ "$ENVIRONMENT" == "production" ]; then
    docker-compose -f docker-compose.prod.yml ps
else
    docker-compose ps
fi

# Health checks
echo "🏥 Проверка работоспособности..."

# Проверяем базу данных
echo "Проверка PostgreSQL..."
docker exec telegram_bot_db$([ "$ENVIRONMENT" == "production" ] && echo "_prod") pg_isready -U bot_user || echo "⚠️ PostgreSQL недоступен"

# Проверяем Redis
echo "Проверка Redis..."
docker exec telegram_bot_redis$([ "$ENVIRONMENT" == "production" ] && echo "_prod") redis-cli ping || echo "⚠️ Redis недоступен"

# Проверяем MinIO
echo "Проверка MinIO..."
curl -f http://localhost:9000/minio/health/live || echo "⚠️ MinIO недоступен"

# Проверяем Nginx
echo "Проверка Nginx..."
curl -f http://localhost/health || echo "⚠️ Nginx недоступен"

# Инициализация базы данных
echo "🗄️ Инициализация базы данных..."
sleep 10
docker exec telegram_bot$([ "$ENVIRONMENT" == "production" ] && echo "_prod") python -c "
import asyncio
from database_crud import init_database
asyncio.run(init_database())
print('База данных инициализирована')
" || echo "⚠️ Ошибка инициализации БД"

# Загружаем AI модели
echo "🤖 Проверка AI моделей..."
if [ ! -f "models/.models_downloaded" ]; then
    echo "Загружаем AI модели (это может занять время)..."
    docker exec ai_generator$([ "$ENVIRONMENT" == "production" ] && echo "_prod") python -c "
from ai_generator_service import ModelManager
import asyncio
async def download_models():
    manager = ModelManager()
    await manager.load_models_on_gpus()
    print('Модели загружены')
try:
    asyncio.run(download_models())
except Exception as e:
    print(f'Ошибка загрузки моделей: {e}')
" && touch models/.models_downloaded
fi

echo ""
echo "🎉 Деплой завершен!"
echo ""
echo "📋 Информация о сервисах:"
echo "• Telegram Bot: http://localhost:8000"
echo "• Payment Webhook: http://localhost:8001"
echo "• MinIO Console: http://localhost:9001"
echo "• Prometheus: http://localhost:9090"
echo "• Grafana: http://localhost:3000 (admin/$(grep GRAFANA_PASSWORD .env | cut -d'=' -f2))"
echo ""
echo "📊 Мониторинг:"
if [ "$ENVIRONMENT" == "production" ]; then
    echo "docker-compose -f docker-compose.prod.yml logs -f"
else
    echo "docker-compose logs -f"
fi
echo ""
echo "🛑 Остановка:"
if [ "$ENVIRONMENT" == "production" ]; then
    echo "docker-compose -f docker-compose.prod.yml down"
else
    echo "docker-compose down"
fi
echo ""
echo "🔍 Для просмотра логов конкретного сервиса:"
echo "docker logs -f <container_name>"

# Создаем systemd сервис для автозапуска (опционально)
if [ "$ENVIRONMENT" == "production" ] && command -v systemctl &> /dev/null; then
    read -p "Создать systemd сервис для автозапуска? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo tee /etc/systemd/system/telegram-ai-bot.service > /dev/null <<EOF
[Unit]
Description=Telegram AI Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
        sudo systemctl daemon-reload
        sudo systemctl enable telegram-ai-bot.service
        echo "✅ Systemd сервис создан и включен"
    fi
fi
