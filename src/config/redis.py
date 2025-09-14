"""
Redis 配置和连接管理

提供 Redis 连接配置、健康检查和连接池管理功能
"""

import os
import redis
from typing import Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger

@dataclass
class RedisConfig:
    """Redis 配置类"""
    
    # 连接配置
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    
    # 连接池配置
    max_connections: int = 20
    retry_on_timeout: bool = True
    
    # 超时配置
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    
    # TTL 配置 (用于 LangGraph checkpointer)
    default_ttl: int = 3600  # 1小时，单位：秒
    refresh_on_read: bool = True
    
    # 键前缀
    checkpoint_prefix: str = "langgraph:checkpoint:"
    store_prefix: str = "langgraph:store:"
    
    @classmethod
    def from_env(cls) -> "RedisConfig":
        """从环境变量创建 Redis 配置"""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD"),
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
            socket_connect_timeout=int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            default_ttl=int(os.getenv("REDIS_DEFAULT_TTL", "3600")),
            refresh_on_read=os.getenv("REDIS_REFRESH_ON_READ", "true").lower() == "true",
            checkpoint_prefix=os.getenv("REDIS_CHECKPOINT_PREFIX", "langgraph:checkpoint:"),
            store_prefix=os.getenv("REDIS_STORE_PREFIX", "langgraph:store:")
        )
    
    def get_connection_url(self) -> str:
        """获取 Redis 连接 URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    def get_ttl_config(self) -> Dict[str, Any]:
        """获取 TTL 配置字典"""
        return {
            "default_ttl": self.default_ttl // 60,  # LangGraph Redis 期望分钟
            "refresh_on_read": self.refresh_on_read
        }


class RedisManager:
    """Redis 连接管理器"""
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or RedisConfig.from_env()
        self._redis_client: Optional[redis.Redis] = None
        
    @property
    def redis_client(self) -> redis.Redis:
        """获取 Redis 客户端（单例模式）"""
        if self._redis_client is None:
            # 创建连接池
            pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password,
                max_connections=self.config.max_connections,
                retry_on_timeout=self.config.retry_on_timeout,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
                decode_responses=True
            )
            # 显式创建同步 Redis 客户端
            self._redis_client = redis.Redis(connection_pool=pool)
        return self._redis_client
    
    def test_connection(self) -> bool:
        """测试 Redis 连接"""
        try:
            # 直接调用 ping()，同步客户端应该返回布尔值
            result = self.redis_client.ping()
            # 确保结果是布尔值
            success = bool(result)
            if success:
                logger.info(f"✅ Redis 连接成功: {self.config.host}:{self.config.port}")
            else:
                logger.error(f"❌ Redis ping 返回 False")
            return success
        except Exception as e:
            logger.error(f"❌ Redis 连接失败: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """获取 Redis 服务器信息"""
        try:
            info = self.redis_client.info()
            # 确保返回的是字典类型
            if isinstance(info, dict):
                return info
            else:
                logger.warning(f"Redis info() 返回了非字典类型: {type(info)}")
                return {}
        except Exception as e:
            logger.error(f"获取 Redis 信息失败: {e}")
            return {}
    
    def clear_cache(self, pattern: str = "*") -> int:
        """清理缓存"""
        try:
            keys = self.redis_client.keys(pattern)
            # 确保 keys 是列表类型
            if isinstance(keys, (list, tuple)) and keys:
                deleted = self.redis_client.delete(*keys)
                # 安全处理 deleted 的类型转换
                if isinstance(deleted, int):
                    deleted_count = deleted
                else:
                    # 对于非整数类型（包括异步类型），返回 0
                    logger.warning(f"Redis delete() 返回了非整数类型: {type(deleted)}，默认为 0")
                    deleted_count = 0
                    
                logger.info(f"清理了 {deleted_count} 个缓存键")
                return deleted_count
            elif isinstance(keys, (list, tuple)):
                # 空列表
                return 0
            else:
                logger.warning(f"Redis keys() 返回了非列表类型: {type(keys)}")
                return 0
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        try:
            # 直接调用 info() 方法，同步 Redis 客户端应该返回字典
            info = self.redis_client.info("memory")
            
            # 确保返回的是字典类型
            if isinstance(info, dict):
                return {
                    "used_memory": info.get("used_memory", 0),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "used_memory_peak": info.get("used_memory_peak", 0),
                    "used_memory_peak_human": info.get("used_memory_peak_human", "0B"),
                    "total_system_memory": info.get("total_system_memory", 0),
                    "total_system_memory_human": info.get("total_system_memory_human", "0B")
                }
            else:
                # 如果不是字典类型，记录警告并返回空字典
                logger.warning(f"Redis info() 返回了非字典类型: {type(info)}")
                return {}
        except Exception as e:
            logger.error(f"获取内存使用情况失败: {e}")
            return {}
    
    def close(self):
        """关闭 Redis 连接"""
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None
            logger.info("Redis 连接已关闭")


# 全局 Redis 管理器实例
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    """获取全局 Redis 管理器实例"""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


def get_redis_config() -> RedisConfig:
    """获取 Redis 配置"""
    return get_redis_manager().config


def test_redis_connection() -> bool:
    """测试 Redis 连接"""
    return get_redis_manager().test_connection()


# 健康检查函数
def redis_health_check() -> Dict[str, Any]:
    """Redis 健康检查"""
    manager = get_redis_manager()
    
    health_info = {
        "service": "redis",
        "status": "unknown",
        "details": {}
    }
    
    try:
        # 测试连接
        if manager.test_connection():
            health_info["status"] = "healthy"
            health_info["details"]["connection"] = "ok"
            
            # 获取服务器信息
            info = manager.get_info()
            if isinstance(info, dict):
                health_info["details"]["version"] = info.get("redis_version", "unknown")
                health_info["details"]["uptime"] = info.get("uptime_in_seconds", 0)
            
            # 获取内存使用情况
            memory_info = manager.get_memory_usage()
            health_info["details"]["memory"] = memory_info
            
        else:
            health_info["status"] = "unhealthy"
            health_info["details"]["error"] = "connection_failed"
            
    except Exception as e:
        health_info["status"] = "unhealthy"
        health_info["details"]["error"] = str(e)
    
    return health_info