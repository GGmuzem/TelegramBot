import asyncio, logging, uuid
from datetime import datetime
from src.generator.models_manager import model_manager
from src.generator.gpu_balancer import gpu_balancer
from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)

class AIGeneratorService:
    async def worker(self):
        await model_manager.load_models_on_gpus()
        while True:
            task = await redis_client.redis.rpop("priority_queue") \
                or await redis_client.redis.rpop("generation_queue")
            if not task:
                await asyncio.sleep(2); continue
            task = eval(task)  # храним dict строкой
            await self.process_task(task)

    async def process_task(self, task: dict):
        gpu_id = await gpu_balancer.get_available_gpu(priority=task["priority"])
        if gpu_id is None:
            await asyncio.sleep(5); return

        img_bytes = await model_manager.generate_image(
            gpu_id=gpu_id,
            prompt=task["prompt"],
            style=task["style"],
            quality=task["quality"],
            size=task["size"]
        )
        if img_bytes:
            filename = f"{task['task_id']}.jpg"
            from src.storage.minio_client import minio_client
            url = await minio_client.upload_bytes(img_bytes, filename)
            logger.info(f"Image saved to {url}")
        else:
            gpu_balancer.mark_gpu_error(gpu_id, "generation failed")

generator_service = AIGeneratorService()
