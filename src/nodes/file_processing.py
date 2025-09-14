"""
ZIP解压节点

专门处理ZIP压缩包解压和17个标准文件夹结构验证
"""

from typing import Dict, Any
from pathlib import Path
from src.graph.state import AuditState
from src.tools import (
    extract_zip_file,
    validate_folder_structure
)


async def file_processing_node(state: AuditState) -> Dict[str, Any]:
    """
    ZIP解压节点 - 解压ZIP文件并验证17个标准文件夹结构
    """
    try:
        # 支持两种输入字段名（向后兼容）
        zip_path = state.get("uploaded_file") or state.get("zip_file_path")
        
        if not zip_path:
            return {
                "current_step": "zip_extraction_failed",
                "error_message": "未找到上传的ZIP文件路径"
            }
        
        print(f"📦 开始解压ZIP文件: {Path(zip_path).name}")
        
        # 解压 ZIP 文件
        extraction_result = await extract_zip_file(zip_path)
        
        if not extraction_result:
            return {
                "current_step": "zip_extraction_failed",
                "error_message": "ZIP文件解压失败"
            }
        
        # 获取解压后的根目录
        extraction_path = extraction_result.get("extraction_path")
        extracted_files = extraction_result.get("files", [])
        
        # 检查解压是否成功
        if not extraction_path:
            return {
                "current_step": "zip_extraction_failed",
                "error_message": "ZIP文件解压失败，无法获取解压路径"
            }
        
        print(f"📁 ZIP解压完成，提取到: {extraction_path}")
        print(f"📊 共解压 {len(extracted_files)} 个文件")
        
        # 验证17个标准文件夹结构
        folder_validation = await validate_folder_structure(extraction_path)
        
        return {
            "extraction_path": extraction_path,
            "extracted_files": extracted_files,
            "folder_validation": folder_validation,
            "current_step": "zip_extraction_completed",
            "file_type": "zip"
        }
        
    except Exception as e:
        print(f"❌ ZIP解压失败: {str(e)}")
        return {
            "current_step": "zip_extraction_failed",
            "error_message": f"ZIP解压失败: {str(e)}"
        }