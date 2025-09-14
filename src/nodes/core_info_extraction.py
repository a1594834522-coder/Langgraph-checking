"""
核心信息提取节点

从1-17项材料中分别提取各自的核心信息：
- 每项材料提取相应的关键字段
- 输出17个字段的结构化信息
- 支持AI增强的信息提取
"""

from typing import Dict, Any, Optional
from src.graph.state import AuditState
from src.tools.ai_utils import extract_core_information_with_ai, extract_category_core_info_with_ai


def core_info_extraction_node(state: AuditState) -> Dict[str, Any]:
    """
    完全无缓存的核心信息提取节点 - 每次都处理全新数据
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    """
    try:
        print(f"🎯 开始无缓存核心信息提取...")
        
        # 直接获取当前状态的数据 - 不使用任何缓存
        api_extraction_results = state.get("api_extraction_results", {})
        extracted_content = state.get("extracted_content", {})
        
        print(f"🔍 当前状态数据:")
        print(f"   API提取结果: {len(api_extraction_results)} 项")
        print(f"   备用提取内容: {len(extracted_content)} 项")
        
        # 确定使用哪个数据源 - 直接判断，不做缓存检查
        if api_extraction_results:
            data_source = api_extraction_results
            print(f"✅ 使用API提取结果: {len(api_extraction_results)} 项")
        elif extracted_content:
            data_source = extracted_content
            print(f"⚠️ 使用备用提取内容: {len(extracted_content)} 项")
        else:
            print("⚠️ 没有找到提取的内容，跳过核心信息提取")
            return {
                "core_info": _create_empty_core_info_structure(),
                "current_step": "core_info_extraction_skipped",
                "processing_logs": ["未找到有效数据，跳过核心信息提取"]
            }
        
        # 直接创建17项核心信息结构 - 不使用缓存
        core_info_structure = _create_empty_core_info_structure()
        
        # 1-17项材料分类映射
        material_categories = {
            "1.教育经历": "education",
            "教育经历": "education",
            "2.工作经历": "work_experience", 
            "工作经历": "work_experience",
            "3.继续教育(培训情况)": "continuing_education",
            "继续教育": "continuing_education",
            "培训情况": "continuing_education",
            "4.学术技术兼职情况": "academic_positions",
            "学术技术兼职情况": "academic_positions",
            "5.获奖情况": "awards",
            "获奖情况": "awards",
            "6.获得荣誉称号情况": "honors",
            "荣誉称号": "honors",
            "7.主持参与科研项目(基金)情况": "research_projects",
            "科研项目": "research_projects",
            "8.主持参与工程技术项目情况": "engineering_projects",
            "工程项目": "engineering_projects",
            "9.论文": "papers",
            "论文": "papers",
            "10.著(译)作(教材)": "publications",
            "著作": "publications",
            "教材": "publications",
            "11.专利(著作权)情况": "patents",
            "专利": "patents",
            "12.主持参与指定标准情况": "standards",
            "标准制定": "standards",
            "13.成果被批示、采纳、运用和推广情况": "achievements",
            "成果应用": "achievements",
            "14.资质证书": "certificates",
            "资质证书": "certificates",
            "15.奖惩情况": "rewards_punishments",
            "奖惩情况": "rewards_punishments",
            "16.考核情况": "evaluations",
            "考核情况": "evaluations",
            "17.申报材料附件信息": "attachments",
            "附件信息": "attachments"
        }
        
        print(f"📁 发现 {len(data_source)} 个材料类型需要提取核心信息")
        
        # 处理每个材料类型
        for folder_name, folder_data in data_source.items():
            print(f"🔍 正在处理: {folder_name}")
            
            # 确定材料类别
            category_key = None
            for key, category in material_categories.items():
                if key in folder_name or folder_name in key:
                    category_key = category
                    break
            
            if not category_key:
                print(f"⚠️ 未识别的材料类型: {folder_name}，归类为附件信息")
                category_key = "attachments"
            
            # 提取材料内容
            material_content = _extract_material_content_from_folder(folder_data)
            
            if not material_content.strip():
                print(f"⚠️ {folder_name} 没有有效内容")
                continue
                
            # 使用AI提取该材料类型的核心信息
            try:
                extracted_info = extract_category_core_info_with_ai(
                    category_key, folder_name, material_content
                )
                
                if extracted_info:
                    core_info_structure[category_key] = extracted_info
                    print(f"✅ {folder_name} 核心信息提取成功")
                else:
                    print(f"⚠️ {folder_name} 核心信息提取失败")
                    
            except Exception as e:
                print(f"⚠️ {folder_name} 信息提取异常: {e}")
                # 创建默认结构，保持数据一致性
                core_info_structure[category_key] = {
                    "name": None,
                    "id_number": None,
                    "extracted_from": [folder_name],
                    "content_summary": None,
                    "key_info": {
                        "category": category_key,
                        "folder_name": folder_name,
                        "error": str(e),
                        "extracted_at": _get_current_timestamp()
                    }
                }
                continue
        
        # 统计提取结果
        extracted_categories = []
        name_count = 0
        id_count = 0
        
        for category, info in core_info_structure.items():
            if info and info.get('name'):
                name_count += 1
            if info and info.get('id_number'):
                id_count += 1
            if info and (info.get('name') or info.get('id_number') or info.get('content_summary')):
                extracted_categories.append(category)
        
        print(f"✅ 核心信息提取完成:")
        print(f"   成功处理 {len(extracted_categories)} 项材料")
        print(f"   提取到姓名的材料: {name_count} 项")
        print(f"   提取到身份证号的材料: {id_count} 项")
        
        # 🚨 确保数据结构符合交叉校验节点的期望
        return {
            "core_info": core_info_structure,
            "current_step": "core_info_extraction_completed",
            "processing_logs": [
                f"核心信息提取完成: 成功处理{len(extracted_categories)}项材料",
                f"提取到姓名的材料: {name_count}项",
                f"提取到身份证号的材料: {id_count}项"
            ]
        }
        
    except Exception as e:
        print(f"❌ 核心信息提取失败: {str(e)}")
        # 🚨 即使失败也要返回有效的空结构，确保后续节点能正常处理
        return {
            "core_info": _create_empty_core_info_structure(),
            "current_step": "core_info_extraction_failed",
            "error_message": f"核心信息提取失败: {str(e)}",
            "processing_logs": [f"核心信息提取失败: {str(e)}"]
        }


def _create_empty_core_info_structure() -> Dict[str, Any]:
    """创建空的1-17项核心信息结构，每项都包含姓名和身份证号用于交叉校验"""
    # 为每一项材料创建相同的基础结构
    base_structure = {
        "name": None,           # 姓名（从该项材料中提取）
        "id_number": None,      # 身份证号（从该项材料中提取）
        "extracted_from": [],   # 信息来源文件
        "content_summary": None, # 内容摘要
        "key_info": {}          # 该项材料的关键信息
    }
    
    return {
        # 1-17项材料，每项都包含姓名和身份证号用于交叉校验
        "education": base_structure.copy(),         # 1.教育经历
        "work_experience": base_structure.copy(),   # 2.工作经历
        "continuing_education": base_structure.copy(),  # 3.继续教育(培训情况)
        "academic_positions": base_structure.copy(),    # 4.学术技术兼职情况
        "awards": base_structure.copy(),            # 5.获奖情况
        "honors": base_structure.copy(),            # 6.获得荣誉称号情况
        "research_projects": base_structure.copy(), # 7.主持参与科研项目(基金)情况
        "engineering_projects": base_structure.copy(),  # 8.主持参与工程技术项目情况
        "papers": base_structure.copy(),            # 9.论文
        "publications": base_structure.copy(),     # 10.著(译)作(教材)
        "patents": base_structure.copy(),           # 11.专利(著作权)情况
        "standards": base_structure.copy(),         # 12.主持参与指定标准情况
        "achievements": base_structure.copy(),      # 13.成果被批示、采纳、运用和推广情况
        "certificates": base_structure.copy(),      # 14.资质证书
        "rewards_punishments": base_structure.copy(),   # 15.奖惩情况
        "evaluations": base_structure.copy(),       # 16.考核情况
        "attachments": base_structure.copy()        # 17.申报材料附件信息
    }


def _extract_material_content_from_folder(folder_data: Any) -> str:
    """从文件夹数据中提取材料内容"""
    material_content = ""
    
    if isinstance(folder_data, list):
        # 处理api_extraction_results格式
        for json_item in folder_data:
            if isinstance(json_item, dict):
                content = json_item.get("content", {})
                if isinstance(content, dict):
                    # 尝试多种可能的内容字段
                    for key in ["md_content", "raw_markdown", "text", "content"]:
                        if key in content:
                            text_content = str(content[key])
                            if text_content.strip():
                                material_content += text_content + "\n\n"
                            break
                    if not material_content:
                        material_content += str(content) + "\n\n"
                else:
                    material_content += str(content) + "\n\n"
    
    elif isinstance(folder_data, dict):
        # 处理extracted_content格式
        content_list = folder_data.get("content", [])
        if isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, dict):
                    if "json_data" in item:
                        json_data = item["json_data"]
                        content = json_data.get("content", {})
                        if isinstance(content, dict):
                            for key in ["md_content", "raw_markdown", "text", "content"]:
                                if key in content:
                                    text_content = str(content[key])
                                    if text_content.strip():
                                        material_content += text_content + "\n\n"
                                    break
                        else:
                            material_content += str(content) + "\n\n"
                    elif "content" in item:
                        material_content += str(item["content"]) + "\n\n"
                    else:
                        material_content += str(item) + "\n\n"
    
    return material_content.strip()


def _get_current_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()