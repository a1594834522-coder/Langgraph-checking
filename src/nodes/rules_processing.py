"""
规则集处理节点

实现规则集的加载、提取和JSON格式转换：
1. load_rules_node: 加载规则集文件
2. extract_rules_node: 提取规则内容并转换为JSON格式
3. 严格按照1-17项分类规则
4. 支持多条规则转换为多条JSON
"""

import os
import json
import re
from typing import Dict, Any, List
from pathlib import Path

# Excel 文件读取支持
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False
    print("⚠️ pandas 未安装，无法读取 Excel 文件")

from ..graph.state import AuditState
from ..models.state import RuleInfo, RuleFileInfo


async def load_rules_node(state: AuditState) -> Dict[str, Any]:
    """
    加载规则集节点
    
    从预定义的规则目录加载所有规则文件

    """
    try:
        print("🔄 开始加载规则集...")
        
        # 规则集目录
        rules_dir = Path("rules")
        # 使用异步方式检查和创建目录
        import asyncio
        dir_exists = await asyncio.to_thread(rules_dir.exists)
        if not dir_exists:
            print("⚠️ 规则目录不存在，创建默认规则目录")
            await asyncio.to_thread(rules_dir.mkdir, exist_ok=True)
        
        rules_data = []
        
        # 使用异步方式遍历规则目录（只支持 .xlsx 和 .md 格式）
        async def find_rule_files():
            rule_files = []
            # 使用异步方式遍历文件
            glob_result = await asyncio.to_thread(list, rules_dir.glob("**/*"))
            for file_path in glob_result:
                is_file = await asyncio.to_thread(file_path.is_file)
                if is_file and file_path.suffix in ['.xlsx', '.md']:
                    rule_files.append(file_path)
            return rule_files
        
        rule_files_list = await find_rule_files()
        
        for rule_file in rule_files_list:
            try:
                # 根据文件格式读取内容
                if rule_file.suffix == '.md':
                    # 异步读取 Markdown 文件
                    import asyncio
                    content = await asyncio.to_thread(
                        lambda: open(rule_file, 'r', encoding='utf-8').read()
                    )
                elif rule_file.suffix == '.xlsx':
                    # 读取 Excel 文件（异步调用）
                    excel_rules = await _read_excel_file(rule_file)
                    if not excel_rules:
                        print(f"⚠️ Excel 文件读取失败或为空: {rule_file.name}")
                        continue
                                    
                    # 对于 Excel 文件，直接使用提取的规则列表
                    rule_info = {
                        "file_name": rule_file.name,
                        "file_path": str(rule_file),
                        "file_type": rule_file.suffix,
                        "extracted_rules": excel_rules,  # 直接存储规则列表
                        "size": len(excel_rules)
                    }
                    rules_data.append(rule_info)
                    print(f"✅ 加载规则文件: {rule_file.name} ({len(excel_rules)} 条规则)")
                    continue
                else:
                    print(f"⚠️ 不支持的文件格式: {rule_file.suffix}")
                    continue
                
                # 处理 Markdown 文件
                rule_info = {
                    "file_name": rule_file.name,
                    "file_path": str(rule_file),
                    "file_type": rule_file.suffix,
                    "content": content,
                    "size": len(content)
                }
                rules_data.append(rule_info)
                print(f"✅ 加载规则文件: {rule_file.name} ({len(content)} 字符)")
                
            except Exception as e:
                print(f"⚠️ 读取规则文件失败 {rule_file}: {e}")
                continue
        
        if not rules_data:
            print("⚠️ 未找到任何规则文件，跳过规则处理")
            # 不再使用默认规则集，直接返回空列表
        
        print(f"✅ 成功加载 {len(rules_data)} 个规则文件")
        
        return {
            "rules_data": rules_data,
            "processing_logs": [f"成功加载 {len(rules_data)} 个规则文件"],
            "current_step": "rules_loaded"
        }
        
    except Exception as e:
        error_msg = f"规则集加载失败: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "error_message": error_msg,
            "processing_logs": [error_msg],
            "current_step": "rules_load_failed"
        }


def extract_rules_node(state: AuditState) -> Dict[str, Any]:
    """
    提取规则节点
    
    将加载的规则内容提取并转换为JSON格式
    严格按照1-17项分类规则
    """
    try:
        print("🔄 开始提取和转换规则...")
        
        rules_data = state.get("rules_data", [])
        if not rules_data:
            print("⚠️ 没有找到规则数据，跳过规则提取")
            return {
                "parsed_rules": [],
                "rules_by_category": {},
                "processing_logs": ["未找到规则数据，跳过规则提取"],
                "current_step": "rules_extract_skipped"
            }
        
        parsed_rules = []
        rules_by_category = {}
        
        # 1-17项分类标准
        standard_categories = {
            "1": "教育经历",
            "2": "工作经历", 
            "3": "继续教育(培训情况)",
            "4": "学术技术兼职情况",
            "5": "获奖情况",
            "6": "获得荣誉称号情况",
            "7": "主持参与科研项目(基金)情况",
            "8": "主持参与工程技术项目情况",
            "9": "论文",
            "10": "著(译)作(教材)",
            "11": "专利(著作权)情况",
            "12": "主持参与指定标准情况",
            "13": "成果被批示、采纳、运用和推广情况",
            "14": "资质证书",
            "15": "奖惩情况",
            "16": "考核情况",
            "17": "申报材料附件信息"
        }
        
        # 初始化分类字典
        for key, name in standard_categories.items():
            rules_by_category[key] = []
        
        # 处理每个规则文件
        for rule_data in rules_data:
            try:
                file_name = rule_data["file_name"]
                
                # 对于 Excel 文件，直接使用已提取的规则
                if file_name.endswith('.xlsx') and 'extracted_rules' in rule_data:
                    extracted_rules = rule_data['extracted_rules']
                else:
                    # 对于 Markdown 文件，使用正则匹配提取
                    content = rule_data.get("content", "")
                    extracted_rules = _extract_rules_with_regex(content, file_name)
                
                # 将规则分类到1-17项中（根据文件名直接分类）
                for rule in extracted_rules:
                    category = _classify_rule_by_filename(rule, file_name, standard_categories)
                    if category:
                        # 更新规则信息，添加1-17项分类
                        updated_rule = RuleInfo(
                            rule_id=rule.rule_id,
                            content=rule.content,
                            source_file=rule.source_file,
                            category=category,
                            priority=rule.priority
                        )
                        
                        rules_by_category[category].append(updated_rule)
                        parsed_rules.append(updated_rule)
                        
                print(f"✅ 提取规则文件 {file_name}: {len(extracted_rules)} 条规则")
                
            except Exception as e:
                print(f"⚠️ 提取规则文件失败 {rule_data.get('file_name')}: {e}")
                continue
        
        # 统计结果
        total_rules = len(parsed_rules)
        category_counts = {k: len(v) for k, v in rules_by_category.items() if v}
        
        # 调试：检查规则字段完整性
        print(f"✅ 规则提取完成: 总计 {total_rules} 条规则")
        print(f"📊 分类统计: {category_counts}")
        
        # 验证规则字段完整性
        if parsed_rules:
            sample_rule = parsed_rules[0]
            required_fields = ['rule_id', 'content', 'source_file', 'category', 'priority']
            
            # 检查RuleInfo对象的属性
            if hasattr(sample_rule, '__dict__'):
                missing_fields = [field for field in required_fields if not hasattr(sample_rule, field)]
                if missing_fields:
                    print(f"⚠️ 警告：规则缺少字段: {missing_fields}")
                else:
                    print(f"✅ 规则字段完整性验证通过")
                
                print(f"📋 示例规则属性: {list(sample_rule.__dict__.keys())}")
            else:
                # 如果是字典格式
                if hasattr(sample_rule, 'keys'):
                    missing_fields = [field for field in required_fields if field not in sample_rule]
                    if missing_fields:
                        print(f"⚠️ 警告：规则缺少字段: {missing_fields}")
                    else:
                        print(f"✅ 规则字段完整性验证通过")
                    
                    print(f"📋 示例规则字段: {list(sample_rule.keys())}")
                else:
                    print(f"⚠️ 无法验证规则字段完整性，规则类型: {type(sample_rule)}")
        
        return {
            "parsed_rules": parsed_rules,  # 直接返回列表，不使用特殊语法
            "rules_by_category": rules_by_category,
            "processing_logs": [
                f"成功提取 {total_rules} 条规则",
                f"分类统计: {category_counts}"
            ],
            "current_step": "rules_extracted"
        }
        
    except Exception as e:
        error_msg = f"规则提取失败: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "error_message": error_msg,
            "processing_logs": [error_msg],
            "current_step": "rules_extract_failed"
        }


async def _read_excel_file(file_path: Path) -> List[RuleInfo]:
    """
    读取 Excel 文件内容（专门处理规则集的固定结构）
    
    Excel 文件结构：序号、文件类型、核心问题、规则内容、优先级（一定）
    
    Args:
        file_path: Excel 文件路径
        
    Returns:
        规则列表
    """
    if not PANDAS_AVAILABLE or pd is None:
        print(f"⚠️ pandas 未安装，无法读取 Excel 文件: {file_path.name}")
        return []
    
    try:
        import asyncio
        # 使用异步方式读取 Excel 文件的所有工作表
        excel_data = await asyncio.to_thread(
            lambda: pd.read_excel(file_path, sheet_name=None)  # type: ignore
        )
        
        extracted_rules = []
        
        # 期望的列名（支持变形）
        expected_columns = {
            '序号': ['序号', '编号', 'ID', 'id', '序'],
            '文件类型': ['文件类型', '类型', 'Type', 'type', '类别'],
            '核心问题': ['核心问题', '问题', 'Problem', 'problem', '主题'],
            '规则内容': ['规则内容', '内容', 'Content', 'content', '规则'],
            '优先级': ['优先级', 'Priority', 'priority', '级别']
        }
        
        for sheet_name, df in excel_data.items():
            if df.empty:
                continue
                
            print(f"📊 读取工作表: {sheet_name}")
            
            # 映射实际列名到标准列名
            column_mapping = {}
            for standard_col, possible_names in expected_columns.items():
                for col in df.columns:
                    if str(col).strip() in possible_names:
                        column_mapping[standard_col] = col
                        break
            
            # 逐行处理规则数据
            for index, row in df.iterrows():
                if index == 0:  # 跳过标题行
                    continue
                    
                # 提取各个字段
                rule_data = {}
                for standard_col, actual_col in column_mapping.items():
                    if actual_col in df.columns:
                        cell_value = row[actual_col]
                        if pd.notna(cell_value):  # type: ignore
                            rule_data[standard_col] = str(cell_value).strip()
                
                # 只处理有效规则（至少有规则内容）
                if '规则内容' in rule_data and rule_data['规则内容']:
                    rule = RuleInfo(
                        rule_id=f"{file_path.stem}_{rule_data.get('序号', index)}",
                        content=rule_data['规则内容'],
                        source_file=file_path.name,
                        category="未分类",
                        priority=rule_data.get('优先级', 'normal')
                    )
                    extracted_rules.append(rule)
        
        print(f"✅ Excel文件 {file_path.name}: 提取到 {len(extracted_rules)} 条规则")
        return extracted_rules
        
    except Exception as e:
        print(f"❌ 读取 Excel 文件失败 {file_path.name}: {e}")
        return []





def _extract_rules_with_regex(content: str, file_name: str) -> List[RuleInfo]:
    """
    使用正则表达式提取规则内容（仅处理 Markdown 文件）
    """
    try:
        print(f"🔍 使用正则匹配提取规则: {file_name}")
        
        rules = []
        
        # 仅对 Markdown 文件进行处理，规则按逗号分开
        if file_name.endswith('.md'):
            # 按逗号分割规则
            rule_parts = content.split(',')
            
            rule_id = 1
            for part in rule_parts:
                rule_content = part.strip()
                
                # 只要有内容就提取，只保留必要字段
                if rule_content:
                    rule = RuleInfo(
                        rule_id=f"{file_name}_{rule_id:03d}",
                        content=rule_content,
                        source_file=file_name,
                        category="未分类",
                        priority="normal"
                    )
                    rules.append(rule)
                    rule_id += 1
        else:
            print(f"⚠️ 不支持的文件格式用于正则提取: {file_name}")
        
        print(f"✅ 正则匹配提取 {len(rules)} 条规则")
        return rules
        
    except Exception as e:
        print(f"⚠️ 正则匹配提取失败: {e}")
        return []


def _classify_rule_by_filename(rule: RuleInfo, file_name: str, categories: Dict[str, str]) -> str:
    """
    根据标准化的文件名直接分类规则到1-17项中
    
    Args:
        rule: 规则对象
        file_name: 规则文件名（如"2.工作经历规则集.xlsx"）
        categories: 分类字典
        
    Returns:
        分类编号（1-17）
    """
    try:
        # 从文件名中提取数字编号
        # 支持格式："2.工作经历规则集.xlsx" 或 "9.论文规则集.md"
        import re
        match = re.match(r'^(\d+)\.', file_name)
        
        if match:
            category_num = match.group(1)
            # 确保编号在1-17范围内
            if category_num in categories:
                print(f"📋 文件 {file_name} 分类为: {category_num}.{categories[category_num]}")
                return category_num
        
        # 如果文件名不符合标准格式，尝试从文件名关键词推断
        file_lower = file_name.lower()
        for cat_num, cat_name in categories.items():
            # 简化的关键词匹配（只针对文件名）
            if any(keyword in file_lower for keyword in [
                cat_name[:2],  # 取分类名的前两个字符
                cat_num + ".",  # 数字编号
            ]):
                print(f"📋 文件 {file_name} 通过关键词匹配分类为: {cat_num}.{cat_name}")
                return cat_num
        
        # 默认分类到附件信息
        print(f"⚠️ 文件 {file_name} 无法识别分类，默认归入17.申报材料附件信息")
        return "17"
        
    except Exception as e:
        print(f"⚠️ 文件分类失败 {file_name}: {e}")
        return "17"  # 默认分类


def _classify_rule(rule: Dict[str, Any], categories: Dict[str, str]) -> str:
    """
    将规则分类到1-17项中（备用方法）
    """
    return "17"  # 默认分类


def _create_default_rules() -> List[Dict[str, Any]]:
    """
    创建默认规则集（已取消，返回空列表）
    """
    return []


# 导出节点函数
__all__ = ["load_rules_node", "extract_rules_node"]