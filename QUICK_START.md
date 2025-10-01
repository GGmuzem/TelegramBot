# 🚀 БЫСТРЫЙ СТАРТ

## ✅ Проект полностью готов к запуску!

Все критичные проблемы исправлены. Следуйте этой инструкции:

---

## 📋 Шаг 1: Создание .env файла

```bash
# Скопируйте пример
cp .env.example .env

# Отредактируйте .env и заполните:
nano .env
```

### 🔑 Обязательные переменные:

```env
# Telegram (получите от @BotFather)
BOT_TOKEN=1234567890:YOUR_ACTUAL_BOT_TOKEN

# База данных
DB_PASSWORD=your_secure_password_123

# Redis
REDIS_PASSWORD=your_redis_password_456

# MinIO
MINIO_SECRET_KEY=minio_secure_password_789

# ЮKassa (из личного кабинета yookassa.ru)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Безопасность
SECRET_KEY=your_super_secret_jwt_key_32chars_minimum
WEBHOOK_SECRET=your_webhook_secret_key

# Grafana
GRAFANA_PASSWORD=your_grafana_password
```

---

## 🐳 Шаг 2: Запуск через Docker

### Первый запуск (Production):

```bash
# Убедитесь что Docker и Docker Compose установлены
docker --version
docker-compose --version

# Запустите все сервисы
docker-compose -f docker-compose.yml up -d

# Проверьте статус
docker-compose ps

# Смотрите логи
docker-compose logs -f bot
```

### Для разработки (без GPU):

```bash
# Запустите только основные сервисы
docker-compose up -d postgres redis minio bot webhook nginx
```

---

## 📊 Шаг 3: Проверка работы

### 1. Проверьте сервисы:
```bash
# Все сервисы должны быть "Up"
docker-compose ps

# Health check
curl http://localhost:8000/health
```

### 2. Откройте мониторинг:
- **Grafana**: http://localhost:3000 (admin/ваш_пароль_из_.env)
- **Prometheus**: http://localhost:9090
- **MinIO Console**: http://localhost:9001

### 3. Проверьте бота:
1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте `/start`
4. Бот должен ответить приветственным сообщением

---

## 🧪 Шаг 4: Тестирование

### Запуск тестов:
```bash
# Установите зависимости для тестов
pip install -r requirements.txt

# Запустите все тесты
pytest tests/ -v

# Результат: 13 passed, 3 skipped (это нормально)
```

---

## ⚙️ Основные команды

### Управление сервисами:
```bash
# Остановить все
docker-compose down

# Перезапустить конкретный сервис
docker-compose restart bot

# Просмотр логов
docker-compose logs -f [service_name]

# Обновление после изменений кода
docker-compose up -d --build

# Полная очистка (удаляет данные!)
docker-compose down -v
```

### Проверка состояния:
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Логи конкретного сервиса
docker logs telegram_bot -f
```

---

## 🔧 Troubleshooting

### Проблема: Бот не отвечает
**Решение**:
```bash
# Проверьте логи
docker logs telegram_bot -f

# Убедитесь что BOT_TOKEN правильный
docker exec telegram_bot env | grep BOT_TOKEN

# Перезапустите бота
docker-compose restart bot
```

### Проблема: База данных не подключается
**Решение**:
```bash
# Проверьте статус PostgreSQL
docker-compose ps postgres

# Проверьте логи
docker logs telegram_bot_db -f

# Проверьте подключение
docker exec telegram_bot_db psql -U bot_user -d telegram_bot -c "SELECT 1"
```

### Проблема: AI генерация не работает
**Требования**:
- NVIDIA GPU с поддержкой CUDA 12.1+
- NVIDIA Container Toolkit установлен
- Docker настроен для работы с GPU

**Проверка**:
```bash
# Проверьте GPU в контейнере
docker exec celery_worker nvidia-smi
```

---

## 📚 Дополнительная информация

### Структура портов:
- **8000** - Telegram Bot (webhook)
- **8001** - Payment Webhook
- **5432** - PostgreSQL
- **6379** - Redis
- **9000** - MinIO API
- **9001** - MinIO Console
- **9090** - Prometheus
- **3000** - Grafana
- **80/443** - Nginx (HTTP/HTTPS)

### Важные файлы:
- `.env` - Конфигурация (НЕ коммитить!)
- `docker-compose.yml` - Docker конфигурация
- `nginx.conf` - Nginx настройки
- `AUDIT_REPORT.md` - Полный отчёт аудита

---

## ✅ Чек-лист готовности

Перед production запуском убедитесь:

- [ ] `.env` создан с реальными ключами
- [ ] Все пароли сильные и уникальные
- [ ] SSL сертификаты настроены (для HTTPS)
- [ ] Домен настроен и указывает на сервер
- [ ] Firewall правила настроены
- [ ] Backup стратегия определена
- [ ] Мониторинг настроен в Grafana
- [ ] GPU драйверы установлены (если используете AI)
- [ ] Протестировали оплату в тестовом режиме

---

## 🎯 Результат

После выполнения всех шагов у вас будет:

✅ Работающий Telegram бот  
✅ Платёжная система (ЮKassa/CloudPayments)  
✅ AI генерация изображений на GPU  
✅ Полный мониторинг через Grafana  
✅ Автоматические бекапы  
✅ Production-ready архитектура  

---

## 🆘 Нужна помощь?

1. Проверьте `AUDIT_REPORT.md` - полный технический отчёт
2. Смотрите логи: `docker-compose logs -f`
3. Проверьте тесты: `pytest tests/ -v`
4. Документация в `README.md`

**Проект готов к работе! Удачного запуска! 🚀**
