"""
警告配置管理

统一管理系统中的警告过滤器，特别针对第三方库的弃用警告
"""

import warnings
import os


def setup_warning_filters():
    """
    设置系统警告过滤器
    
    主要针对以下警告进行优化：
    1. pkg_resources弃用警告（来自Marker内部）
    2. 其他第三方库的不必要警告
    """
    
    # 抑制pkg_resources弃用警告
    # 这个警告来自Marker库内部，用户无法控制
    warnings.filterwarnings(
        "ignore", 
        category=DeprecationWarning, 
        module="pkg_resources"
    )
    
    # 抑制setuptools相关的pkg_resources警告
    warnings.filterwarnings(
        "ignore",
        message=".*pkg_resources is deprecated.*",
        category=UserWarning
    )
    
    # 抑制其他第三方库的常见警告
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module="transformers"
    )
    
    # 可选：在开发模式下显示所有警告
    if os.environ.get("LANGGRAPH_DEBUG", "false").lower() == "true":
        warnings.resetwarnings()
        warnings.simplefilter("always", DeprecationWarning)
        print("🔍 调试模式：显示所有警告信息")
    else:
        print("✅ 已配置警告过滤器，抑制第三方库不必要的警告")


def suppress_marker_warnings():
    """
    保持兼容性函数（已无作用）
    """
    pass


def get_warning_env_vars():
    """
    获取用于抑制警告的环境变量字典
    
    Returns:
        环境变量字典
    """
    return {
        "PYTHONWARNINGS": "ignore::DeprecationWarning:pkg_resources",
        "TRANSFORMERS_VERBOSITY": "error",  # 降低transformers库的输出等级
        "TOKENIZERS_PARALLELISM": "false",  # 避免tokenizers并发警告
    }


# 自动在模块导入时设置警告过滤器
if __name__ != "__main__":
    setup_warning_filters()