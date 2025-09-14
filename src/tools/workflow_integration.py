"""
审核工作流集成工具

提供审核系统的核心集成函数，连接各个工具模块
"""

from typing import List, Dict, Any
from pathlib import Path
from src.models.state import ValidationResult, CoreInfo
from src.tools import (
    extract_core_information_with_ai,
    validate_material_with_ai,
    extract_with_regex
)

def extract_core_information_from_json(json_extractions: List[Dict[str, Any]]) -> CoreInfo:
    """使用Gemma AI从JSON提取结果中智能提取核心信息"""
    print("🤖 使用Gemma模型进行智能信息提取...")
    
    # 整合所有文档内容
    combined_content = ""
    extracted_from = []
    
    for json_extraction in json_extractions:
        file_path = json_extraction.get("file_path", "")
        content_blocks = json_extraction.get("content_blocks", [])
        
        for block in content_blocks:
            content = block.get("content", "")
            if content.strip():
                combined_content += content + "\n"
        
        if file_path:
            extracted_from.append(Path(file_path).name)
    
    if not combined_content.strip():
        return CoreInfo(name="", id_number="", extracted_from=extracted_from)
    
    # 使用AI提取，失败时降级到正则表达式
    ai_result = extract_core_information_with_ai(combined_content, extracted_from)
    
    if ai_result:
        return CoreInfo(
            name=ai_result["name"],
            id_number=ai_result["id_number"],
            extracted_from=ai_result["extracted_from"]
        )
    else:
        name, id_number = extract_with_regex(combined_content)
        return CoreInfo(name=name, id_number=id_number, extracted_from=extracted_from)

def extract_core_information(materials: List[Dict[str, Any]]) -> CoreInfo:
    """提取核心信息（简化版） - 使用Dict替代MaterialInfo"""
    # 将Dict转换为JSON格式进行处理
    json_extractions = []
    for material in materials:
        json_extraction = {
            "file_path": material.get("material_id", ""),
            "content_blocks": [{"content": material.get("content", "")}]
        }
        json_extractions.append(json_extraction)
    
    return extract_core_information_from_json(json_extractions)

def validate_material_rules(material: Dict[str, Any]) -> List[ValidationResult]:
    """使用Gemma AI进行智能审核 - 使用Dict替代MaterialInfo"""
    material_type = material.get("material_type", "")
    content = material.get("content", "")
    
    print(f"🤖 使用Gemma模型审核材料: {material_type}")
    
    # 使用AI进行智能审核
    ai_results = validate_material_with_ai(material_type, content)
    
    if ai_results:
        results = []
        for item in ai_results:
            if isinstance(item, dict) and "rule_name" in item:
                results.append(ValidationResult(
                    rule_id=f"GEMMA_{len(results)+1:03d}",
                    rule_name=item.get("rule_name", "智能审核"),
                    status=item.get("status", "WARNING"),
                    message=item.get("message", "审核完成")
                ))
        return results
    else:
        # AI失败时返回默认验证结果
        return [ValidationResult(
            rule_id="FALLBACK_001",
            rule_name="默认审核",
            status="WARNING",
            message="AI审核失败，使用默认审核规则"
        )]

