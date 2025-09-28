import logging
import json
from src.shared.celery_app import celery_app
from src.generator.models_manager import model_manager
from src.generator.gpu_balancer import gpu_balancer
from src.storage.minio_client import minio_client
from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_image_task(self, task_data: str):
    """Celery задача для генерации изображения"""
    try:
        task = json.loads(task_data)
        logger.info(f"Processing task: {task['task_id']}")

        gpu_id = gpu_balancer.get_available_gpu(priority=task["priority"])
        if gpu_id is None:
            logger.warning("No available GPU, retrying task...")
            raise self.retry()

        img_bytes = model_manager.generate_image(
            gpu_id=gpu_id,
            prompt=task["prompt"],
            style=task["style"],
            quality=task["quality"],
            size=task["size"]
        )

        if img_bytes:
            filename = f"{task['task_id']}.jpg"
            url = minio_client.upload_bytes(img_bytes, filename)
            logger.info(f"Image for task {task['task_id']} saved to {url}")
            
            # Публикуем результат в очередь для бота
            result_data = {
                "user_id": task['user_id'],
                "chat_id": task['chat_id'],
                "message_id": task['message_id'],
                "prompt": task['prompt'],
                "image_url": url
            }
            redis_client.sync_redis.lpush("results_queue", json.dumps(result_data))
            
            return {"status": "completed", "url": url}
        else:
            gpu_balancer.mark_gpu_error(gpu_id, "generation failed")
            logger.error(f"Image generation failed for task {task['task_id']}")
            raise Exception("Image generation failed")

    except Exception as e:
        logger.error(f"Error in generate_image_task: {e}")
        # В случае ошибки Celery автоматически повторит попытку (max_retries=3)
        raise self.retry(exc=e)
