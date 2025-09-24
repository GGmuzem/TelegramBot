"""
Балансировщик нагрузки GPU для AI генерации
"""
import threading
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

import torch

from src.shared.config import settings
from src.shared.redis_client import redis_client

logger = logging.getLogger(__name__)


class GPUBalancer:
    """Балансировщик нагрузки между GPU для оптимального использования RTX 5080"""
    
    def __init__(self):
        # Получаем список доступных GPU
        self.gpu_devices = self._get_gpu_devices()
        
        # Состояние каждого GPU
        self.gpu_status = {}
        
        # Блокировка для thread-safety
        self.lock = threading.Lock()
        
        # Инициализируем состояние GPU
        self._initialize_gpu_status()
        
        # Статистика использования
        self.stats = {
            'total_generations': 0,
            'gpu_usage_time': {},
            'generation_times': [],
            'error_count': 0
        }
    
    def _get_gpu_devices(self) -> List[int]:
        """Получение списка доступных GPU"""
        try:
            if not torch.cuda.is_available():
                logger.warning("CUDA недоступна")
                return []
            
            gpu_count = torch.cuda.device_count()
            logger.info(f"Обнаружено GPU: {gpu_count}")
            
            # Проверяем конфигурацию GPU из настроек
            if hasattr(settings, 'GPU_DEVICES') and settings.GPU_DEVICES:
                configured_devices = [int(x) for x in settings.GPU_DEVICES.split(',')]
                available_devices = [i for i in configured_devices if i < gpu_count]
            else:
                available_devices = list(range(gpu_count))
            
            # Проверяем RTX 5080 и архитектуру Blackwell
            validated_devices = []
            for gpu_id in available_devices:
                props = torch.cuda.get_device_properties(gpu_id)
                
                logger.info(
                    f"GPU {gpu_id}: {props.name}, "
                    f"Compute: {props.major}.{props.minor}, "
                    f"Memory: {props.total_memory / 1024**3:.1f} GB"
                )
                
                # Проверяем минимальные требования
                if props.total_memory >= 8 * 1024**3:  # Минимум 8GB
                    validated_devices.append(gpu_id)
                    
                    # Отмечаем RTX 5080 с архитектурой Blackwell
                    if "RTX 5080" in props.name or (props.major == 12 and props.minor == 0):
                        logger.info(f"🚀 RTX 5080 с архитектурой Blackwell обнаружена на GPU {gpu_id}")
                else:
                    logger.warning(f"GPU {gpu_id} не соответствует минимальным требованиям")
            
            return validated_devices
            
        except Exception as e:
            logger.error(f"Ошибка определения GPU: {e}")
            return []
    
    def _initialize_gpu_status(self):
        """Инициализация статуса GPU"""
        for gpu_id in self.gpu_devices:
            self.gpu_status[gpu_id] = {
                "busy": False,
                "queue_length": 0,
                "current_task": None,
                "total_generations": 0,
                "total_time": 0.0,
                "error_count": 0,
                "memory_usage": 0.0,
                "temperature": 0.0,
                "last_used": None
            }
        
        logger.info(f"Инициализированы GPU: {list(self.gpu_status.keys())}")
    
    async def get_available_gpu(self, priority: bool = False) -> Optional[int]:
        """
        Получение оптимального GPU для задачи
        
        Args:
            priority: Приоритетная задача (для премиум пользователей)
        
        Returns:
            ID доступного GPU или None
        """
        try:
            with self.lock:
                available_gpus = []
                
                # Сначала ищем полностью свободные GPU
                for gpu_id, status in self.gpu_status.items():
                    if not status["busy"] and status["queue_length"] == 0:
                        available_gpus.append((gpu_id, 0))
                
                # Если нет свободных, ищем с минимальной очередью
                if not available_gpus:
                    for gpu_id, status in self.gpu_status.items():
                        if not status["busy"]:
                            available_gpus.append((gpu_id, status["queue_length"]))
                
                # Если все заняты, выбираем с минимальной очередью
                if not available_gpus:
                    for gpu_id, status in self.gpu_status.items():
                        available_gpus.append((gpu_id, status["queue_length"]))
                
                if not available_gpus:
                    return None
                
                # Сортируем по нагрузке и выбираем оптимальный
                available_gpus.sort(key=lambda x: (x[1], self.gpu_status[x[0]]["total_generations"]))
                
                selected_gpu = available_gpus[0][0]
                
                # Обновляем статус
                if priority:
                    # Приоритетные задачи идут в начало очереди
                    self.gpu_status[selected_gpu]["busy"] = True
                    self.gpu_status[selected_gpu]["current_task"] = f"priority_{datetime.now().isoformat()}"
                else:
                    self.gpu_status[selected_gpu]["queue_length"] += 1
                
                logger.info(f"Выделен GPU {selected_gpu} (приоритет: {priority})")
                return selected_gpu
                
        except Exception as e:
            logger.error(f"Ошибка выбора GPU: {e}")
            return None
    
    def release_gpu(self, gpu_id: int, generation_time: float = 0.0):
        """
        Освобождение GPU после завершения задачи
        
        Args:
            gpu_id: ID GPU для освобождения
            generation_time: Время генерации в секундах
        """
        try:
            with self.lock:
                if gpu_id in self.gpu_status:
                    status = self.gpu_status[gpu_id]
                    
                    if status["queue_length"] > 0:
                        status["queue_length"] -= 1
                    else:
                        status["busy"] = False
                        status["current_task"] = None
                    
                    # Обновляем статистику
                    status["total_generations"] += 1
                    status["total_time"] += generation_time
                    status["last_used"] = datetime.now()
                    
                    if generation_time > 0:
                        self.stats["generation_times"].append(generation_time)
                        self.stats["total_generations"] += 1
                    
                    logger.info(f"Освобожден GPU {gpu_id}, время: {generation_time:.1f}с")
                    
        except Exception as e:
            logger.error(f"Ошибка освобождения GPU {gpu_id}: {e}")
    
    def mark_gpu_error(self, gpu_id: int, error: str):
        """Отметка ошибки на GPU"""
        try:
            with self.lock:
                if gpu_id in self.gpu_status:
                    self.gpu_status[gpu_id]["error_count"] += 1
                    self.stats["error_count"] += 1
                    
                    logger.error(f"Ошибка на GPU {gpu_id}: {error}")
                    
                    # Если много ошибок, временно исключаем GPU
                    if self.gpu_status[gpu_id]["error_count"] > 5:
                        logger.warning(f"GPU {gpu_id} временно отключен из-за множественных ошибок")
                        # Можно добавить логику временного отключения
                        
        except Exception as e:
            logger.error(f"Ошибка отметки ошибки GPU {gpu_id}: {e}")
    
    async def get_gpu_stats(self) -> Dict[str, Any]:
        """Получение статистики использования GPU"""
        try:
            with self.lock:
                stats = {
                    "gpu_count": len(self.gpu_devices),
                    "gpu_status": self.gpu_status.copy(),
                    "total_generations": self.stats["total_generations"],
                    "total_errors": self.stats["error_count"],
                    "average_generation_time": 0.0,
                    "queue_lengths": {},
                    "memory_usage": {},
                    "availability": {}
                }
                
                # Вычисляем среднее время генерации
                if self.stats["generation_times"]:
                    stats["average_generation_time"] = sum(self.stats["generation_times"]) / len(self.stats["generation_times"])
                
                # Получаем текущую информацию о GPU
                for gpu_id in self.gpu_devices:
                    try:
                        # Длина очереди
                        stats["queue_lengths"][gpu_id] = self.gpu_status[gpu_id]["queue_length"]
                        
                        # Использование памяти GPU
                        if torch.cuda.is_available():
                            torch.cuda.set_device(gpu_id)
                            memory_allocated = torch.cuda.memory_allocated(gpu_id) / 1024**3
                            memory_reserved = torch.cuda.memory_reserved(gpu_id) / 1024**3
                            
                            stats["memory_usage"][gpu_id] = {
                                "allocated_gb": round(memory_allocated, 2),
                                "reserved_gb": round(memory_reserved, 2)
                            }
                        
                        # Доступность
                        stats["availability"][gpu_id] = not self.gpu_status[gpu_id]["busy"]
                        
                    except Exception as e:
                        logger.warning(f"Не удалось получить статистику GPU {gpu_id}: {e}")
                
                return stats
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики GPU: {e}")
            return {"error": str(e)}
    
    async def optimize_gpu_assignment(self):
        """Оптимизация распределения нагрузки между GPU"""
        try:
            with self.lock:
                # Находим перегруженные и недогруженные GPU
                total_load = sum(status["queue_length"] for status in self.gpu_status.values())
                
                if total_load == 0:
                    return
                
                average_load = total_load / len(self.gpu_devices)
                
                overloaded_gpus = []
                underloaded_gpus = []
                
                for gpu_id, status in self.gpu_status.items():
                    if status["queue_length"] > average_load * 1.5:
                        overloaded_gpus.append(gpu_id)
                    elif status["queue_length"] < average_load * 0.5:
                        underloaded_gpus.append(gpu_id)
                
                # Логируем информацию для мониторинга
                if overloaded_gpus or underloaded_gpus:
                    logger.info(
                        f"GPU балансировка: перегружены {overloaded_gpus}, "
                        f"недогружены {underloaded_gpus}"
                    )
                
                # Можно добавить логику перебалансировки задач
                
        except Exception as e:
            logger.error(f"Ошибка оптимизации GPU: {e}")
    
    async def cleanup_stale_tasks(self):
        """Очистка зависших задач"""
        try:
            with self.lock:
                current_time = datetime.now()
                
                for gpu_id, status in self.gpu_status.items():
                    # Проверяем задачи, которые выполняются слишком долго
                    if (status["current_task"] and 
                        status["last_used"] and 
                        (current_time - status["last_used"]).seconds > 600):  # 10 минут
                        
                        logger.warning(f"Обнаружена зависшая задача на GPU {gpu_id}")
                        
                        # Освобождаем GPU
                        status["busy"] = False
                        status["current_task"] = None
                        status["error_count"] += 1
                        
                        # Очищаем память GPU
                        try:
                            torch.cuda.empty_cache()
                        except:
                            pass
                
        except Exception as e:
            logger.error(f"Ошибка очистки зависших задач: {e}")
    
    async def save_stats_to_redis(self):
        """Сохранение статистики в Redis для мониторинга"""
        try:
            stats = await self.get_gpu_stats()
            await redis_client.set(
                "gpu_balancer_stats",
                stats,
                ex=300  # 5 минут
            )
            
        except Exception as e:
            logger.error(f"Ошибка сохранения статистики GPU в Redis: {e}")
    
    def get_recommended_quality(self, gpu_id: int) -> str:
        """Рекомендация качества генерации в зависимости от нагрузки GPU"""
        try:
            with self.lock:
                if gpu_id not in self.gpu_status:
                    return "standard"
                
                status = self.gpu_status[gpu_id]
                queue_length = status["queue_length"]
                
                # Рекомендуем качество в зависимости от нагрузки
                if queue_length == 0:
                    return "ultra"
                elif queue_length <= 2:
                    return "high"
                elif queue_length <= 5:
                    return "standard"
                else:
                    return "fast"
                    
        except Exception as e:
            logger.error(f"Ошибка определения рекомендуемого качества: {e}")
            return "standard"


# Глобальный экземпляр балансировщика
gpu_balancer = GPUBalancer()