import asyncio, logging
from minio import Minio
from minio.error import S3Error
from src.shared.config import settings

logger = logging.getLogger(__name__)

class MinioClient:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False  # внутренняя сеть
        )
        self.bucket = "ai-images"

    async def ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            logger.info("🗄️  MinIO bucket created")

    async def upload_bytes(self, data: bytes, object_name: str, content_type="image/jpeg"):
        await self.ensure_bucket()
        self.client.put_object(self.bucket, object_name, data, len(data), content_type=content_type)
        return f"{self.bucket}/{object_name}"

minio_client = MinioClient()
