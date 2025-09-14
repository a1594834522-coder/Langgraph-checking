"""
交叉校验节点

对核心信息进行交叉校验：
1. 姓名一致性校验
2. 身份证一致性校验
3. 基于rules文件夹中的交叉检验规则
"""

from typing import Dict, Any
from src.graph.state import AuditState
from src.tools.ai_utils import cross_validate_materials_with_ai


def cross_validation_node(state: AuditState) -> Dict[str, Any]:
    """
    完全无缓存的交叉校验节点 - 每次都处理全新数据
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    """
    try:
        print(f"🔍 开始无缓存交叉校验节点...")
        
        # 🔍 获取核心信息（优先使用核心信息提取节点的结果）
        core_info = state.get("core_info")
        all_extracted_info = state.get("api_extraction_results", {}) or state.get("extracted_content", {})
        current_step = state.get("current_step", "未知")
        
        print(f"🔍 当前状态详细信息:")
        print(f"   当前步骤: {current_step}")
        print(f"   核心信息状态: {'有效' if core_info else '无'}")
        print(f"   提取材料数量: {len(all_extracted_info)}")
        
        # 🚨 优先检查核心信息提取节点的结果
        if not core_info:
            print(f"⚠️ 没有找到核心信息，检查核心信息提取节点是否正常执行")
            raise Exception("未找到任何核心信息用于交叉校验")
        
        # 🔍 验证核心信息的数据结构
        if not isinstance(core_info, dict):
            print(f"⚠️ 核心信息格式不正确: {type(core_info)}")
            # 尝试转换为字典格式
            if hasattr(core_info, 'name') and hasattr(core_info, 'id_number'):
                core_info = {
                    "attachments": {
                        "name": getattr(core_info, 'name', ''),
                        "id_number": getattr(core_info, 'id_number', ''),
                        "extracted_from": getattr(core_info, 'extracted_from', [])
                    }
                }
            else:
                raise Exception(f"核心信息格式不可识别: {type(core_info)}")
        
        # 🔍 统计有效的核心信息条目
        valid_entries = 0
        name_sources = []
        id_sources = []
        
        for category, info in core_info.items():
            if isinstance(info, dict) and (info.get('name') or info.get('id_number')):
                valid_entries += 1
                if info.get('name'):
                    name_sources.append(f"{category}: {info['name']}")
                if info.get('id_number'):
                    id_sources.append(f"{category}: {info['id_number']}")
        
        print(f"📋 有效核心信息条目: {valid_entries}")
        print(f"📋 姓名信息来源: {len(name_sources)} 项")
        print(f"📋 身份证信息来源: {len(id_sources)} 项")
        
        if valid_entries == 0:
            print(f"⚠️ 所有核心信息条目都为空，无法进行交叉校验")
            raise Exception("所有核心信息条目都为空，无法进行交叉校验")
        
        # 🚨 直接执行交叉验证 - 不使用缓存，使用核心信息提取节点的结果
        cross_validation_results = cross_validate_materials_with_ai(all_extracted_info, core_info)
        
        # 直接转换AI结果为标准格式 - 不存入缓存
        converted_results = []
        for ai_result in cross_validation_results:
            status = ai_result.get('status', 'WARNING')
            if status == 'PASS' or '✅' in status:
                result_status = '✅通过'
            elif status == 'WARNING' or '⚠️' in status:
                result_status = '⚠️警告'
            elif status == 'ERROR' or '❌' in status:
                result_status = '❌不通过'
            else:
                result_status = '⚠️警告'
            
            converted_result = {
                "rule_name": ai_result.get('rule_name', '未知规则'),
                "result": result_status,
                "details": ai_result.get('message', 'AI交叉校验完成'),
                "priority": ai_result.get('priority', '极高'),
                "material_type": "AI交叉校验",
                "rule_content": ai_result.get('rule_content', ''),
                "timestamp": _get_current_timestamp()
            }
            converted_results.append(converted_result)
        
        # 🚨 直接返回结果，不使用任何缓存机制
        print(f"✅ 无缓存交叉校验完成，生成{len(converted_results)}项结果")
        
        return {
            "cross_validation": converted_results,
            "current_step": "cross_validation_completed",
            "processing_logs": [
                f"交叉校验完成，生成{len(converted_results)}项结果",
                f"基于{valid_entries}项有效核心信息进行校验",
                "已完全取消缓存机制，确保数据全新"
            ]
        }
        
    except Exception as e:
        print(f"❌ 交叉校验失败: {str(e)}")
        return {
            "current_step": "cross_validation_failed",
            "error_message": f"交叉校验失败: {str(e)}",
            "processing_logs": [f"交叉校验失败: {str(e)}"]
        }


def _get_current_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()