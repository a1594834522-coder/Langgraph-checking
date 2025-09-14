"""
LangGraph边和路由逻辑定义

包含工作流中的条件边和路由函数：
- 根据PDF页数决定处理策略的路由
- 根据材料类型决定校验规则的路由  
- 根据校验结果决定后续流程的路由
- 支持Send API实现的并行分支
"""

from typing import Dict, Any, List, Union
from .state import AuditState

# 导入Send API用于并行处理
try:
    from langgraph.types import Send
    SEND_AVAILABLE = True
except ImportError:
    Send = None
    SEND_AVAILABLE = False


def should_continue_processing(state: AuditState) -> str:
    """
    判断是否继续处理流程
    
    Returns:
        "continue": 继续处理
        "error": 发生错误，终止流程
    """
    if state.get("error_message"):
        return "error"
    
    if not state.get("uploaded_file"):
        return "error"
    
    return "continue"


def route_folder_validation(state: AuditState) -> str:
    """
    根据文件夹结构验证结果决定处理策略
    
    Returns:
        "process_folders": 文件夹结构正确，继续处理
        "error": 文件夹结构错误，终止流程
    """
    folder_validation = state.get("folder_validation", {})
    
    # 检查是否有17个标准文件夹
    if not folder_validation:
        return "error"
    
    folders_found = folder_validation.get("folders_found", [])
    if len(folders_found) < 17:
        return "error"
    
    return "process_folders"


def should_continue_content_analysis(state: AuditState) -> str:
    """
    判断是否继续内容分析
    
    Returns:
        "analyze": 继续分析
        "skip_analysis": 跳过分析
        "error": 发生错误
    """
    if state.get("error_message"):
        return "error"
    
    extracted_content = state.get("extracted_content", {})
    if not extracted_content:
        return "skip_analysis"
    
    return "analyze"


def route_to_cross_validation(state: AuditState) -> str:
    """
    决定是否进行交叉校验
    
    Returns:
        "cross_validate": 进行交叉校验
        "skip_cross_validation": 跳过交叉校验
        "error": 发生错误
    """
    if state.get("error_message"):
        return "error"
    
    # 检查是否有材料校验结果
    material_validation = state.get("material_validation", {})
    if not material_validation:
        return "skip_cross_validation"
    
    # 检查是否有核心信息
    core_info = state.get("core_info")
    extracted_content = state.get("extracted_content", {})
    
    if not core_info and not extracted_content:
        return "skip_cross_validation"
    
    return "cross_validate"


def should_generate_report(state: AuditState) -> str:
    """
    判断是否应该生成报告
    
    Returns:
        "generate_report": 生成报告
        "error": 发生错误，终止流程
    """
    if state.get("error_message"):
        return "error"
    
    # 只要有任何处理结果就生成报告
    has_content = any([
        state.get("extracted_content"),
        state.get("material_validation"),
        state.get("cross_validation"),
        state.get("folder_classification")
    ])
    
    if has_content:
        return "generate_report"
    else:
        return "error"
def check_pdf_extraction_for_parallel_processing(state: AuditState) -> Union[List, str]:
    """
    PDF提取完成后，并行分发到core_info_extraction和validation节点
    
    确保PDF提取的数据能同时进入核心信息提取和材料校验
    
    Returns:
        Send对象列表，发送到core_info_extraction和validation
        或者在失败时返回END
    """
    if not SEND_AVAILABLE or Send is None:
        print("⚠️ Send API不可用，使用传统路由")
        # 检查PDF提取状态
        status = check_pdf_extraction_status(state)
        if status == "pdf_extraction_success":
            return "core_info_extraction"  # 退化到传统路由
        else:
            return "END"
    
    # 检查PDF提取状态
    status = check_pdf_extraction_status(state)
    
    if status == "pdf_extraction_success":
        print(f"🚀 PDF提取成功，并行分发到核心信息提取和校验节点")
        
        # 并行发送到两个处理节点
        return [
            Send("core_info_extraction", state),  # 核心信息提取
            Send("validation", state)             # 直接进入校验
        ]
    else:
        print("❌ PDF提取失败，终止流程")
        return "END"


def check_core_info_for_cross_validation(state: AuditState) -> str:
    """
    检查核心信息是否完成，决定是否进行交叉验证
    
    注意：LangGraph不支持真正的"等待两个节点都完成"逻辑
    这里简化为：只要有核心信息就进行交叉验证
    
    Returns:
        "proceed_cross_validation": 进行交叉验证
        "skip_cross_validation": 跳过交叉验证
    """
    core_info = state.get("core_info")
    extracted_content = state.get("extracted_content", {})
    
    # 只要有核心信息和提取内容就进行交叉验证
    if core_info is not None and extracted_content:
        return "proceed_cross_validation"
    else:
        return "skip_cross_validation"


def check_pdf_extraction_status(state: AuditState) -> str:
    """
    检查PDF提取状态，确保PDF内容提取完成后才进行下一步
    
    这是关键的状态判断函数，遵循LangGraph条件边的最佳实践
    
    Returns:
        "pdf_extraction_success": PDF提取成功，继续后续流程
        "pdf_extraction_failed": PDF提取失败，跳转到错误处理
        "pdf_extraction_pending": PDF提取正在进行中（理论上不应该出现）
    """
    print("🔍 检查PDF提取状态...")
    
    # 检查当前步骤状态
    current_step = state.get("current_step", "")
    print(f"📋 当前步骤: {current_step}")
    
    # 修复被连接的状态字符串问题
    if "pdf_extraction_failed" in current_step:
        print("❌ PDF提取已标记为失败")
        return "pdf_extraction_failed"
    
    if "pdf_extraction_completed" in current_step:
        print("✅ PDF提取已标记为完成")
        # 检查是否有实际的提取结果
        pdf_extraction_results = state.get("pdf_extraction_results", {})
        api_extraction_results = state.get("api_extraction_results", {})
        if pdf_extraction_results or api_extraction_results:
            print(f"📊 找到PDF提取结果: {len(pdf_extraction_results)} 个文件夹")
            return "pdf_extraction_success"
        else:
            print("⚠️ PDF提取完成但没有结果数据")
            return "pdf_extraction_failed"
    
    # 检查是否有实际的提取结果或空文件夹结构
    pdf_extraction_results = state.get("pdf_extraction_results", {})
    api_extraction_results = state.get("api_extraction_results", {})
    
    # 只要有文件夹结构就认为成功，不一定要有PDF文件
    if pdf_extraction_results:
        total_files = 0
        successful_files = 0
        
        for folder_name, folder_data in pdf_extraction_results.items():
            files = folder_data.get("files", [])
            total_files += len(files)
            successful_files += len([f for f in files if f.get("success")])
        
        print(f"📊 PDF提取统计: {successful_files}/{total_files} 文件成功，{len(pdf_extraction_results)}个文件夹")
        
        # 即使没有PDF文件，只要有文件夹结构就认为成功
        print("✅ 检测到PDF提取结果或文件夹结构")
        return "pdf_extraction_success"
    else:
        print("❌ 没有PDF提取结果")
        return "pdf_extraction_failed"
    
    # 检查错误消息
    error_message = state.get("error_message", "")
    if error_message and "pdf" in error_message.lower() and "failed" in error_message.lower():
        print(f"❌ 发现PDF相关错误: {error_message}")
        return "pdf_extraction_failed"
    
    # 默认情况：如果状态不明确，认为是失败
    print("⚠️ PDF提取状态不明确，默认为失败")
    return "pdf_extraction_failed"


def create_parallel_branches(state: AuditState) -> Union[List, str]:
    """
    创建并行分支：从文件处理后分发到多个并行路径
    
    使用LangGraph的Send API实现真正的并行处理：
    1. PDF提取路径
    2. 规则处理路径
    
    Returns:
        Send对象列表，每个对象代表一个并行分支
    """
    if not SEND_AVAILABLE or Send is None:
        print("⚠️ Send API不可用，使用传统路由")
        return "pdf_extraction"  # 退化到传统路由
    
    print("🚀 创建并行分支: PDF提取 + 规则处理")
    
    # 返回多个Send对象，实现并行处理
    return [
        Send("pdf_extraction", state),  # PDF提取路径
        Send("load_rules", state)       # 规则加载路径
    ]


def after_rules_loaded(state: AuditState) -> str:
    """
    规则加载完成后的路由
    
    Returns:
        "extract_rules": 继续提取规则
        "rules_load_failed": 规则加载失败
    """
    current_step = state.get("current_step", "")
    
    if "rules_load_failed" in current_step:
        print("❌ 规则加载失败")
        return "rules_load_failed"
    
    if "rules_loaded" in current_step:
        print("✅ 规则加载成功，继续提取")
        return "extract_rules"
    
    # 检查是否有规则数据
    rules_data = state.get("rules_data", [])
    if rules_data:
        print(f"✅ 发现 {len(rules_data)} 个规则数据，继续提取")
        return "extract_rules"
    
    print("❌ 未找到规则数据")
    return "rules_load_failed"


def check_core_info_for_parallel_validation(state: AuditState) -> Union[List, str]:
    """
    核心信息提取完成后，并行分发到validation和cross_validation节点
    
    确保PDF提取路径的数据也能进入validation节点
    
    Returns:
        Send对象列表，发送到validation和cross_validation
    """
    if not SEND_AVAILABLE or Send is None:
        print("⚠️ Send API不可用，使用传统路由")
        return "validation"  # 退化到传统路由
    
    core_info = state.get("core_info")
    extracted_content = state.get("extracted_content", {})
    
    print(f"🚀 核心信息提取完成，分发到验证节点")
    print(f"📊 核心信息状态: {core_info is not None}")
    print(f"📊 提取内容状态: {len(extracted_content) if extracted_content else 0} 项")
    
    # 并行发送到两个验证节点
    return [
        Send("validation", state),
        Send("cross_validation", state)
    ]


def check_rules_for_validation(state: AuditState) -> Union[List, str]:
    """
    检查规则提取结果，决定是否可以进入验证阶段
    
    使用Send API将规则数据发送到validation和cross_validation节点
    
    Returns:
        Send对象列表，发送到validation和cross_validation
    """
    if not SEND_AVAILABLE or Send is None:
        print("⚠️ Send API不可用，使用传统路由")
        return "validation"  # 退化到传统路由
    
    parsed_rules = state.get("parsed_rules", [])
    current_step = state.get("current_step", "")
    
    # 添加详细调试信息
    print(f"🔍 check_rules_for_validation 调试信息:")
    print(f"   current_step: {current_step}")
    print(f"   parsed_rules 数量: {len(parsed_rules)}")
    print(f"   parsed_rules 内容: {parsed_rules[:2] if parsed_rules else '空'}")
    
    # 修复条件判断：只要有规则就传递给validation
    if parsed_rules and len(parsed_rules) > 0:
        print(f"🚀 规则提取成功，分发到验证节点: {len(parsed_rules)} 条规则")
        
        # 将规则数据发送到两个验证节点
        return [
            Send("validation", state),
            Send("cross_validation", state)
        ]
    elif "rules_extract_skipped" in current_step:
        print("🚨 规则提取已跳过，直接进行基础验证")
        return [Send("validation", state)]
    else:
        print("⚠️ 规则提取未完成或无规则数据，只进行基础验证")
        return [Send("validation", state)]