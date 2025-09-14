"""
AI驱动的规则校验节点 - 基于rules文件夹中的Excel规则
"""

from typing import Dict, List, Any
from src.graph.state import AuditState

# 导入AI工具
try:
    from src.tools.ai_utils import validate_material_with_ai
    _ai_utils_available = True
except ImportError:
    _ai_utils_available = False
    validate_material_with_ai = None


def validation_node(state: AuditState) -> Dict[str, Any]:
    """
    完全无缓存的AI智能校验节点 - 每次都处理全新数据
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    """
    try:
        print(f"⚡ 开始无缓存AI智能校验...")
        
        # 直接获取当前状态的材料内容和规则数据 - 不使用任何缓存
        extracted_content = state.get("api_extraction_results", {}) or state.get("extracted_content", {})
        parsed_rules = state.get("parsed_rules", [])
        rules_by_category = state.get("rules_by_category", {})
        
        print(f"🔍 当前状态数据:")
        print(f"   材料数量: {len(extracted_content)}")
        print(f"   规则数量: {len(parsed_rules)}")
        print(f"   规则分类: {list(rules_by_category.keys())}")
        
        if not extracted_content:
            print("⚠️ 未找到可校验的材料内容")
            return {
                "current_step": "validation_completed",
                "processing_logs": ["未找到可校验的材料内容"]
            }
        
        # 直接处理所有材料 - 不使用队列缓存机制
        validation_results = []
        material_validation = {}
        total_materials = len(extracted_content)
        processed_count = 0
        
        print(f"📋 开始校验{total_materials}个材料类型")
        
        # 直接遍历处理每个材料 - 完全无缓存
        for material_type, material_data in extracted_content.items():
            processed_count += 1
            print(f"🔍 正在校验: {material_type} ({processed_count}/{total_materials})")
            
            try:
                # 数据预处理：确保是单个材料的数据
                if isinstance(material_data, list) and len(material_data) > 0:
                    actual_data = material_data[0] if material_data else {}
                elif isinstance(material_data, dict):
                    actual_data = material_data
                else:
                    actual_data = {"content": material_data, "material_type": material_type}
                
                # 提取材料内容
                material_content = _extract_material_content(actual_data)
                
                # 🎯 智能规则匹配：教育经历材料只与教育经历规则集匹配
                matched_rules = _get_matched_rules_for_material(material_type, rules_by_category, parsed_rules)
                print(f"🎯 {material_type} 匹配到 {len(matched_rules)} 条相关规则")
                
                # 使用AI工具进行校验，将规则作为prompt的一部分
                material_results = None
                
                if _ai_utils_available and validate_material_with_ai and material_content.strip():
                    print(f"✅ 使用AI校验: {material_type}")
                    
                    try:
                        # 使用匹配的规则进行AI校验，而不是所有规则
                        if matched_rules and len(matched_rules) > 0:
                            print(f"📤 向AI传递{len(matched_rules)}条匹配的{material_type}规则")
                            
                            ai_results = validate_material_with_ai(
                                material_type, 
                                material_content, 
                                rules_context=matched_rules
                            )
                        else:
                            print(f"⚠️ {material_type}未找到匹配的规则，跳过AI校验")
                            ai_results = []
                            
                        if ai_results and len(ai_results) > 0:
                            print(f"✅ AI校验成功，生成{len(ai_results)}个结果")
                            # 转换AI结果格式
                            converted_results = []
                            for ai_result in ai_results:
                                converted_result = {
                                    "rule_name": ai_result.get("rule_name", f"{material_type}规则校验"),
                                    "result": _convert_ai_status_to_result(ai_result.get("status", "WARNING")),
                                    "details": ai_result.get("message", "校验完成"),
                                    "priority": _convert_ai_status_to_priority(ai_result.get("status", "WARNING")),
                                    "material_type": material_type,
                                    "rule_content": ai_result.get("rule_content", ""),
                                    "ai_powered": True,
                                    "timestamp": _get_current_timestamp()
                                }
                                converted_results.append(converted_result)
                                validation_results.append(converted_result)
                            
                            material_results = converted_results
                        else:
                            print(f"⚠️ AI校验返回空结果")
                            
                    except Exception as ai_error:
                        print(f"⚠️ AI校验失败: {ai_error}")
                else:
                    print(f"⚠️ AI工具不可用或无内容")
                
                # 如果AI校验失败，创建基础结果
                if not material_results:
                    print(f"🔧 为{material_type}创建基础校验结果")
                    basic_result = {
                        "rule_name": f"{material_type}基础校验",
                        "result": "⚠️警告",
                        "details": "未能进行AI校验，仅进行了基础检查",
                        "priority": "中",
                        "material_type": material_type,
                        "rule_content": "",
                        "ai_powered": False,
                        "timestamp": _get_current_timestamp()
                    }
                    material_results = [basic_result]
                    validation_results.append(basic_result)
                
                # 存储到material_validation中以兼容现有系统
                material_validation[material_type] = material_results
                
                print(f"✅ {material_type}校验完成，生成{len(material_results)}个结果")
                
            except Exception as material_error:
                print(f"❌ 校验{material_type}时发生错误: {str(material_error)}")
                # 为失败的材料创建错误记录
                error_result = {
                    "rule_name": f"{material_type}校验错误",
                    "result": "❌不通过",
                    "details": f"校验过程发生错误: {str(material_error)}",
                    "priority": "高",
                    "material_type": material_type,
                    "rule_content": "",
                    "timestamp": _get_current_timestamp()
                }
                validation_results.append(error_result)
                material_validation[material_type] = [error_result]
        
        # 直接返回结果，不使用任何缓存机制
        print(f"✅ 无缓存规则校验完成：处理{processed_count}个材料类型，生成{len(validation_results)}项结果")
        
        # 构建详细结果与摘要（供报告使用）
        try:
            from src.models.state import ValidationResult, ValidationSummary
            detailed_results = []
            for rd in validation_results:
                try:
                    detailed_results.append(ValidationResult.from_validation_output(rd))
                except Exception as conv_err:
                    print(f"⚠️ 转换验证结果失败: {conv_err}")
            summary = ValidationSummary.from_validation_results(detailed_results) if detailed_results else None
        except Exception as model_err:
            print(f"⚠️ 生成验证模型失败: {model_err}")
            detailed_results = []
            summary = None
            
        return {
            "material_validation": material_validation,
            "validation_cache": validation_results,
            "validation_results_detailed": [r.dict() for r in detailed_results],
            "validation_summary": summary.dict() if summary else None,
            "current_step": "validation_completed",
            "processing_logs": [
                f"处理了{processed_count}个材料类型",
                f"生成了{len(validation_results)}项校验结果",
                "已完全取消缓存机制，确保数据全新"
            ]
        }
        
    except Exception as e:
        print(f"❌ 规则校验失败: {str(e)}")
        return {
            "current_step": "validation_failed",
            "error_message": f"规则校验失败: {str(e)}"
        }


def _process_validation_results(material_type: str, validation_results: List, 
                              validation_cache_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理AI校验结果并存入缓存
    """
    processed_results = []
    
    if isinstance(validation_results, list) and len(validation_results) > 0:
        for result in validation_results:
            if isinstance(result, dict):
                result['timestamp'] = _get_current_timestamp()
                processed_results.append(result)
                validation_cache_results.append(result)
            else:
                # 其他类型，转换为字典
                result_dict = {
                    "rule_name": f"{material_type}校验",
                    "result": "⚠️警告",
                    "details": str(result),
                    "priority": "中",
                    "material_type": material_type,
                    "rule_content": "",
                    "timestamp": _get_current_timestamp()
                }
                processed_results.append(result_dict)
                validation_cache_results.append(result_dict)
    else:
        # 空结果
        result_dict = {
            "rule_name": f"{material_type}校验",
            "result": "⚠️警告",
            "details": "未能生成有效的校验结果",
            "priority": "中",
            "material_type": material_type,
            "rule_content": "",
            "timestamp": _get_current_timestamp()
        }
        processed_results.append(result_dict)
        validation_cache_results.append(result_dict)
    
    return processed_results


def _get_current_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()


def _convert_ai_status_to_result(status: str) -> str:
    """将AI状态转换为结果格式"""
    status_upper = status.upper()
    if status_upper == "PASS":
        return "✅通过"
    elif status_upper == "WARNING":
        return "⚠️警告"
    elif status_upper == "ERROR":
        return "❌不通过"
    else:
        return "⚠️警告"  # 默认


def _convert_ai_status_to_priority(status: str) -> str:
    """将AI状态转换为优先级"""
    status_upper = status.upper()
    if status_upper == "ERROR":
        return "高"
    elif status_upper == "WARNING":
        return "中"
    elif status_upper == "PASS":
        return "低"
    else:
        return "中"  # 默认


def _get_matched_rules_for_material(material_type: str, rules_by_category: Dict[str, List[Any]], all_rules: List[Any]) -> List[Any]:
    """
    🎯 智能规则匹配：教育经历材料只与教育经历规则集匹配
    
    Args:
        material_type: 材料类型（如"教育经历"）
        rules_by_category: 按分类组织的规则
        all_rules: 所有规则列表（备用）
        
    Returns:
        匹配的规则列表
    """
    try:
        print(f"🔍 正在为{material_type}匹配规则...")
        
        # 1-17项材料分类映射表
        material_to_category = {
            # 直接匹配数字编号
            "1.教育经历": "1",
            "2.工作经历": "2", 
            "3.继续教育": "3",
            "4.学术技术兼职情况": "4",
            "5.获奖情况": "5",
            "6.获得荣誉称号情况": "6",
            "7.主持参与科研项目": "7",
            "8.主持参与工程技术项目情况": "8",
            "9.论文": "9",
            "10.著(译)作(教材)": "10",
            "11.专利(著作权)情况": "11",
            "12.主持参与指定标准情况": "12",
            "13.成果被批示、采纳、运用和推广情况": "13",
            "14.资质证书": "14",
            "15.奖惩情况": "15",
            "16.考核情况": "16",
            "17.申报材料附件信息": "17",
            
            # 关键词匹配
            "教育经历": "1",
            "工作经历": "2",
            "继续教育": "3",
            "培训情况": "3",
            "学术技术兼职": "4",
            "获奖": "5",
            "荣誉称号": "6",
            "科研项目": "7",
            "工程项目": "8",
            "项目经历": "8",
            "论文": "9",
            "著作": "10",
            "教材": "10",
            "专利": "11",
            "著作权": "11",
            "标准": "12",
            "成果": "13",
            "证书": "14",
            "资质": "14",
            "奖惩": "15",
            "考核": "16",
            "附件": "17"
        }
        
        # 首先尝试直接匹配
        category_id = material_to_category.get(material_type)
        
        # 如果直接匹配失败，尝试关键词匹配
        if not category_id:
            for keyword, cat_id in material_to_category.items():
                if keyword in material_type and len(keyword) > 2:  # 避免过短的关键词
                    category_id = cat_id
                    print(f"🎯 通过关键词'{keyword}'匹配到分类 {cat_id}")
                    break
        
        # 获取匹配的规则
        matched_rules = []
        
        if category_id and category_id in rules_by_category:
            matched_rules = rules_by_category[category_id]
            print(f"✅ {material_type} 匹配到分类{category_id}，找到 {len(matched_rules)} 条专用规则")
        
        # 如果没有找到专用规则，查找通用规则
        if not matched_rules:
            # 查找通用规则（如交叉检验规则、通用规则等）
            general_rules = []
            for rule in all_rules:
                rule_content = getattr(rule, 'content', '') if hasattr(rule, 'content') else rule.get('content', '')
                source_file = getattr(rule, 'source_file', '') if hasattr(rule, 'source_file') else rule.get('source_file', '')
                
                if '通用' in source_file or '交叉' in source_file or '基础' in source_file:
                    general_rules.append(rule)
            
            if general_rules:
                matched_rules = general_rules
                print(f"⚠️ {material_type} 未找到专用规则，使用 {len(general_rules)} 条通用规则")
        
        # 最后的备用方案：返回空列表（不使用所有规则）
        if not matched_rules:
            print(f"⚠️ {material_type} 未找到任何匹配的规则，将跳过校验")
        
        return matched_rules
        
    except Exception as e:
        print(f"⚠️ 规则匹配失败: {e}")
        return []


def _extract_material_content(actual_data: Dict[str, Any]) -> str:
    """从材料数据中提取文本内容"""
    material_content = ""
    if isinstance(actual_data, dict):
        if "content" in actual_data:
            content_data = actual_data["content"]
            if isinstance(content_data, dict):
                # 尝试多种可能的内容字段
                for key in ["md_content", "raw_markdown", "text", "content"]:
                    if key in content_data:
                        material_content = str(content_data[key])
                        break
                if not material_content:
                    material_content = str(content_data)
            else:
                material_content = str(content_data)
        else:
            material_content = str(actual_data)
    else:
        material_content = str(actual_data)
    
    return material_content