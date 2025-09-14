"""
通用工具

提供通用的工具函数：
- 正则表达式提取
- 数据清理和验证
- HTML报告生成
- 日志记录
"""

import re
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from src.models.state import CoreInfo, ValidationResult as StateValidationResult

def extract_with_regex(content: str) -> tuple[str, str]:
    """使用正则表达式的备用提取方法（增强版）"""
    name = ""
    id_number = ""
    
    # 提取姓名（多种格式匹配）
    name_patterns = [
        r"姓[名]*[：:]\s*([^\s\n\r\t]+)",  # 姓名：
        r"申请人[：:]\s*([^\s\n\r\t]+)",        # 申请人：
        r"姓[\s]*名[\s]*[：:]\s*([^\s\n\r\t]+)",  # 姓 名：
        r"^([\u4e00-\u9fff]{2,4})[\s]*[男女]",         # 中文姓名后面跟性别
    ]
    
    for pattern in name_patterns:
        name_match = re.search(pattern, content, re.MULTILINE)
        if name_match:
            potential_name = name_match.group(1).strip()
            # 验证姓名的合理性（中文字符2-4个字）
            if re.match(r'^[\u4e00-\u9fff]{2,4}$', potential_name):
                name = potential_name
                break
    
    # 提取身份证号（多种格式匹配）
    id_patterns = [
        r"身份证[号码]*[：:]\s*(\d{17}[\dX])",  # 身份证号：
        r"公民身份号码[：:]\s*(\d{17}[\dX])",    # 公民身份号码：
        r"ID[\s]*Number[\s]*[：:]\s*(\d{17}[\dX])",   # ID Number:
        r"(\d{17}[\dX])(?![\d])",                   # 直接匹配18位数字（排除更长数字）
    ]
    
    for pattern in id_patterns:
        id_match = re.search(pattern, content)
        if id_match:
            potential_id = id_match.group(1)
            # 验证身份证号格式
            if re.match(r'^\d{17}[\dX]$', potential_id):
                id_number = potential_id
                break
    
    if name or id_number:
        print(f"✅ 正则提取成功: 姓名='{name}', 身份证='{id_number}'")
    else:
        print("⚠️ 正则提取未找到有效信息")
    
    return name, id_number

def generate_html_report(core_info: Optional[Union[CoreInfo, Dict[str, Any]]], validation_results: List[Any]) -> str:
    """生成HTML格式化报告"""
    # 处理core_info为None的情况
    if core_info is None:
        name = '未提取'
        id_number = '未提取'
        extracted_from = []
    else:
        # 支持CoreInfo对象和Dict两种类型
        if isinstance(core_info, dict):
            name = core_info.get('name', '') or '未提取'
            id_number = core_info.get('id_number', '') or '未提取'
            extracted_from = core_info.get('extracted_from', []) or []
        else:
            # CoreInfo对象
            name = getattr(core_info, 'name', None) or '未提取'
            id_number = getattr(core_info, 'id_number', None) or '未提取'
            extracted_from = getattr(core_info, 'extracted_from', []) or []
    
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>职称评审材料审核报告</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 30px; }}
        .result-item {{ padding: 10px; margin: 5px 0; border-left: 4px solid #ddd; background: #f9f9f9; }}
        .result-pass {{ border-color: #28a745; }}
        .result-warning {{ border-color: #ffc107; }}
        .result-error {{ border-color: #dc3545; }}
        .result-unknown {{ border-color: #6c757d; }}
        .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .info-item {{ background: #e9ecef; padding: 15px; border-radius: 5px; }}
        h1, h2 {{ color: #333; }}
        .badge {{ padding: 2px 8px; border-radius: 3px; font-size: 12px; color: white; }}
        .badge-pass {{ background: #28a745; }}
        .badge-warning {{ background: #ffc107; color: #000; }}
        .badge-error {{ background: #dc3545; }}
        .badge-unknown {{ background: #6c757d; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 职称评审材料审核报告</h1>
        <p>生成时间：<span id="datetime"></span></p>
    </div>
    
    <div class="section">
        <h2>👤 核心信息</h2>
        <div class="info-grid">
            <div class="info-item">
                <strong>姓名:</strong> {name}
            </div>
            <div class="info-item">
                <strong>身份证号:</strong> {id_number}
            </div>
            <div class="info-item">
                <strong>信息来源:</strong> {', '.join(extracted_from) if extracted_from else '无'}
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>✅ 审核结果</h2>"""
    
    if validation_results:
        for result in validation_results:
            # 处理不同的ValidationResult类型
            # 支持既有status属性，也支持result属性
            status = getattr(result, 'status', None) or getattr(result, 'result', 'UNKNOWN')
            rule_name = getattr(result, 'rule_name', '未知规则')
            message = getattr(result, 'message', None) or getattr(result, 'details', '无详细信息')
            
            # 统一处理status格式
            if '✅' in status or status == 'PASS':
                status_normalized = 'pass'
                status_display = '✅通过'
            elif '⚠️' in status or status == 'WARNING':
                status_normalized = 'warning' 
                status_display = '⚠️警告'
            elif '❌' in status or status == 'ERROR':
                status_normalized = 'error'
                status_display = '❌不通过'
            else:
                status_normalized = 'unknown'
                status_display = status
            
            status_class = f"result-{status_normalized}"
            badge_class = f"badge-{status_normalized}"
            
            html_template += f"""
        <div class="result-item {status_class}">
            <strong>{rule_name}</strong>
            <span class="badge {badge_class}">{status_display}</span>
            <p>{message}</p>
        </div>"""
    else:
        html_template += "<p>无审核结果</p>"
    
    html_template += """
    </div>
    
    <script>
        document.getElementById('datetime').textContent = new Date().toLocaleString('zh-CN');
    </script>
</body>
</html>"""
    
    return html_template