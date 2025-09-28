from celery import Celery
from src.shared.config import settings

# Для Celery будем использовать отдельные базы данных в Redis
celery_broker_url = settings.REDIS_URL.replace('/0', '/1')
celery_backend_url = settings.REDIS_URL.replace('/0', '/2')

celery_app = Celery(
    "telegram_ai_bot",
    broker=celery_broker_url,
    backend=celery_backend_url,
    include=["src.generator.tasks"]  # Путь к модулю с задачами
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    worker_concurrency=3,  # Количество одновременных задач (можно настроить по числу GPU)
    worker_prefetch_multiplier=1, # Воркер берет по одной задаче за раз
    task_acks_late=True,  # Подтверждение выполнения после завершения задачи
)

if __name__ == "__main__":
    celery_app.start()
