"""
PostgreSQL 配置和连接管理

基于查阅的技术文档实现：
- SQLAlchemy 同步和异步引擎配置
- Asyncpg 连接池管理
- Psycopg 多版本支持
- 健康检查和连接测试
"""

import os
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager, asynccontextmanager
from loguru import logger

# SQLAlchemy 导入
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

# PostgreSQL 驱动程序导入
try:
    import asyncpg  # type: ignore
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg 不可用，异步连接功能将受限")

try:
    import psycopg  # type: ignore
    PSYCOPG3_AVAILABLE = True
except ImportError:
    PSYCOPG3_AVAILABLE = False
    logger.warning("psycopg3 不可用，部分功能将使用 psycopg2")

try:
    import psycopg2  # type: ignore
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 不可用")


@dataclass
class PostgreSQLConfig:
    """PostgreSQL 配置类"""
    
    # 基本连接配置
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    username: str = "postgres"
    password: str = ""
    
    # 连接池配置
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    # 连接选项
    connect_timeout: int = 10
    command_timeout: int = 60
    
    # SSL 配置
    sslmode: str = "prefer"
    sslcert: Optional[str] = None
    sslkey: Optional[str] = None
    sslrootcert: Optional[str] = None
    
    # 应用程序配置
    application_name: str = "langgraph_app"
    
    # SQLAlchemy 配置
    echo: bool = False
    echo_pool: bool = False
    
    # 驱动程序偏好
    preferred_driver: str = "asyncpg"  # asyncpg, psycopg, psycopg2
    
    @classmethod
    def from_env(cls) -> "PostgreSQLConfig":
        """从环境变量创建配置"""
        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DATABASE", "postgres"),
            username=os.getenv("POSTGRES_USERNAME", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            pool_size=int(os.getenv("POSTGRES_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("POSTGRES_MAX_OVERFLOW", "20")),
            pool_timeout=int(os.getenv("POSTGRES_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("POSTGRES_POOL_RECYCLE", "3600")),
            connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10")),
            command_timeout=int(os.getenv("POSTGRES_COMMAND_TIMEOUT", "60")),
            sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
            sslcert=os.getenv("POSTGRES_SSLCERT"),
            sslkey=os.getenv("POSTGRES_SSLKEY"),
            sslrootcert=os.getenv("POSTGRES_SSLROOTCERT"),
            application_name=os.getenv("POSTGRES_APPLICATION_NAME", "langgraph_app"),
            echo=os.getenv("POSTGRES_ECHO", "false").lower() == "true",
            echo_pool=os.getenv("POSTGRES_ECHO_POOL", "false").lower() == "true",
            preferred_driver=os.getenv("POSTGRES_PREFERRED_DRIVER", "asyncpg")
        )
    
    def get_sync_url(self, driver: Optional[str] = None) -> str:
        """生成同步连接 URL"""
        if driver is None:
            driver = "psycopg2" if PSYCOPG2_AVAILABLE else "psycopg"
        
        base_url = f"postgresql+{driver}://{self.username}"
        if self.password:
            base_url += f":{self.password}"
        base_url += f"@{self.host}:{self.port}/{self.database}"
        
        # 添加连接参数
        params = []
        if self.sslmode:
            params.append(f"sslmode={self.sslmode}")
        if self.sslcert:
            params.append(f"sslcert={self.sslcert}")
        if self.application_name:
            params.append(f"application_name={self.application_name}")
        
        if params:
            base_url += "?" + "&".join(params)
        
        return base_url
    
    def get_async_url(self, driver: Optional[str] = None) -> str:
        """生成异步连接 URL"""
        if driver is None:
            driver = self.preferred_driver if self.preferred_driver in ["asyncpg", "psycopg"] else "asyncpg"
        
        base_url = f"postgresql+{driver}://{self.username}"
        if self.password:
            base_url += f":{self.password}"
        base_url += f"@{self.host}:{self.port}/{self.database}"
        
        # 添加连接参数
        params = []
        if self.sslmode:
            params.append(f"sslmode={self.sslmode}")
        if self.application_name:
            params.append(f"application_name={self.application_name}")
        
        if params:
            base_url += "?" + "&".join(params)
        
        return base_url


class PostgreSQLManager:
    """PostgreSQL 连接管理器"""
    
    def __init__(self, config: Optional[PostgreSQLConfig] = None):
        self.config = config or PostgreSQLConfig.from_env()
        self._sync_engine: Optional[Engine] = None
        self._async_engine: Optional[AsyncEngine] = None
        self._sync_session_factory: Optional[sessionmaker] = None
        self._async_session_factory: Optional[async_sessionmaker] = None
        self._asyncpg_pool: Optional[Any] = None
        
    @property
    def sync_engine(self) -> Engine:
        """获取同步引擎"""
        if self._sync_engine is None:
            self._sync_engine = self._create_sync_engine()
        return self._sync_engine
    
    @property
    def async_engine(self) -> AsyncEngine:
        """获取异步引擎"""
        if self._async_engine is None:
            self._async_engine = self._create_async_engine()
        return self._async_engine
    
    @property
    def sync_session_factory(self) -> sessionmaker:
        """获取同步会话工厂"""
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                bind=self.sync_engine,
                expire_on_commit=False
            )
        return self._sync_session_factory
    
    @property
    def async_session_factory(self) -> async_sessionmaker:
        """获取异步会话工厂"""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                expire_on_commit=False
            )
        return self._async_session_factory
    
    def _create_sync_engine(self) -> Engine:
        """创建同步引擎"""
        url = self.config.get_sync_url()
        
        engine_kwargs = {
            "echo": self.config.echo,
            "echo_pool": self.config.echo_pool,
            "pool_size": self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "pool_timeout": self.config.pool_timeout,
            "pool_recycle": self.config.pool_recycle,
            "poolclass": QueuePool,
            "connect_args": {
                "connect_timeout": self.config.connect_timeout,
            }
        }
        
        logger.info(f"创建同步 PostgreSQL 引擎: {url.split('@')[0]}@***")
        return create_engine(url, **engine_kwargs)
    
    def _create_async_engine(self) -> AsyncEngine:
        """创建异步引擎"""
        url = self.config.get_async_url()
        
        engine_kwargs = {
            "echo": self.config.echo,
            "echo_pool": self.config.echo_pool,
            "pool_size": self.config.pool_size,
            "max_overflow": self.config.max_overflow,
            "pool_timeout": self.config.pool_timeout,
            "pool_recycle": self.config.pool_recycle,
        }
        
        # 异步引擎的连接参数
        connect_args = {}
        if "asyncpg" in url:
            connect_args.update({
                "server_settings": {
                    "application_name": self.config.application_name,
                    "jit": "off"  # 优化性能
                },
                "command_timeout": self.config.command_timeout,
            })
        elif "psycopg" in url:
            connect_args.update({
                "connect_timeout": self.config.connect_timeout,
            })
        
        if connect_args:
            engine_kwargs["connect_args"] = connect_args
        
        logger.info(f"创建异步 PostgreSQL 引擎: {url.split('@')[0]}@***")
        return create_async_engine(url, **engine_kwargs)
    
    async def create_asyncpg_pool(self) -> Optional[Any]:
        """创建原生 asyncpg 连接池"""
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg 不可用，无法创建原生连接池")
            return None
        
        if self._asyncpg_pool is not None:
            return self._asyncpg_pool
        
        try:
            pool_kwargs = {
                "host": self.config.host,
                "port": self.config.port,
                "user": self.config.username,
                "password": self.config.password,
                "database": self.config.database,
                "min_size": 1,
                "max_size": self.config.pool_size,
                "command_timeout": self.config.command_timeout,
                "server_settings": {
                    "application_name": self.config.application_name,
                    "timezone": "UTC"
                }
            }
            
            if self.config.sslmode and self.config.sslmode != "disable":
                pool_kwargs["ssl"] = self.config.sslmode
            
            if not ASYNCPG_AVAILABLE:
                logger.error("❌ asyncpg 模块不可用")
                return None
                
            # 使用动态导入防止类型错误
            import asyncpg  # type: ignore
            self._asyncpg_pool = await asyncpg.create_pool(**pool_kwargs)
            logger.info(f"✅ 创建 asyncpg 连接池成功")
            return self._asyncpg_pool
            
        except Exception as e:
            logger.error(f"❌ 创建 asyncpg 连接池失败: {e}")
            return None
    
    @contextmanager
    def get_sync_session(self):
        """获取同步会话上下文管理器"""
        session = self.sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self):
        """获取异步会话上下文管理器"""
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    def test_sync_connection(self) -> bool:
        """测试同步连接"""
        try:
            with self.sync_engine.connect() as connection:
                result = connection.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"✅ 同步连接测试成功: PostgreSQL {version}")
                return True
        except Exception as e:
            logger.error(f"❌ 同步连接测试失败: {e}")
            return False
    
    async def test_async_connection(self) -> bool:
        """测试异步连接"""
        try:
            async with self.async_engine.connect() as connection:
                result = await connection.execute(text("SELECT version()"))
                version = result.scalar()
                logger.info(f"✅ 异步连接测试成功: PostgreSQL {version}")
                return True
        except Exception as e:
            logger.error(f"❌ 异步连接测试失败: {e}")
            return False
    
    async def test_asyncpg_pool(self) -> bool:
        """测试 asyncpg 连接池"""
        pool = await self.create_asyncpg_pool()
        if pool is None:
            return False
        
        try:
            async with pool.acquire() as connection:
                version = await connection.fetchval("SELECT version()")
                logger.info(f"✅ asyncpg 连接池测试成功: PostgreSQL {version}")
                return True
        except Exception as e:
            logger.error(f"❌ asyncpg 连接池测试失败: {e}")
            return False
    
    async def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        info = {}
        
        try:
            async with self.async_engine.connect() as connection:
                # 获取版本信息
                result = await connection.execute(text("SELECT version()"))
                info["version"] = result.scalar()
                
                # 获取数据库大小
                result = await connection.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                ))
                info["database_size"] = result.scalar()
                
                # 获取连接数
                result = await connection.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                ))
                info["active_connections"] = result.scalar()
                
                # 获取最大连接数
                result = await connection.execute(text("SHOW max_connections"))
                info["max_connections"] = result.scalar()
                
                # 获取数据库编码
                result = await connection.execute(text("SHOW server_encoding"))
                info["encoding"] = result.scalar()
                
                logger.info("📊 数据库信息获取成功")
                
        except Exception as e:
            logger.error(f"❌ 获取数据库信息失败: {e}")
            info["error"] = str(e)
        
        return info
    
    async def close(self):
        """关闭所有连接"""
        try:
            if self._async_engine:
                await self._async_engine.dispose()
                logger.info("异步引擎已关闭")
            
            if self._sync_engine:
                self._sync_engine.dispose()
                logger.info("同步引擎已关闭")
            
            if self._asyncpg_pool:
                await self._asyncpg_pool.close()
                logger.info("asyncpg 连接池已关闭")
                
        except Exception as e:
            logger.error(f"关闭连接时出错: {e}")


# 全局管理器实例
_postgresql_manager: Optional[PostgreSQLManager] = None


def get_postgresql_manager() -> PostgreSQLManager:
    """获取全局 PostgreSQL 管理器实例"""
    global _postgresql_manager
    if _postgresql_manager is None:
        _postgresql_manager = PostgreSQLManager()
    return _postgresql_manager


def get_postgresql_config() -> PostgreSQLConfig:
    """获取 PostgreSQL 配置"""
    return get_postgresql_manager().config


async def test_postgresql_connection() -> bool:
    """测试 PostgreSQL 连接"""
    manager = get_postgresql_manager()
    
    # 测试同步连接
    sync_result = manager.test_sync_connection()
    
    # 测试异步连接
    async_result = await manager.test_async_connection()
    
    # 测试 asyncpg 连接池（如果可用）
    pool_result = True
    if ASYNCPG_AVAILABLE:
        pool_result = await manager.test_asyncpg_pool()
    
    return sync_result and async_result and pool_result


async def postgresql_health_check() -> Dict[str, Any]:
    """PostgreSQL 健康检查"""
    manager = get_postgresql_manager()
    
    health_info = {
        "status": "unknown",
        "timestamp": asyncio.get_event_loop().time(),
        "sync_connection": False,
        "async_connection": False,
        "asyncpg_pool": False,
        "database_info": {}
    }
    
    try:
        # 测试连接
        health_info["sync_connection"] = manager.test_sync_connection()
        health_info["async_connection"] = await manager.test_async_connection()
        
        if ASYNCPG_AVAILABLE:
            health_info["asyncpg_pool"] = await manager.test_asyncpg_pool()
        
        # 获取数据库信息
        health_info["database_info"] = await manager.get_database_info()
        
        # 判断整体状态
        if health_info["sync_connection"] and health_info["async_connection"]:
            health_info["status"] = "healthy"
        else:
            health_info["status"] = "degraded"
            
    except Exception as e:
        health_info["status"] = "unhealthy"
        health_info["error"] = str(e)
        logger.error(f"PostgreSQL 健康检查失败: {e}")
    
    return health_info


if __name__ == "__main__":
    # 测试代码
    async def main():
        logger.info("🚀 开始 PostgreSQL 连接测试...")
        
        # 测试配置
        config = PostgreSQLConfig.from_env()
        logger.info(f"配置: {config.host}:{config.port}/{config.database}")
        
        # 测试连接
        manager = PostgreSQLManager(config)
        success = await test_postgresql_connection()
        
        if success:
            logger.info("✅ 所有连接测试通过")
            
            # 获取数据库信息
            info = await manager.get_database_info()
            logger.info(f"数据库信息: {info}")
            
            # 健康检查
            health = await postgresql_health_check()
            logger.info(f"健康状态: {health['status']}")
        else:
            logger.error("❌ 连接测试失败")
        
        # 清理
        await manager.close()
    
    asyncio.run(main())