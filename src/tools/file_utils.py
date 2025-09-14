"""
文件处理工具

提供文件处理相关的工具函数：
- ZIP文件解压
- 17个标准文件夹结构验证
- Markdown文件处理
- 文件路径处理
"""

import zipfile
import re
import markdown
from pathlib import Path
from typing import List, Dict, Any, Optional

async def extract_zip_file(zip_path: str) -> Dict[str, Any]:
    """
    解压ZIP文件并返回解压结果
    
    Args:
        zip_path: ZIP文件路径
        
    Returns:
        解压结果字典，包含解压路径和文件列表
    """
    try:
        import asyncio
        
        # 使用异步方式处理ZIP文件
        def _extract_zip():
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 解压到当前目录的 extracted 文件夹
                extract_dir = Path(zip_path).parent / "extracted"
                extract_dir.mkdir(exist_ok=True)
                
                zip_ref.extractall(extract_dir)
                
                # 收集所有解压的文件
                extracted_files = []
                import os
                # 使用os.walk代替rglob来避免阻塞调用
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        extracted_files.append(file_path)
                return extract_dir, extracted_files
        
        extract_dir, extracted_files = await asyncio.to_thread(_extract_zip)
        
        return {
            "extraction_path": str(extract_dir),
            "files": extracted_files,
            "success": True
        }
    
    except Exception as e:
        print(f"解压失败: {e}")
        return {
            "extraction_path": None,
            "files": [],
            "success": False,
            "error": str(e)
        }

async def validate_folder_structure(extraction_path: str) -> Dict[str, Any]:
    """
    验证17个标准文件夹结构
    
    支持文件夹在根目录或下一层子目录中
    
    Args:
        extraction_path: 解压后的根目录路径
        
    Returns:
        验证结果字典
    """
    # 17个标准文件夹名称
    standard_folders = [
        "1.教育经历",
        "2.工作经历",
        "3.继续教育(培训情况)",
        "4.学术技术兼职情况",
        "5.获奖情况",
        "6.获得荣誉称号情况",
        "7.主持参与科研项目(基金)情况",
        "8.主持参与工程技术项目情况",
        "9.论文",
        "10.著(译)作(教材)",
        "11.专利(著作权)情况",
        "12.主持参与指定标准情况",
        "13.成果被批示、采纳、运用和推广情况",
        "14.资质证书",
        "15.奖惩情况",
        "16.考核情况",
        "17.申报材料附件信息"
    ]
    
    extraction_dir = Path(extraction_path)
    
    # 递归查找17个标准文件夹（在根目录或下一层子目录中）
    async def find_folders_recursively(search_dir: Path, max_depth: int = 2) -> Dict[str, str]:
        """
        递归查找标准文件夹
        
        Args:
            search_dir: 搜索目录
            max_depth: 最大搜索深度（1=仅根目录，2=根目录+一层子目录）
            
        Returns:
            找到的文件夹映射 {文件夹名: 路径}
        """
        found_folders = {}
        
        async def _search_directory(current_dir: Path, current_depth: int):
            if current_depth > max_depth:
                return
                
            try:
                # 使用异步方式读取目录 - 使用os.scandir避免阻塞
                import asyncio
                import os
                
                try:
                    # 使用asyncio.to_thread包装os.scandir调用
                    def _list_directory():
                        return list(os.scandir(current_dir))
                    
                    entries = await asyncio.to_thread(_list_directory)
                    
                    for entry in entries:
                        # 检查是否是目录
                        def _check_is_dir():
                            return entry.is_dir()
                        
                        if await asyncio.to_thread(_check_is_dir):
                            folder_name = entry.name
                            # 检查是否是标准文件夹
                            if folder_name in standard_folders and folder_name not in found_folders:
                                found_folders[folder_name] = str(entry.path)
                                print(f"📁 找到标准文件夹: {folder_name} -> {entry.path}")
                            
                            # 如果还没达到最大深度，继续递归搜索
                            if current_depth < max_depth:
                                from pathlib import Path
                                await _search_directory(Path(entry.path), current_depth + 1)
                except OSError as e:
                    print(f"⚠️ 无法扫描目录 {current_dir}: {e}")
            except PermissionError:
                print(f"⚠️ 无法访问目录: {current_dir}")
                
        await _search_directory(search_dir, 1)
        return found_folders
    
    print(f"🔍 开始递归查找17个标准文件夹（最大深度2层）...")
    found_folder_paths = await find_folders_recursively(extraction_dir, max_depth=2)
    
    # 构建文件夹信息
    folders_found = []
    missing_folders = []
    
    for standard_folder in standard_folders:
        if standard_folder in found_folder_paths:
            folders_found.append({
                "name": standard_folder,
                "path": found_folder_paths[standard_folder],
                "exists": True
            })
        else:
            missing_folders.append(standard_folder)
    
    # 获取所有实际存在的文件夹（用于检查额外文件夹）
    import asyncio
    import os
    all_actual_folders = []
    
    async def collect_folders():
        # 使用os.walk代替rglob来避免阻塞调用
        def _walk_dirs():
            folders = []
            for root, dirs, files in os.walk(extraction_dir):
                for dir_name in dirs:
                    folders.append(dir_name)
            return folders
        
        folder_names = await asyncio.to_thread(_walk_dirs)
        all_actual_folders.extend(folder_names)
    
    await collect_folders()
    
    # 检查额外的文件夹
    extra_folders = []
    for actual_folder in set(all_actual_folders):
        if actual_folder not in standard_folders:
            extra_folders.append(actual_folder)
    
    # 判断是否合规
    is_valid = len(missing_folders) == 0
    
    print(f"📊 文件夹验证结果: 找到 {len(folders_found)}/{len(standard_folders)} 个标准文件夹")
    if missing_folders:
        print(f"⚠️ 缺失的文件夹: {missing_folders}")
    
    return {
        "is_valid": is_valid,
        "folders_found": folders_found,
        "missing_folders": missing_folders,
        "extra_folders": extra_folders,
        "total_standard_folders": len(standard_folders),
        "found_count": len(folders_found)
    }


def analyze_markdown_structure(md_content: str) -> Dict[str, Any]:
    """
    分析Markdown文件结构
    
    Args:
        md_content: Markdown内容
        
    Returns:
        结构分析结果
    """
    import datetime
    
    try:
        # 基本统计信息
        lines = md_content.split('\n')
        
        # 提取标题
        headers = []
        for line in lines:
            if line.strip().startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.strip('#').strip()
                headers.append({
                    "level": level,
                    "title": title
                })
        
        # 提取列表项
        list_items = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('-') or stripped.startswith('*') or re.match(r'^\d+\.', stripped):
                list_items.append(stripped)
        
        return {
            "total_lines": len(lines),
            "total_chars": len(md_content),
            "headers": headers,
            "list_items": list_items,
            "has_content": len(md_content.strip()) > 0,
            "extraction_timestamp": datetime.datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "total_lines": 0,
            "total_chars": 0,
            "headers": [],
            "list_items": [],
            "has_content": False,
            "error": str(e)
        }


async def extract_markdown_content(md_file_path: str) -> Dict[str, Any]:
    """
    提取Markdown文件内容
    
    Args:
        md_file_path: Markdown文件路径
        
    Returns:
        提取结果
    """
    try:
        import asyncio
        # 使用异步方式读取文件
        def _read_file():
            with open(md_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        content = await asyncio.to_thread(_read_file)
        
        structure = analyze_markdown_structure(content)
        
        return {
            "file_path": md_file_path,
            "content": content,
            "structure": structure,
            "success": True
        }
        
    except Exception as e:
        return {
            "file_path": md_file_path,
            "content": "",
            "structure": {},
            "success": False,
            "error": str(e)
        }