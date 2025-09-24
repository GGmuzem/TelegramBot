#!/usr/bin/env bash
# Настройка окружения CUDA для RTX 5080
set -e
echo "🔧 Проверка NVIDIA драйвера..."
nvidia-smi || { echo "❌ GPU не обнаружена"; exit 1; }
echo "✅ GPU OK  — $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "⚙️  Установка переменных окружения..."
echo 'export CUDA_VISIBLE_DEVICES=0,1,2' >> ~/.bashrc
echo 'export HF_HUB_DISABLE_TELEMETRY=1' >> ~/.bashrc
echo "🎉 RTX 5080 готова!"
