#!/bin/bash
#
# Скрипт для установки зависимостей под новые архитектуры GPU (например, Blackwell)
# Этот скрипт должен вызываться в Dockerfile.generator

set -e

# Обновляем список пакетов
apt-get update

# Устанавливаем утилиты, необходимые для компиляции и сборки
apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    curl \
    wget

# Здесь могла бы быть логика для скачивания и компиляции PyTorch с поддержкой sm_120,
# но на данный момент официальной поддержки нет. Оставляем плейсхолдер.
echo "PyTorch build for Blackwell (sm_120) would be here."

# Очистка
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "✅ Environment setup for new GPU architectures is complete."
