"""
配置模块

包含项目所有配置相关的功能：
- Redis 配置和连接管理
- 环境变量配置
- 其他系统配置
"""

from .model_config import (
    model_config, 
    setup_model_environment, 
    setup_model_environment_sync,
    print_model_help
)

__all__ = [
    'model_config', 
    'setup_model_environment', 
    'setup_model_environment_sync',
    'print_model_help'
]
