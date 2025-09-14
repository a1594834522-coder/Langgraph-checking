"""
报告生成节点 - 完全无缓存版本

🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
"""

from typing import Dict, Any
from src.graph.state import AuditState


def report_generation_node(state: AuditState) -> Dict[str, Any]:
    """
    完全无缓存的报告生成节点 - 每次都处理全新数据
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    """
    try:
        print(f"📄 开始无缓存报告生成...")
        
        # 生成报告ID
        from datetime import datetime
        import uuid
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"AUDIT_{timestamp}_{str(uuid.uuid4())[:8].upper()}"
        
        # 直接获取当前状态的所有数据 - 不使用任何缓存
        material_validation = state.get("material_validation", {})
        cross_validation = state.get("cross_validation", [])
        
        print(f"🔍 当前状态数据:")
        print(f"   材料校验结果: {len(material_validation)} 项")
        print(f"   交叉校验结果: {len(cross_validation)} 项")
        
        # 直接整合所有数据 - 不做缓存检查
        all_results = []
        
        # 整合material_validation数据
        for material_type, results in material_validation.items():
            if isinstance(results, list):
                all_results.extend(results)
            elif results:
                all_results.append(results)
        
        # 整合cross_validation数据
        if isinstance(cross_validation, list):
            all_results.extend(cross_validation)
        
        if not all_results:
            print("⚠️ 未找到任何校验结果，生成空报告")
        
        print(f"📊 报告数据统计: 共{len(all_results)}项结果")
        
        # 直接生成HTML报告 - 不使用缓存的复杂逻辑
        html_report = _generate_html_report(all_results, report_id)
        
        # 保存报告文件
        report_path = f"audit_report_{timestamp}.html"
        
        if report_path and html_report:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_report)
            
            print(f"✅ 报告已生成: {report_path}")
        else:
            raise Exception("报告路径或内容为空")
        
        return {
            "audit_report": html_report,
            "report_path": report_path,
            "current_step": "completed",
            "is_complete": True,
            "processing_logs": [
                f"报告生成完成: {report_id}",
                f"处理了{len(all_results)}项结果",
                "已完全取消缓存机制，确保数据全新",
                f"报告已保存至: {report_path}"
            ]
        }
        
    except Exception as e:
        print(f"❌ 报告生成失败: {str(e)}")
        return {
            "current_step": "report_generation_failed",
            "error_message": f"报告生成失败: {str(e)}"
        }


def _generate_html_report(all_results: list, report_id: str) -> str:
    """
    生成简化的HTML报告 - 完全无缓存机制
    """
    from datetime import datetime
    
    print(f"📊 报告生成使用数据，共{len(all_results)}项结果")
    
    # 按材料类型分组
    material_groups = {}
    for result in all_results:
        material_type = result.get('material_type', '未知类型')
        if material_type not in material_groups:
            material_groups[material_type] = []
        material_groups[material_type].append(result)
    
    # 统计数据
    error_count = sum(1 for r in all_results if r.get('result', '').startswith('❌'))
    warning_count = sum(1 for r in all_results if r.get('result', '').startswith('⚠️'))
    pass_count = sum(1 for r in all_results if r.get('result', '').startswith('✅'))
    total_validations = len(all_results)
    
    print(f"📊 统计: 错误{error_count}, 警告{warning_count}, 通过{pass_count}")

    # 生成基本的HTML报告结构
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>职称评审材料审核报告 - {report_id}</title>
    <style>
        body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; margin: 20px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-item {{ background: #e8f4fd; padding: 15px; border-radius: 5px; flex: 1; }}
        .material-group {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
        .material-header {{ background: #f0f0f0; padding: 10px; font-weight: bold; }}
        .result-item {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .pass {{ color: green; }}
        .warning {{ color: orange; }}
        .error {{ color: red; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>职称评审材料审核报告</h1>
        <p>报告ID: {report_id}</p>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-item">
            <h3>总计</h3>
            <p>{len(all_results)} 项检查</p>
        </div>
        <div class="stat-item error">
            <h3>错误</h3>
            <p>{error_count} 项</p>
        </div>
        <div class="stat-item warning">
            <h3>警告</h3>
            <p>{warning_count} 项</p>
        </div>
        <div class="stat-item pass">
            <h3>通过</h3>
            <p>{pass_count} 项</p>
        </div>
    </div>
    
    <div class="content">
        <h2>详细结果</h2>
"""
    
    # 添加材料组详情
    for material_type, results in material_groups.items():
        html_template += f"""
        <div class="material-group">
            <div class="material-header">{material_type} ({len(results)} 项)</div>
"""
        for result in results[:10]:  # 限制显示数量
            result_class = "error" if result.get('result', '').startswith('❌') else "warning" if result.get('result', '').startswith('⚠️') else "pass"
            html_template += f"""
            <div class="result-item {result_class}">
                <strong>{result.get('rule_name', '未知规则')}</strong>: {result.get('result', '未知')}<br>
                <small>{result.get('details', '无详情')}</small>
            </div>
"""
        html_template += "</div>"
    
    html_template += """
    </div>
</body>
</html>
    """
    
    return html_template