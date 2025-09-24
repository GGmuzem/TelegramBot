"""
Менеджер AI моделей для генерации изображений
Оптимизирован для RTX 5080 с архитектурой Blackwell
"""
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

import torch
import torch.nn.functional as F
from diffusers import (
    StableDiffusionXLPipeline, 
    StableDiffusionXLImg2ImgPipeline,
    LCMScheduler,
    DiffusionPipeline
)
from diffusers.models import AutoencoderKL
from safetensors.torch import load_file
import xformers

from src.shared.config import settings, QUALITY_SETTINGS, IMAGE_STYLES
from src.generator.gpu_balancer import gpu_balancer

logger = logging.getLogger(__name__)


class ModelManager:
    """Менеджер загрузки и управления AI моделями"""
    
    def __init__(self):
        # Пути к моделям
        self.model_cache_dir = getattr(settings, 'MODEL_CACHE_DIR', './models')
        os.makedirs(self.model_cache_dir, exist_ok=True)
        
        # Загруженные модели по GPU
        self.loaded_models: Dict[int, Dict[str, Any]] = {}
        
        # Конфигурация моделей
        self.model_configs = {
            "sdxl_base": {
                "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
                "type": "text2img",
                "memory_gb": 8.0,
                "recommended_steps": 20
            },
            "sdxl_turbo": {
                "model_id": "stabilityai/sdxl-turbo", 
                "type": "text2img",
                "memory_gb": 6.0,
                "recommended_steps": 4
            },
            "lcm_sdxl": {
                "model_id": "latent-consistency/lcm-sdxl",
                "type": "text2img", 
                "memory_gb": 6.0,
                "recommended_steps": 8
            }
        }
        
        # Статистика использования моделей
        self.model_stats = {
            "total_generations": 0,
            "model_usage": {},
            "generation_times": [],
            "memory_usage": {}
        }
    
    async def load_models_on_gpus(self) -> Dict[int, bool]:
        """Загрузка моделей на доступные GPU"""
        results = {}
        
        for gpu_id in gpu_balancer.gpu_devices:
            try:
                logger.info(f"Загрузка моделей на GPU {gpu_id}...")
                success = await self.load_models_on_gpu(gpu_id)
                results[gpu_id] = success
                
                if success:
                    logger.info(f"✅ Модели успешно загружены на GPU {gpu_id}")
                else:
                    logger.error(f"❌ Не удалось загрузить модели на GPU {gpu_id}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки моделей на GPU {gpu_id}: {e}")
                results[gpu_id] = False
        
        return results
    
    async def load_models_on_gpu(self, gpu_id: int) -> bool:
        """Загрузка моделей на конкретный GPU"""
        try:
            # Устанавливаем устройство
            device = f"cuda:{gpu_id}"
            torch.cuda.set_device(gpu_id)
            
            # Очищаем кеш памяти
            torch.cuda.empty_cache()
            
            # Проверяем доступную память
            memory_gb = torch.cuda.get_device_properties(gpu_id).total_memory / 1024**3
            logger.info(f"GPU {gpu_id} имеет {memory_gb:.1f} GB памяти")
            
            models = {}
            
            # Загружаем SDXL Base (основная модель)
            logger.info(f"Загрузка SDXL Base на GPU {gpu_id}...")
            models["sdxl_base"] = await self._load_sdxl_base(device)
            
            # Если достаточно памяти, загружаем дополнительные модели
            current_memory = torch.cuda.memory_allocated(gpu_id) / 1024**3
            available_memory = memory_gb - current_memory - 2  # Резерв 2GB
            
            if available_memory > 6:
                logger.info(f"Загрузка SDXL Turbo на GPU {gpu_id}...")
                models["sdxl_turbo"] = await self._load_sdxl_turbo(device)
            
            if available_memory > 4:
                logger.info(f"Загрузка LCM на GPU {gpu_id}...")
                models["lcm"] = await self._load_lcm_model(device)
            
            # Сохраняем загруженные модели
            self.loaded_models[gpu_id] = models
            
            # Обновляем статистику памяти
            final_memory = torch.cuda.memory_allocated(gpu_id) / 1024**3
            self.model_stats["memory_usage"][gpu_id] = final_memory
            
            logger.info(f"GPU {gpu_id}: Использовано памяти {final_memory:.1f}GB из {memory_gb:.1f}GB")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей на GPU {gpu_id}: {e}")
            return False
    
    async def _load_sdxl_base(self, device: str) -> DiffusionPipeline:
        """Загрузка основной модели SDXL"""
        try:
            # Настройки для RTX 5080 и архитектуры Blackwell
            torch_dtype = torch.float16
            variant = "fp16"
            
            pipeline = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                cache_dir=self.model_cache_dir,
                torch_dtype=torch_dtype,
                variant=variant,
                use_safetensors=True,
                add_watermarker=False
            ).to(device)
            
            # Оптимизации для RTX 5080
            pipeline.enable_xformers_memory_efficient_attention()
            pipeline.enable_model_cpu_offload() if device != "cuda:0" else None
            
            # Компиляция для ускорения на Blackwell
            if hasattr(torch, 'compile'):
                try:
                    pipeline.unet = torch.compile(pipeline.unet, mode="reduce-overhead")
                    logger.info(f"Модель скомпилирована для ускорения на {device}")
                except Exception as e:
                    logger.warning(f"Не удалось скомпилировать модель: {e}")
            
            return pipeline
            
        except Exception as e:
            logger.error(f"Ошибка загрузки SDXL Base: {e}")
            raise
    
    async def _load_sdxl_turbo(self, device: str) -> DiffusionPipeline:
        """Загрузка быстрой модели SDXL Turbo"""
        try:
            pipeline = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/sdxl-turbo",
                cache_dir=self.model_cache_dir,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True
            ).to(device)
            
            pipeline.enable_xformers_memory_efficient_attention()
            
            return pipeline
            
        except Exception as e:
            logger.error(f"Ошибка загрузки SDXL Turbo: {e}")
            raise
    
    async def _load_lcm_model(self, device: str) -> DiffusionPipeline:
        """Загрузка LCM модели для сверхбыстрой генерации"""
        try:
            # Загружаем базовую SDXL и заменяем планировщик на LCM
            pipeline = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                cache_dir=self.model_cache_dir,
                torch_dtype=torch.float16,
                variant="fp16",
                use_safetensors=True
            )
            
            # Заменяем планировщик на LCM
            pipeline.scheduler = LCMScheduler.from_config(pipeline.scheduler.config)
            
            # Загружаем LoRA адаптер LCM
            pipeline.load_lora_weights("latent-consistency/lcm-lora-sdxl")
            
            pipeline = pipeline.to(device)
            pipeline.enable_xformers_memory_efficient_attention()
            
            return pipeline
            
        except Exception as e:
            logger.error(f"Ошибка загрузки LCM модели: {e}")
            raise
    
    def get_optimal_model(self, gpu_id: int, quality: str) -> Optional[DiffusionPipeline]:
        """Получение оптимальной модели для заданного качества"""
        try:
            if gpu_id not in self.loaded_models:
                logger.error(f"Модели не загружены на GPU {gpu_id}")
                return None
            
            models = self.loaded_models[gpu_id]
            
            # Выбираем модель в зависимости от качества
            if quality == "fast" and "lcm" in models:
                return models["lcm"]
            elif quality in ["fast", "standard"] and "sdxl_turbo" in models:
                return models["sdxl_turbo"]
            elif "sdxl_base" in models:
                return models["sdxl_base"]
            else:
                # Возвращаем любую доступную модель
                return next(iter(models.values())) if models else None
                
        except Exception as e:
            logger.error(f"Ошибка выбора модели: {e}")
            return None
    
    def apply_style_to_prompt(self, prompt: str, style: str) -> str:
        """Применение стиля к промпту"""
        try:
            if style not in IMAGE_STYLES:
                return prompt
            
            style_config = IMAGE_STYLES[style]
            
            # Добавляем префикс стиля
            styled_prompt = f"{style_config.get('prefix', '')}, {prompt}"
            
            # Добавляем суффикс стиля
            if 'suffix' in style_config:
                styled_prompt = f"{styled_prompt}, {style_config['suffix']}"
            
            # Добавляем негативные промпты
            negative_prompt = style_config.get('negative', '')
            
            return styled_prompt, negative_prompt
            
        except Exception as e:
            logger.error(f"Ошибка применения стиля {style}: {e}")
            return prompt, ""
    
    async def generate_image(
        self,
        gpu_id: int,
        prompt: str,
        style: str = "realistic",
        quality: str = "standard",
        size: str = "512x512",
        guidance_scale: float = 7.5,
        seed: Optional[int] = None
    ) -> Optional[bytes]:
        """
        Генерация изображения
        
        Args:
            gpu_id: ID GPU для генерации
            prompt: Текстовый промпт
            style: Стиль изображения
            quality: Качество генерации
            size: Размер изображения
            guidance_scale: Степень следования промпту
            seed: Семя для воспроизводимости
        
        Returns:
            Байты изображения или None при ошибке
        """
        generation_start = datetime.now()
        
        try:
            # Получаем модель
            model = self.get_optimal_model(gpu_id, quality)
            if not model:
                raise ValueError(f"Нет доступной модели на GPU {gpu_id}")
            
            # Применяем стиль к промпту
            styled_prompt, negative_prompt = self.apply_style_to_prompt(prompt, style)
            
            # Определяем параметры генерации
            quality_config = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS["standard"])
            num_inference_steps = quality_config["steps"]
            
            # Парсим размер
            width, height = map(int, size.split('x'))
            
            # Устанавливаем устройство
            torch.cuda.set_device(gpu_id)
            
            # Генерируем изображение
            with torch.cuda.amp.autocast():
                if seed is not None:
                    generator = torch.Generator(device=f"cuda:{gpu_id}").manual_seed(seed)
                else:
                    generator = None
                
                result = model(
                    prompt=styled_prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    width=width,
                    height=height,
                    generator=generator,
                    output_type="pil"
                )
                
                image = result.images[0]
            
            # Конвертируем в байты
            from io import BytesIO
            img_bytes = BytesIO()
            image.save(img_bytes, format='JPEG', quality=90, optimize=True)
            img_bytes.seek(0)
            
            # Обновляем статистику
            generation_time = (datetime.now() - generation_start).total_seconds()
            await self._update_generation_stats(gpu_id, quality, generation_time, True)
            
            logger.info(
                f"✅ Изображение сгенерировано на GPU {gpu_id}: "
                f"{quality}/{style}/{size}, время: {generation_time:.1f}с"
            )
            
            return img_bytes.getvalue()
            
        except Exception as e:
            generation_time = (datetime.now() - generation_start).total_seconds()
            await self._update_generation_stats(gpu_id, quality, generation_time, False)
            
            logger.error(f"❌ Ошибка генерации на GPU {gpu_id}: {e}")
            return None
    
    async def _update_generation_stats(
        self, 
        gpu_id: int, 
        quality: str, 
        generation_time: float, 
        success: bool
    ):
        """Обновление статистики генерации"""
        try:
            self.model_stats["total_generations"] += 1
            self.model_stats["generation_times"].append(generation_time)
            
            # Статистика по качеству
            if quality not in self.model_stats["model_usage"]:
                self.model_stats["model_usage"][quality] = {
                    "count": 0,
                    "total_time": 0.0,
                    "success_count": 0
                }
            
            stats = self.model_stats["model_usage"][quality]
            stats["count"] += 1
            stats["total_time"] += generation_time
            
            if success:
                stats["success_count"] += 1
            
            # Освобождаем GPU в балансировщике
            gpu_balancer.release_gpu(gpu_id, generation_time)
            
        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о загруженных моделях"""
        try:
            info = {
                "loaded_gpus": list(self.loaded_models.keys()),
                "model_configs": self.model_configs,
                "stats": self.model_stats,
                "memory_usage": {},
                "model_status": {}
            }
            
            # Информация о памяти каждого GPU
            for gpu_id in self.loaded_models:
                try:
                    torch.cuda.set_device(gpu_id)
                    allocated = torch.cuda.memory_allocated(gpu_id) / 1024**3
                    reserved = torch.cuda.memory_reserved(gpu_id) / 1024**3
                    total = torch.cuda.get_device_properties(gpu_id).total_memory / 1024**3
                    
                    info["memory_usage"][gpu_id] = {
                        "allocated_gb": round(allocated, 2),
                        "reserved_gb": round(reserved, 2),
                        "total_gb": round(total, 2),
                        "utilization_percent": round((allocated / total) * 100, 1)
                    }
                    
                    # Статус моделей на GPU
                    info["model_status"][gpu_id] = list(self.loaded_models[gpu_id].keys())
                    
                except Exception as e:
                    logger.warning(f"Не удалось получить информацию о GPU {gpu_id}: {e}")
            
            return info
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о моделях: {e}")
            return {"error": str(e)}
    
    async def cleanup_models(self):
        """Очистка неиспользуемых моделей из памяти"""
        try:
            for gpu_id in list(self.loaded_models.keys()):
                torch.cuda.set_device(gpu_id)
                
                # Удаляем модели из памяти
                if gpu_id in self.loaded_models:
                    for model_name, model in self.loaded_models[gpu_id].items():
                        try:
                            del model
                            logger.info(f"Модель {model_name} удалена с GPU {gpu_id}")
                        except Exception as e:
                            logger.warning(f"Не удалось удалить модель {model_name}: {e}")
                    
                    del self.loaded_models[gpu_id]
                
                # Очищаем кеш CUDA
                torch.cuda.empty_cache()
                
                logger.info(f"Очищена память GPU {gpu_id}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки моделей: {e}")


# Глобальный экземпляр менеджера моделей
model_manager = ModelManager()