"""
AI模型工具

提供AI模型相关的工具函数：
- Gemma模型懒加载和调用
- 智能信息提取
- 智能规则审核
- 结构化输出处理
"""

import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()  # 加载 .env 文件
except ImportError:
    pass  # 如果没有 python-dotenv，忽略

# Google Gemini AI 模型配置
_gemini_client = None

def _get_gemini_client():
    """懒加载Google Gemini客户端"""
    global _gemini_client
    if _gemini_client is None:
        try:
            import google.generativeai as genai  # type: ignore
            
            # 从环境变量获取API Key
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key or api_key == 'your_google_api_key_here':
                raise Exception("未配置有效的GOOGLE_API_KEY，请设置环境变量GOOGLE_API_KEY")
                return None
            
            # 配置API Key
            genai.configure(api_key=api_key)  # type: ignore
            _gemini_client = genai
            
            # 获取并显示模型配置
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
            print(f"✅ Google Gemini客户端初始化成功（使用google-generativeai包）")
            print(f"🤖 配置的模型: {model_name}")
            
        except ImportError:
            raise Exception("google-generativeai包未安装，请运行: pip install google-generativeai")
        except Exception as e:
            raise Exception(f"Gemini客户端初始化失败: {e}")
    
    return _gemini_client

def generate_with_gemini(prompt: str, max_tokens: int = 1000) -> str:
    """使用Google Gemini生成文本（基于google-generativeai API）"""
    try:
        client = _get_gemini_client()
        if client is None:
            raise Exception("Gemini客户端未可用")
        
        # 从环境变量获取模型名称，默认使用 gemini-2.5-flash
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        print(f"🤖 使用模型: {model_name}")
        
        # 使用google-generativeai API格式
        model = client.GenerativeModel(model_name)  # type: ignore
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text.strip()
        else:
            raise Exception("Gemini返回了空响应")
            
    except Exception as e:
        raise Exception(f"Gemini生成失败: {e}")

def extract_core_information_with_ai(combined_content: str, extracted_from: List[str]) -> Dict[str, Any]:
    """
    使用AI提取核心信息（优先使用Gemini，失败时降级到正则匹配）
    """
    try:
        print("🤖 尝试使用Gemini AI提取核心信息...")
        
        # 尝试使用Gemini AI
        client = _get_gemini_client()
        if client is not None:
            prompt = f"""
请从以下文档内容中提取核心信息。请严格按照JSON格式返回，只返回JSON，不要其他说明文字：

{{"name": "姓名", "id_number": "身份证号码"}}

要求：
- 姓名：提取中文姓名（2-4个汉字）
- 身份证号码：提取18位身份证号（17位数字+最后一位数字或X）
- 如果找不到对应信息，请填写空字符串
- 注意：只从当前文档中提取，不要推测或使用其他信息

文档内容：
{combined_content[:1000]}  # 限制长度避免超出token限制
"""
            
            ai_response = generate_with_gemini(prompt, max_tokens=200)
            if ai_response:
                try:
                    import json
                    # 尝试解析JSON响应
                    if '{' in ai_response and '}' in ai_response:
                        json_start = ai_response.find('{')
                        json_end = ai_response.rfind('}') + 1
                        json_str = ai_response[json_start:json_end]
                        result = json.loads(json_str)
                        
                        name = result.get('name', '').strip()
                        id_number = result.get('id_number', '').strip()
                        
                        # 验证结果
                        if name and len(name) >= 2 and len(name) <= 4:
                            if not id_number or re.match(r'^\d{17}[\dX]$', id_number):
                                print(f"✅ Gemini AI提取成功: 姓名='{name}', 身份证='{id_number}'")
                                return {"name": name, "id_number": id_number, "extracted_from": extracted_from}
                except Exception as e:
                    print(f"⚠️ 解析Gemini响应失败: {e}")
        
        # AI失败时抛出异常
        raise Exception("AI提取失败，无法获取核心信息")
        
    except Exception as e:
        raise Exception(f"AI提取异常: {e}")

def validate_material_with_ai(material_type: str, content: str, rules_context: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """
    材料智能审核 - 完全无缓存，基于真实规则的AI校验
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    
    Args:
        material_type: 材料类型
        content: 材料内容
        rules_context: 规则上下文列表，必须提供
    
    Returns:
        审核结果列表
        
    Raises:
        Exception: 当AI不可用或规则无效时直接抛出异常（禁用模拟模式）
    """
    try:
        print(f"🤖 开始AI审核{material_type}...")
        
        # 验证必需参数
        if not rules_context or len(rules_context) == 0:
            raise Exception(f"没有提供审核规则，无法进行{material_type}审核")
        
        # 获取Gemini AI客户端
        client = _get_gemini_client()
        if client is None:
            raise Exception("Gemini AI客户端不可用，无法进行AI审核")
        
        # 构建规则上下文 - 完全无缓存处理
        print(f"📋 使用{len(rules_context)}条规则进行AI校验")
        rules_section = "\n\n审核规则上下文：\n"
        valid_rule_count = 0
        
        for i, rule in enumerate(rules_context, 1):  # 🚨 移除规则数量限制，处理所有规则
            # 根据规范：统一使用'content'字段，不再使用兼容性代码
            if hasattr(rule, 'content'):
                # RuleInfo对象
                rule_content = rule.content
                rule_id = rule.rule_id
                source_file = rule.source_file
                priority = rule.priority
            else:
                # 字典格式 - 只使用'content'字段
                rule_content = rule.get('content', '')
                rule_id = rule.get('rule_id', f'rule_{i}')
                source_file = rule.get('source_file', '未知来源')
                priority = rule.get('priority', 'normal')
            
            # 验证规则内容
            if rule_content and rule_content.strip():
                rules_section += f"{i}. [{rule_id}] (来源: {source_file}, 优先级: {priority}): {rule_content[:200]}\n"
                print(f"📋 正在传递规则{i}: {rule_content[:50]}...")  # 调试信息
                valid_rule_count += 1
            else:
                print(f"⚠️ 规则{i} [{rule_id}] 内容为空！")
        
        if valid_rule_count == 0:
            raise Exception(f"所有{len(rules_context)}条规则内容都为空，无法进行{material_type}审核")
        
        rules_section += f"\n共找到 {valid_rule_count} 条有效规则，请根据以上规则进行精确校验\n"
        print(f"✅ 有效规则数量: {valid_rule_count}/{len(rules_context)}")
                
                    
        # 构建基于真实规则的prompt
        prompt = f"""
你是一个专业的职称评审材料审核专家。请根据以下具体规则对{material_type}材料进行严格审核。

{rules_section}

请仔细阅读上述每一条规则，并逐一检查材料内容是否符合要求。

材料内容：
{content[:9999]}

请严格按照以下 JSON 格式返回审核结果，只返回 JSON 数组，不要其他说明文字：

[
  {{
    "rule_name": "具体规则名称或ID",
    "status": "PASS/WARNING/ERROR",
    "message": "详细的审核结果说明，包含具体问题或通过原因",
    "rule_content": "应用的规则内容摘要"
  }}
]

注意：
1. 必须逐一检查每条规则
2. status 只能是 PASS、WARNING 或 ERROR 中的一个
3. message 必须具体明确，说明检查结果的具体原因
4. 对于不符合的情况，请明确指出具体问题所在
"""
        
        ai_response = generate_with_gemini(prompt, max_tokens=9999)
        if ai_response:
            try:
                import json
                # 尝试解析JSON响应
                if '[' in ai_response and ']' in ai_response:
                    json_start = ai_response.find('[')
                    json_end = ai_response.rfind(']') + 1
                    json_str = ai_response[json_start:json_end]
                    results = json.loads(json_str)
                    
                    # 验证结果格式
                    if isinstance(results, list) and len(results) > 0:
                        valid_results = []
                        for item in results:
                            if isinstance(item, dict) and 'rule_name' in item and 'status' in item:
                                valid_results.append(item)
                        
                        if valid_results:
                            rules_info = f"（应用了{len(rules_context)}条规则）"
                            print(f"✅ Gemini AI审核成功{rules_info}，生成{len(valid_results)}个审核结果")
                            return valid_results
                        else:
                            raise Exception("AI返回的结果格式不正确")
                    else:
                        raise Exception("AI返回的结果不是有效的列表")
                else:
                    raise Exception("AI返回的内容不包含JSON数组")
            except Exception as e:
                print(f"⚠️ 解析Gemini响应失败: {e}")
                raise Exception(f"解析AI响应失败: {e}")
        else:
            raise Exception("AI返回空响应")
        
    except Exception as e:
        # 根据“禁用模拟模式”规范，直接抛出异常，不提供降级方案
        raise Exception(f"AI审核失败: {str(e)}")

def cross_validate_materials_with_ai(all_extracted_info: Dict[str, Any], core_info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    使用AI进行材料交叉校验 - 只比对1-17项材料的核心信息
    
    Args:
        all_extracted_info: 所有提取的信息字典
        core_info: 核心信息（姓名、身份证号等）
        
    Returns:
        交叉校验结果列表
    """
    try:
        print(f"🤖 开始使用Gemini AI进行交叉校验...")
        
        # 尝试使用Gemini AI
        client = _get_gemini_client()
        if client is not None:
            # 读取交叉检验规则文件
            from pathlib import Path
            rules_context = []
            rules_dir = Path("rules")
            
            # 加载交叉检验规则.md
            try:
                cross_rules_path = rules_dir / "交叉检验规则.md"
                if cross_rules_path.exists():
                    cross_rules_content = cross_rules_path.read_text(encoding='utf-8')
                    # 按照MD文件处理规范，按逗号分割
                    cross_rules_items = [item.strip() for item in cross_rules_content.split(',') if item.strip()]
                    for i, rule_content in enumerate(cross_rules_items, 1):
                        rules_context.append({
                            'rule_id': f'cross_rule_{i}',
                            'content': rule_content,
                            'source_file': '交叉检验规则.md',
                            'priority': '极高'
                        })
            except Exception as e:
                print(f"⚠️ 加载交叉检验规则失败: {e}")
            
            # 加载通用规则.md
            try:
                general_rules_path = rules_dir / "通用规则.md"
                if general_rules_path.exists():
                    general_rules_content = general_rules_path.read_text(encoding='utf-8')
                    # 按照MD文件处理规范，按逗号分割
                    general_rules_items = [item.strip() for item in general_rules_content.split(',') if item.strip()]
                    for i, rule_content in enumerate(general_rules_items, 1):
                        rules_context.append({
                            'rule_id': f'general_rule_{i}',
                            'content': rule_content,
                            'source_file': '通用规则.md',
                            'priority': '高'
                        })
            except Exception as e:
                print(f"⚠️ 加载通用规则失败: {e}")
            
            if not rules_context:
                raise Exception("未找到交叉检验规则，无法进行交叉校验")
            
            # 提取各项材料的核心信息（只要姓名和身份证号）
            materials_core_info = []
            
            # 从 core_info 中提取信息（1-17项结构化数据）
            if core_info and isinstance(core_info, dict):
                for category, info in core_info.items():
                    if isinstance(info, dict):
                        name = info.get('name')
                        id_number = info.get('id_number')
                        if name or id_number:  # 只要有任意一个信息就记录
                            materials_core_info.append({
                                "material_type": category,
                                "name": name or "未提取",
                                "id_number": id_number or "未提取",
                                "extracted_from": info.get('extracted_from', [])
                            })
            
            # 如果 core_info 是老格式，也要处理
            elif core_info and hasattr(core_info, 'name'):
                materials_core_info.append({
                    "material_type": "附件信息",
                    "name": getattr(core_info, 'name', '未提取'),
                    "id_number": getattr(core_info, 'id_number', '未提取'),
                    "extracted_from": getattr(core_info, 'extracted_from', [])
                })
            
            # 从 all_extracted_info 中提取核心信息（如果没有 core_info）
            if not materials_core_info:
                for material_type, info in all_extracted_info.items():
                    if isinstance(info, dict):
                        # 尝试从材料中提取姓名和身份证
                        name = info.get('name') or info.get('姓名')
                        id_number = info.get('id_number') or info.get('身份证号')
                        
                        if name or id_number:
                            materials_core_info.append({
                                "material_type": material_type,
                                "name": name or "未提取",
                                "id_number": id_number or "未提取",
                                "extracted_from": [material_type]
                            })
            
            if not materials_core_info and not core_info:
                raise Exception("未找到任何核心信息用于交叉校验")
            
            print(f"📋 找到 {len(materials_core_info)} 项材料的核心信息用于交叉校验")
            
            # 构建交叉校验内容（只包含核心信息）
            cross_validation_content = "核心信息交叉比对：\n\n"
            
            for i, material_info in enumerate(materials_core_info, 1):
                cross_validation_content += f"{i}. {material_info['material_type']}:\n"
                cross_validation_content += f"   姓名: {material_info['name']}\n"
                cross_validation_content += f"   身份证: {material_info['id_number']}\n"
                cross_validation_content += f"   来源: {', '.join(material_info['extracted_from'])}\n\n"
            
            # 使用统一的AI校验接口
            ai_results = validate_material_with_ai(
                material_type="交叉校验",
                content=cross_validation_content,
                rules_context=rules_context
            )
            
            print(f"✅ Gemini AI交叉校验成功，生成{len(ai_results)}个校验结果")
            return ai_results
        
        # AI失败时抛出异常
        raise Exception("AI交叉校验失败，无法完成交叉校验")
        
    except Exception as e:
        raise Exception(f"AI交叉校验异常: {e}")

def extract_category_core_info_with_ai(category_key: str, folder_name: str, material_content: str) -> Dict[str, Any]:
    """
    使用AI从特定类别材料中提取核心信息（包括姓名、身份证号等）
    
    Args:
        category_key: 材料类别标识
        folder_name: 文件夹名称
        material_content: 材料内容
        
    Returns:
        提取的核心信息字典
    """
    try:
        print(f"🤖 使用AI提取 {category_key} ({folder_name}) 的核心信息...")
        
        # 尝试使用Gemini AI
        client = _get_gemini_client()
        if client is not None:
            prompt = f"""
你是专业的职称评审材料信息提取专家。请从以下材料中提取基本个人信息。

请严格按照JSON格式返回，只返回JSON，不要其他说明文字：

{{
  "name": "姓名",
  "gender": "性别",
  "id_number": "身份证号"
}}

要求：
1. 姓名：2-4个中文字符，找不到填空字符串
2. 性别：男/女，找不到填空字符串  
3. 身份证号：18位（17位数字+最后一位数字或X），找不到填空字符串
4. 不要推测或编造信息

材料内容：
{material_content[:2000]}  # 限制长度
"""
            
            ai_response = generate_with_gemini(prompt, max_tokens=500)
            if ai_response:
                try:
                    import json
                    # 尝试解析JSON响应
                    if '{' in ai_response and '}' in ai_response:
                        json_start = ai_response.find('{')
                        json_end = ai_response.rfind('}') + 1
                        json_str = ai_response[json_start:json_end]
                        result = json.loads(json_str)
                        
                        name = result.get('name', '').strip()
                        gender = result.get('gender', '').strip()
                        id_number = result.get('id_number', '').strip()
                        
                        # 验证提取结果
                        is_valid_name = name and len(name) >= 2 and len(name) <= 4
                        is_valid_gender = gender in ['男', '女']
                        is_valid_id = not id_number or re.match(r'^\d{17}[\dX]$', id_number)
                        
                        if is_valid_name or is_valid_id or is_valid_gender:
                            extracted_info = {
                                "name": name if is_valid_name else None,
                                "gender": gender if is_valid_gender else None,
                                "id_number": id_number if is_valid_id and id_number else None,
                                "extracted_from": [folder_name],
                                "content_summary": material_content[:100] + "..." if len(material_content) > 100 else material_content,
                                "key_info": {
                                    "category": category_key,
                                    "folder_name": folder_name,
                                    "extracted_at": _get_current_timestamp()
                                }
                            }
                            
                            print(f"✅ AI提取 {folder_name} 成功: 姓名='{name}', 性别='{gender}', 身份证='{id_number}'")
                            return extracted_info
                            
                except Exception as e:
                    print(f"⚠️ 解析 {folder_name} AI响应失败: {e}")
        
        # AI失败时抛出异常，由调用方处理
        raise Exception(f"AI提取失败，无法从{folder_name}获取核心信息")
        
    except Exception as e:
        raise Exception(f"AI提取异常: {e}")

def _get_current_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().isoformat()

