
"""
Обработчик изображений для AI бота
"""
import io
import logging
from typing import Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
import hashlib
from datetime import datetime

from src.storage.minio_client import minio_client
from src.shared.config import settings

logger = logging.getLogger(__name__)

class ImageHandler:
    """Класс для обработки и оптимизации изображений"""
    
    def __init__(self):
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.quality_settings = {
            "fast": {"quality": 70, "optimize": True},
            "standard": {"quality": 85, "optimize": True},
            "high": {"quality": 95, "optimize": True},
            "ultra": {"quality": 98, "optimize": False}
        }
    
    def validate_image(self, image_data: bytes) -> bool:
        """Валидация изображения"""
        try:
            if len(image_data) > self.max_file_size:
                logger.warning(f"Image too large: {len(image_data)} bytes")
                return False
            
            # Проверяем, что это валидное изображение
            with Image.open(io.BytesIO(image_data)) as img:
                img.verify()
            
            return True
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False
    
    def optimize_image(self, image_data: bytes, quality: str = "standard") -> bytes:
        """Оптимизация изображения"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Применяем настройки качества
                quality_config = self.quality_settings.get(quality, self.quality_settings["standard"])
                
                # Сохраняем оптимизированное изображение
                output = io.BytesIO()
                img.save(
                    output, 
                    format='JPEG',
                    quality=quality_config["quality"],
                    optimize=quality_config["optimize"]
                )
                
                optimized_data = output.getvalue()
                logger.info(f"Image optimized: {len(image_data)} -> {len(optimized_data)} bytes")
                
                return optimized_data
                
        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            return image_data
    
    def resize_image(self, image_data: bytes, size: Tuple[int, int]) -> bytes:
        """Изменение размера изображения"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Сохраняем пропорции
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                
                return output.getvalue()
                
        except Exception as e:
            logger.error(f"Image resize failed: {e}")
            return image_data
    
    def add_watermark(self, image_data: bytes, watermark_text: str = "AI Generated") -> bytes:
        """Добавление водяного знака"""
        try:
            from PIL import ImageDraw, ImageFont
            
            with Image.open(io.BytesIO(image_data)) as img:
                # Создаем слой для водяного знака
                watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(watermark)
                
                # Настройки водяного знака
                font_size = max(img.size) // 40
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                
                # Позиция водяного знака (правый нижний угол)
                text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                x = img.size[0] - text_width - 20
                y = img.size[1] - text_height - 20
                
                # Полупрозрачный водяной знак
                draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))
                
                # Накладываем водяной знак
                watermarked = Image.alpha_composite(img.convert('RGBA'), watermark)
                
                output = io.BytesIO()
                watermarked.convert('RGB').save(output, format='JPEG', quality=90)
                
                return output.getvalue()
                
        except Exception as e:
            logger.error(f"Watermark failed: {e}")
            return image_data
    
    def generate_thumbnail(self, image_data: bytes, size: Tuple[int, int] = (256, 256)) -> bytes:
        """Создание миниатюры"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=75, optimize=True)
                
                return output.getvalue()
                
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return image_data
    
    def get_image_info(self, image_data: bytes) -> dict:
        """Получение информации об изображении"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "file_size": len(image_data),
                    "hash": hashlib.md5(image_data).hexdigest()
                }
        except Exception as e:
            logger.error(f"Failed to get image info: {e}")
            return {}
    
    async def save_image(self, image_data: bytes, filename: str, user_id: int, quality: str = "standard") -> Optional[str]:
        """Сохранение изображения в хранилище"""
        try:
            # Валидация
            if not self.validate_image(image_data):
                return None
            
            # Оптимизация
            optimized_data = self.optimize_image(image_data, quality)
            
            # Добавляем водяной знак для платных изображений
            if quality in ["high", "ultra"]:
                optimized_data = self.add_watermark(optimized_data)
            
            # Сохраняем в MinIO
            object_name = f"generated/{user_id}/{filename}"
            url = await minio_client.upload_bytes(optimized_data, object_name)
            
            # Создаем миниатюру
            thumbnail_data = self.generate_thumbnail(optimized_data)
            thumbnail_name = f"thumbnails/{user_id}/{filename}"
            await minio_client.upload_bytes(thumbnail_data, thumbnail_name)
            
            logger.info(f"Image saved: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            return None

# Глобальный экземпляр
image_handler = ImageHandler()
