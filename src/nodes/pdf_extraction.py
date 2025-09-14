"""
PDF内容提取节点

通过FastAPI接口处理PDF文件内容提取并转换为JSON格式
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

try:
    import aiohttp  # type: ignore[import]
    from aiohttp import ClientTimeout  # type: ignore[import]
except ImportError:
    print("Warning: aiohttp not installed. Please install with: pip install aiohttp")
    aiohttp = None  # type: ignore
    ClientTimeout = None  # type: ignore

try:
    from ..graph.state import AuditState
except ImportError:
    from src.graph.state import AuditState

logger = logging.getLogger(__name__)


async def extract_pdf_via_api(pdf_file_path: str, api_endpoint: str) -> Dict[str, Any]:
    """
    通过FastAPI提取PDF内容为JSON
    
    基于用户提供的工作案例，使用aiohttp实现类似requests的参数传递方式：
    - 基础URL和查询参数分开处理
    - 逐个上传PDF文件（不是压缩包）
    - 使用multipart/form-data格式
    
    Args:
        pdf_file_path: PDF文件路径
        api_endpoint: API端点URL（不包含查询参数）
        
    Returns:
        提取的JSON内容
    """
    if aiohttp is None:
        return {
            "success": False,
            "error": "aiohttp库未安装，请使用 pip install aiohttp 安装",
            "file_path": pdf_file_path
        }
    
    try:
        # 按照用户案例的方式设置参数
        params = {
            'parse_method': 'auto',
            'is_json_md_dump': 'false',
            'output_dir': 'output',
            'return_layout': 'false',
            'return_info': 'false',
            'return_content_list': 'false',
            'return_images': 'false'
        }
        
        # 创建请求头
        headers = {
            "accept": "application/json",
            "User-Agent": "LangGraph-PDF-Extractor/1.0"
        }
        
        print(f"📤 正在上传PDF文件: {Path(pdf_file_path).name} 到 {api_endpoint}")
        
        async with aiohttp.ClientSession() as session:
            # 异步读取文件内容
            try:
                file_content = await asyncio.to_thread(lambda: open(pdf_file_path, 'rb').read())
            except Exception as file_error:
                error_msg = f"读取PDF文件失败: {str(file_error)}"
                print(f"❌ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "file_path": pdf_file_path,
                    "api_endpoint": api_endpoint
                }
            
            # 按照用户案例创建文件数据
            data = aiohttp.FormData()
            data.add_field(
                'pdf_file',  # 与用户案例中的字段名一致
                file_content, 
                filename=Path(pdf_file_path).name, 
                content_type='application/pdf'
            )
            
            # 使用params参数传递查询参数，类似requests.post(url, params=params, files=files)
            # 创建超时设置
            timeout = ClientTimeout(total=120) if ClientTimeout else aiohttp.ClientTimeout(total=120)
            
            async with session.post(
                api_endpoint, 
                params=params,  # 查询参数单独传递
                data=data,      # 文件数据
                headers=headers, 
                timeout=timeout
            ) as response:
                print(f"📊 API响应状态码: {response.status}")
                
                if response.status == 200:
                    try:
                        result = await response.json()
                        print(f"✅ 成功提取PDF内容: {Path(pdf_file_path).name}")
                        print(f"📋 API返回结构: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                        return {
                            "success": True,
                            "content": result,
                            "file_path": pdf_file_path,
                            "api_endpoint": str(response.url),
                            "extraction_timestamp": None
                        }
                    except Exception as json_error:
                        error_text = await response.text()
                        print(f"⚠️ API返回非JSON格式: {json_error}")
                        return {
                            "success": False,
                            "error": f"API返回非JSON格式: {json_error}",
                            "error_details": error_text[:500],
                            "file_path": pdf_file_path,
                            "api_endpoint": str(response.url)
                        }
                else:
                    error_text = await response.text()
                    print(f"❌ API返回错误状态码 {response.status}: {error_text[:200]}...")
                    return {
                        "success": False,
                        "error": f"API返回错误状态码: {response.status}",
                        "error_details": error_text,
                        "file_path": pdf_file_path,
                        "api_endpoint": str(response.url)
                    }
                        
    except FileNotFoundError:
        error_msg = f"找不到PDF文件: {pdf_file_path}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "file_path": pdf_file_path,
            "api_endpoint": api_endpoint
        }
    except Exception as e:
        error_msg = f"API调用失败: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "file_path": pdf_file_path,
            "api_endpoint": api_endpoint
        }


async def pdf_extraction_node(state: AuditState) -> Dict[str, Any]:
    """
    完全无缓存的PDF内容提取节点 - 每次都处理全新数据
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    """
    try:
        print(f"📄 开始无缓存PDF内容提取...")
        
        # 直接获取当前状态的文件夹数据 - 不使用任何缓存
        folder_validation = state.get("folder_validation", {})
        
        print(f"🔍 当前状态数据:")
        print(f"   文件夹验证结果: {len(folder_validation.get('folders_found', []))} 个文件夹")
        
        # 验证数据有效性
        if not folder_validation or not folder_validation.get("folders_found"):
            print("⚠️ 未找到有效的文件夹结构数据")
            return {
                "current_step": "pdf_extraction_failed",
                "error_message": "没有找到有效的文件夹结构",
                "processing_logs": ["没有找到有效的文件夹结构"]
            }
        
        # 获取PDF API端点配置
        api_endpoint = state.get("pdf_api_endpoint")
        if not api_endpoint:
            # 尝试使用默认配置
            api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
            print(f"⚠️ 状态中未配置PDF API端点，使用默认端点: {api_endpoint}")
            
            # 检查是否有配置文件
            try:
                from src.config.api_config import get_pdf_api_config
                api_config = get_pdf_api_config()
                configured_endpoint = api_config.get("pdf_extraction_endpoint")
                if configured_endpoint:
                    api_endpoint = configured_endpoint
                    print(f"✅ 从配置文件获取到API端点: {api_endpoint}")
            except ImportError:
                print("⚠️ 无法导入API配置模块，使用硬编码默认端点")
            except Exception as e:
                print(f"⚠️ 读取API配置失败: {e}，使用硬编码默认端点")
                
            # 如果仍然没有API端点，返回错误
            if not api_endpoint:
                return {
                    "current_step": "pdf_extraction_failed",
                    "error_message": "未配置PDF提取API端点，请检查配置文件或环境变量"
                }
        
        folders_found = folder_validation["folders_found"]
        pdf_extraction_results = {}
        api_extraction_results = {}
        total_pdf_files = 0
        successful_extractions = 0
        
        # 处理每个标准文件夹中的PDF文件
        for folder_info in folders_found:
            folder_name = folder_info["name"]
            folder_path = folder_info["path"]
            
            print(f"📁 处理文件夹: {folder_name}")
            
            # 查找文件夹中的PDF文件（异步方式）
            folder_path_obj = Path(folder_path)
            
            # 使用asyncio.to_thread来异步执行文件系统操作
            try:
                pdf_files = await asyncio.to_thread(lambda: list(folder_path_obj.glob("*.pdf")))
            except Exception as glob_error:
                print(f"❌ 扫描文件夹 {folder_name} 时发生错误: {str(glob_error)}")
                pdf_extraction_results[folder_name] = {
                    "files": [],
                    "folder_path": folder_path,
                    "material_type": folder_name,
                    "pdf_files_count": 0,
                    "status": "error",
                    "error": str(glob_error)
                }
                continue
            
            if not pdf_files:
                print(f"⚠️ 文件夹 {folder_name} 中没有找到PDF文件")
                pdf_extraction_results[folder_name] = {
                    "files": [],
                    "folder_path": folder_path,
                    "material_type": folder_name,
                    "pdf_files_count": 0,
                    "status": "empty"
                }
                continue
            
            total_pdf_files += len(pdf_files)
            folder_results = []
            
            # 使用asyncio并发处理PDF文件提取
            tasks = []
            for pdf_file in pdf_files:
                task = extract_pdf_via_api(str(pdf_file), api_endpoint)
                tasks.append(task)
            
            # 并发执行API调用
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for pdf_file, result in zip(pdf_files, results):
                if isinstance(result, Exception):
                    print(f"❌ 处理文件 {pdf_file.name} 时发生异常: {str(result)}")
                    folder_results.append({
                        "file_name": pdf_file.name,
                        "file_path": str(pdf_file),
                        "success": False,
                        "error": str(result),
                        "material_type": folder_name
                    })
                elif isinstance(result, dict) and result.get("success"):
                    print(f"✅ 成功提取 {pdf_file.name}")
                    successful_extractions += 1
                    
                    # 异步获取文件大小
                    try:
                        file_size = await asyncio.to_thread(lambda: pdf_file.stat().st_size)
                    except Exception as stat_error:
                        print(f"⚠️ 获取文件大小失败: {stat_error}")
                        file_size = 0
                    
                    # 构建标准化JSON格式
                    standardized_json = {
                        "metadata": {
                            "file_name": pdf_file.name,
                            "file_path": str(pdf_file),
                            "size_bytes": file_size,
                            "material_type": folder_name,
                            "extraction_method": "api"
                        },
                        "content": result.get("content", {}),
                        "validation": {
                            "is_valid": True,
                            "api_endpoint": api_endpoint,
                            "extraction_timestamp": result.get("extraction_timestamp")
                        }
                    }
                    
                    folder_results.append({
                        "file_name": pdf_file.name,
                        "file_path": str(pdf_file),
                        "success": True,
                        "json_data": standardized_json,
                        "json_string": json.dumps(standardized_json, ensure_ascii=False, indent=2),
                        "format": "strict_json",
                        "size": len(json.dumps(standardized_json)),
                        "material_type": folder_name
                    })
                    
                    # 存储API提取结果
                    if folder_name not in api_extraction_results:
                        api_extraction_results[folder_name] = []
                    api_extraction_results[folder_name].append(standardized_json)
                    
                else:
                    # 处理失败的情况
                    error_msg = "未知错误"
                    if isinstance(result, dict):
                        error_msg = result.get("error", "未知错误")
                    print(f"❌ 提取失败 {pdf_file.name}: {error_msg}")
                    folder_results.append({
                        "file_name": pdf_file.name,
                        "file_path": str(pdf_file),
                        "success": False,
                        "error": error_msg,
                        "material_type": folder_name
                    })
            
            pdf_extraction_results[folder_name] = {
                "files": folder_results,
                "folder_path": folder_path,
                "material_type": folder_name,
                "pdf_files_count": len(pdf_files),
                "successful_count": len([r for r in folder_results if r.get("success")]),
                "status": "success" if folder_results else "empty"
            }
        
        success_folders = sum(1 for item in pdf_extraction_results.values() 
                            if item.get("status") in ["success", "empty"])  # 包括空文件夹
        total_folders = len(pdf_extraction_results)
        
        print(f"✅ PDF内容提取完成: {success_folders}/{total_folders}个文件夹，{successful_extractions}/{total_pdf_files}个PDF文件提取成功")
        
        # 即使没有PDF文件，只要有文件夹结构就认为成功
        if total_folders > 0:
            return {
                "pdf_extraction_results": pdf_extraction_results,
                "api_extraction_results": api_extraction_results,
                "extracted_content": api_extraction_results,  # 保持兼容性
                "current_step": "pdf_extraction_completed",
                "processing_stats": {
                    "total_folders": total_folders,
                    "successful_folders": success_folders,
                    "total_pdf_files": total_pdf_files,
                    "successful_extractions": successful_extractions,
                    "extraction_rate": successful_extractions / total_pdf_files if total_pdf_files > 0 else 0
                }
            }
        else:
            return {
                "current_step": "pdf_extraction_failed",
                "error_message": "未找到可处理的文件夹"
            }
        
    except Exception as e:
        logger.error(f"PDF内容提取失败: {str(e)}")
        print(f"❌ PDF内容提取失败: {str(e)}")
        return {
            "current_step": "pdf_extraction_failed",
            "error_message": f"PDF内容提取失败: {str(e)}"
        }


def configure_pdf_api_endpoint(state: AuditState, api_endpoint: str) -> Dict[str, Any]:
    """
    配置PDF提取API端点
    
    Args:
        state: 当前状态
        api_endpoint: API端点URL
        
    Returns:
        更新的状态
    """
    return {
        "pdf_api_endpoint": api_endpoint,
        "processing_logs": [f"已配置PDF提取API端点: {api_endpoint}"]
    }