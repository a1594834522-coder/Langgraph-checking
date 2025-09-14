"""
配置管理器

用于管理OCR API配置及环境变量
"""

import os
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ModelConfig:
    """配置管理器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.cache_dir = self.project_root / ".model_cache"
        
        # 智能初始化：检查是否在异步环境中
        try:
            import asyncio
            # 尝试获取当前任务，如果成功说明在异步环境中
            asyncio.current_task()
            logger.info("🔄 检测到异步环境，将延迟创建缓存目录")
        except RuntimeError:
            # 不在异步环境中，可以安全创建目录
            self.setup_cache_directories_sync()
        except Exception:
            # 如果检测失败，使用同步方式（向后兼容）
            self.setup_cache_directories_sync()
    
    async def setup_cache_directories(self):
        """设置缓存目录（异步版本）"""
        try:
            import asyncio
            # 使用异步方式创建目录
            await asyncio.to_thread(self.cache_dir.mkdir, parents=True, exist_ok=True)
            logger.info(f"📁 缓存目录: {self.cache_dir}")
            
        except Exception as e:
            logger.error(f"❌ 缓存目录设置失败: {e}")
    
    def setup_cache_directories_sync(self):
        """设置缓存目录（同步版本，仅用于初始化）"""
        try:
            # 创建本地缓存目录
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 缓存目录: {self.cache_dir}")
            
        except Exception as e:
            logger.error(f"❌ 缓存目录设置失败: {e}")
    
    async def is_models_cached(self) -> bool:
        """检查缓存是否存在（异步版本）"""
        import asyncio
        return await asyncio.to_thread(self.cache_dir.exists)
    
    async def get_cache_size(self) -> str:
        """获取缓存目录大小（异步版本）"""
        try:
            import asyncio
            total_size = 0
            
            # 使用异步方式遍历文件
            async def calculate_size():
                nonlocal total_size
                paths = await asyncio.to_thread(list, self.cache_dir.rglob("*"))
                for path in paths:
                    is_file = await asyncio.to_thread(path.is_file)
                    if is_file:
                        stat_result = await asyncio.to_thread(path.stat)
                        total_size += stat_result.st_size
            
            await calculate_size()
            
            # 转换为可读格式
            if total_size < 1024:
                return f"{total_size} B"
            elif total_size < 1024**2:
                return f"{total_size/1024:.1f} KB"
            elif total_size < 1024**3:
                return f"{total_size/1024**2:.1f} MB"
            else:
                return f"{total_size/1024**3:.1f} GB"
                
        except Exception as e:
            logger.error(f"❌ 获取缓存大小失败: {e}")
            return "未知"
    
    async def clear_cache(self):
        """清理缓存（异步版本）"""
        try:
            import shutil
            import asyncio
            if self.cache_dir.exists():
                await asyncio.to_thread(shutil.rmtree, self.cache_dir)
                logger.info("🧹 缓存已清理")
            await self.setup_cache_directories()
        except Exception as e:
            logger.error(f"❌ 清理缓存失败: {e}")
    
    def clear_cache_sync(self):
        """清理缓存（同步版本）"""
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                logger.info("🧹 缓存已清理")
            self.setup_cache_directories_sync()
        except Exception as e:
            logger.error(f"❌ 清理缓存失败: {e}")
    
    async def get_status(self) -> Dict[str, str]:
        """获取配置状态（异步版本）"""
        cache_size = await self.get_cache_size()
        return {
            "cache_dir": str(self.cache_dir),
            "cache_size": cache_size,
            "ocr_api_enabled": "启用",
        }
    
    def get_status_sync(self) -> Dict[str, str]:
        """获取配置状态（同步版本）"""
        try:
            total_size = 0
            if self.cache_dir.exists():
                for path in self.cache_dir.rglob("*"):
                    if path.is_file():
                        total_size += path.stat().st_size
            
            # 转换为可读格式
            if total_size < 1024:
                cache_size = f"{total_size} B"
            elif total_size < 1024**2:
                cache_size = f"{total_size/1024:.1f} KB"
            elif total_size < 1024**3:
                cache_size = f"{total_size/1024**2:.1f} MB"
            else:
                cache_size = f"{total_size/1024**3:.1f} GB"
        except Exception as e:
            logger.error(f"❌ 获取缓存大小失败: {e}")
            cache_size = "未知"
        
        return {
            "cache_dir": str(self.cache_dir),
            "cache_size": cache_size,
            "ocr_api_enabled": "启用",
        }


# 全局配置实例
model_config = ModelConfig()


async def setup_model_environment():
    """设置环境（在应用启动时调用，异步版本）"""
    logger.info("🔧 正在设置环境...")
    
    # 设置缓存目录
    await model_config.setup_cache_directories()
    
    # 打印状态信息
    status = await model_config.get_status()
    logger.info("📊 配置状态:")
    for key, value in status.items():
        logger.info(f"  {key}: {value}")

def setup_model_environment_sync():
    """设置环境（同步版本）"""
    logger.info("🔧 正在设置环境...")
    
    # 设置缓存目录
    model_config.setup_cache_directories_sync()
    
    # 打印状态信息
    status = model_config.get_status_sync()
    logger.info("📊 配置状态:")
    for key, value in status.items():
        logger.info(f"  {key}: {value}")


def print_model_help():
    """打印配置帮助信息"""
    help_text = """
🔧 OCR API配置选项:

环境变量设置:
  OCR_API_BASE_URL=http://183.203.184.233:8888    # OCR API地址

使用说明:
1. 启动OCR API服务
   确保您的OCR API服务正在运行
   默认地址: http://183.203.184.233:8888

2. 启动主应用
   python web_app_v2.py

缓存位置: {cache_dir}
""".format(cache_dir=model_config.cache_dir)
    
    print(help_text)


if __name__ == "__main__":
    print_model_help()