#!/usr/bin/env python3
"""
create_structure.py
Создаёт директории Telegram-AI-Bot проекта и добавляет __init__.py во все Python-пакеты.
"""

import os
from pathlib import Path

# Корневые каталоги (относительно места запуска)
ROOT_DIRS = [
    "logs/bot", "logs/generator", "logs/webhook", "logs/nginx",
    "data/postgres", "data/redis", "data/minio", "data/prometheus", "data/grafana",
    "backup", "models", "ssl", "static",
    "scripts", "monitoring/grafana/dashboards", "monitoring/grafana/provisioning/datasources"
]

# Деревья исходного кода
SRC_DIRS = [
    # bot
    "src/bot/handlers",
    "src/bot/keyboards",
    "src/bot/middlewares",
    "src/bot/webapp/templates",
    "src/bot/webapp/static",
    # payment
    "src/payment/providers",
    # generator
    "src/generator",
    # database
    "src/database/migrations",
    # storage
    "src/storage",
    # shared
    "src/shared",
]

# Тесты
TEST_DIRS = ["tests"]


def create_dirs(dirs):
    """Рекурсивно создаёт каталоги."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def touch_init_files():
    """Создаёт пустой __init__.py во всех каталогах src."""
    for path in Path("src").rglob("*"):
        if path.is_dir():
            init_file = path / "__init__.py"
            init_file.touch(exist_ok=True)


def main():
    print("📁  Создание структуры каталогов…")
    create_dirs(ROOT_DIRS + SRC_DIRS + TEST_DIRS)
    touch_init_files()
    print("✅  Структура проекта готова!")


if __name__ == "__main__":
    main()
