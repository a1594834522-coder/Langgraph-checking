"""
API配置工具

用于配置PDF提取API端点和相关参数
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# 全局API配置
_api_config = {
    "pdf_extraction_endpoint": "http://183.203.184.233:8888/pdf_parse_supplychain",  # 用户提供的实际端点
    "timeout": 60,
    "max_file_size": 20 * 1024 * 1024,  # 20MB
    "supported_formats": [".pdf"]
}


def configure_pdf_api(endpoint: str, timeout: int = 60, max_file_size: int = 20 * 1024 * 1024) -> None:
    """
    配置PDF提取API
    
    Args:
        endpoint: API端点URL
        timeout: 超时时间（秒）
        max_file_size: 最大文件大小（字节）
    """
    global _api_config
    
    _api_config.update({
        "pdf_extraction_endpoint": endpoint,
        "timeout": timeout,
        "max_file_size": max_file_size
    })
    
    logger.info(f"PDF API已配置: {endpoint}")
    print(f"✅ PDF提取API已配置: {endpoint}")


def get_pdf_api_config() -> Dict[str, Any]:
    """
    获取当前PDF API配置
    
    Returns:
        API配置字典
    """
    return _api_config.copy()


def is_pdf_api_configured() -> bool:
    """
    检查PDF API是否已配置
    
    Returns:
        是否已配置
    """
    return _api_config.get("pdf_extraction_endpoint") is not None


async def validate_pdf_file(file_path: str) -> Dict[str, Any]:
    """
    验证PDF文件是否符合要求
    
    Args:
        file_path: PDF文件路径
        
    Returns:
        验证结果
    """
    import os
    from pathlib import Path
    
    try:
        import asyncio
        from pathlib import Path
        file_path_obj = Path(file_path)
        
        # 使用异步方式检查文件是否存在
        file_exists = await asyncio.to_thread(file_path_obj.exists)
        if not file_exists:
            return {
                "valid": False,
                "error": "文件不存在"
            }
        
        # 检查文件扩展名
        if file_path_obj.suffix.lower() not in _api_config["supported_formats"]:
            return {
                "valid": False,
                "error": f"不支持的文件格式: {file_path_obj.suffix}"
            }
        
        # 使用异步方式检查文件大小
        file_stat = await asyncio.to_thread(file_path_obj.stat)
        file_size = file_stat.st_size
        if file_size > _api_config["max_file_size"]:
            return {
                "valid": False,
                "error": f"文件过大: {file_size} > {_api_config['max_file_size']}"
            }
        
        return {
            "valid": True,
            "file_size": file_size,
            "format": file_path_obj.suffix.lower()
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"文件验证失败: {str(e)}"
        }


def create_pdf_api_headers() -> Dict[str, str]:
    """
    创建PDF API请求头（基于提供的API示例）
    
    Returns:
        请求头字典
    """
    return {
        "accept": "application/json",  # 与示例一致
        "User-Agent": "LangGraph-PDF-Extractor/1.0"
        # Content-Type 会由 aiohttp 自动设置为 multipart/form-data
    }


def get_pdf_api_params() -> Dict[str, str]:
    """
    获取PDF API查询参数（基于提供的API示例）
    
    Returns:
        API查询参数字典
    """
    return {
        "parse_method": "auto",
        "is_json_md_dump": "false",
        "output_dir": "output",
        "return_layout": "false",
        "return_info": "false",
        "return_content_list": "false",
        "return_images": "false"
    }


def build_pdf_api_url(base_endpoint: str, custom_params: Optional[Dict[str, str]] = None) -> str:
    """
    构建完整的PDF API URL
    
    Args:
        base_endpoint: 基础端点URL（不包含查询参数）
        custom_params: 自定义参数（可选）
        
    Returns:
        完整的API URL
    """
    params = get_pdf_api_params()
    
    # 如果有自定义参数，覆盖默认参数
    if custom_params:
        params.update(custom_params)
    
    # 构建查询字符串
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    
    # 处理base_endpoint是否已经包含查询参数
    separator = "&" if "?" in base_endpoint else "?"
    
    return f"{base_endpoint}{separator}{query_string}"