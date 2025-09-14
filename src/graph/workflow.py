"""
主要的职称评审材料审核工作流定义 - 完全无缓存版本

🚨 已完全取消缓存机制，确保每个节点传输的信息都是全新的、一次性的

包括：
1. ZIP解压和文件夹验证
2. PDF内容提取和核心信息提取
3. 规则集加载和提取（并行处理）
4. 规则校验和交叉验证
5. 报告生成

只包含一个主工作流：create_audit_workflow()
"""

# LangGraph 核心导入 - 移除缓存相关的导入
from langgraph.graph import StateGraph, START, END  # type: ignore

# 导入 RetryPolicy
try:
    from langgraph.types import RetryPolicy  # type: ignore
    RETRY_POLICY_AVAILABLE = True
except ImportError:
    RetryPolicy = None
    RETRY_POLICY_AVAILABLE = False

# 已完全移除 checkpointer 和内存存储器相关导入

from .state import AuditState
from .edges import (
    check_pdf_extraction_status,
    create_parallel_branches,  # 并行分支路由
    after_rules_loaded,        # 规则加载后路由
    check_rules_for_validation, # 规则验证路由
    check_pdf_extraction_for_parallel_processing  # PDF提取并行分发路由
)
from src.tools.langsmith_utils import (
    setup_langsmith_environment,
    event_logger,
    with_langsmith_tracing
)


@with_langsmith_tracing
def create_audit_workflow():
    """
    创建完全无缓存的职称评审材料审核工作流
    
    🚨 已完全取消缓存机制，确保每次传输的信息都是全新的、一次性的
    
    工作流程：
    ZIP解压 -> 并行分支：
      分支1: PDF内容提取 -> 核心信息提取 -> 交叉校验
      分支2: 规则集加载 -> 规则提取 -> 汇入验证
    最后: 报告生成
    
    Returns:
        编译后的LangGraph工作流（无缓存）
    """
    # 延迟导入以避免循环依赖
    from src.nodes import (
        file_processing_node,
        core_info_extraction_node,
        validation_node,
        report_generation_node
    )
    from src.nodes.pdf_extraction import pdf_extraction_node
    from src.nodes.cross_validation import cross_validation_node
    from src.nodes.rules_processing import load_rules_node, extract_rules_node
    
    # 初始化LangSmith环境
    setup_langsmith_environment()
    
    workflow = StateGraph(AuditState)
    
    # 根据LangGraph最佳实践添加重试策略（仅在可用时）
    retry_policy_io = None
    retry_policy_ai = None
    retry_policy_general = None
    
    if RETRY_POLICY_AVAILABLE and RetryPolicy is not None:
        retry_policy_io = RetryPolicy(max_attempts=3, retry_on=[IOError, FileNotFoundError])
        retry_policy_ai = RetryPolicy(max_attempts=5, retry_on=[TimeoutError, ConnectionError])
        retry_policy_general = RetryPolicy(max_attempts=2)
    
    # 添加所有节点并配置重试策略
    workflow.add_node(
        "file_processing", 
        _wrap_node_with_logging(file_processing_node, "file_processing"),
        retry_policy=retry_policy_io
    )
    workflow.add_node(
        "pdf_extraction", 
        _wrap_node_with_logging(pdf_extraction_node, "pdf_extraction"),
        retry_policy=retry_policy_ai
    )
    workflow.add_node(
        "core_info_extraction",
        _wrap_node_with_logging(core_info_extraction_node, "core_info_extraction")
    )
    workflow.add_node(
        "validation",
        _wrap_node_with_logging(validation_node, "validation"),
        retry_policy=retry_policy_ai
    )
    workflow.add_node(
        "cross_validation",
        _wrap_node_with_logging(cross_validation_node, "cross_validation"),
        retry_policy=retry_policy_general
    )
    workflow.add_node(
        "report_generation",
        _wrap_node_with_logging(report_generation_node, "report_generation"),
        retry_policy=retry_policy_general
    )
    workflow.add_node(
        "load_rules",
        _wrap_node_with_logging(load_rules_node, "load_rules"),
        retry_policy=retry_policy_general
    )
    workflow.add_node(
        "extract_rules",
        _wrap_node_with_logging(extract_rules_node, "extract_rules"),
        retry_policy=retry_policy_ai
    )
    
    # 定义工作流边连接：添加规则集并行处理支持
    workflow.add_edge(START, "file_processing")
    
    # 从file_processing分叉到并行处理路径
    workflow.add_conditional_edges(
        "file_processing",
        create_parallel_branches,
        ["pdf_extraction", "load_rules"]  # 支持并行分支
    )
    
    # 规则处理分支
    workflow.add_conditional_edges(
        "load_rules",
        after_rules_loaded,
        {
            "extract_rules": "extract_rules",
            "rules_load_failed": END
        }
    )
    
    # 规则提取完成后，将规则通过条件边传递给validation
    workflow.add_conditional_edges(
        "extract_rules",
        check_rules_for_validation,
        ["validation", "cross_validation"]  # 支持Send API并行分发
    )
    
    # PDF提取后进入核心信息提取（主流程）
    workflow.add_conditional_edges(
        "pdf_extraction",
        check_pdf_extraction_status,
        {
            "pdf_extraction_success": "core_info_extraction",
            "pdf_extraction_failed": END
        }
    )
    
    # 🛠️ 关键修复：简化工作流连接，避免多重触发导致的缓存问题
    # 删除直接边，只使用条件边触发节点，确保数据一致性
    
    # validation和cross_validation完成后进入报告生成
    workflow.add_edge("validation", "report_generation")
    workflow.add_edge("cross_validation", "report_generation")
    workflow.add_edge("core_info_extraction", "report_generation")
    
    workflow.add_edge("report_generation", END)
    
    # 编译工作流 - 完全无缓存版本
    # 🚨 已移除所有checkpointer和内存存储相关的配置
    # 确保每个节点传输的信息都是全新的、一次性的
    return workflow.compile()





def _wrap_node_with_logging(node_func, node_name: str):
    """
    包装节点函数以添加LangSmith日志记录
    
    Args:
        node_func: 节点函数
        node_name: 节点名称
        
    Returns:
        包装后的节点函数
    """
    import asyncio
    import inspect
    
    # 检查节点函数是否为异步函数
    if inspect.iscoroutinefunction(node_func):
        # 异步节点包装器
        async def async_wrapped_node(state):
            try:
                # 记录节点开始
                event_logger.log_node_start(node_name, state)
                
                # 执行异步节点函数
                result = await node_func(state)
                
                # 记录节点完成
                event_logger.log_node_complete(node_name, result)
                
                return result
                
            except Exception as e:
                # 记录节点错误
                event_logger.log_node_error(node_name, e)
                raise
        
        return async_wrapped_node
    else:
        # 同步节点包装器
        def sync_wrapped_node(state):
            try:
                # 记录节点开始
                event_logger.log_node_start(node_name, state)
                
                # 执行节点函数
                result = node_func(state)
                
                # 记录节点完成
                event_logger.log_node_complete(node_name, result)
                
                return result
                
            except Exception as e:
                # 记录节点错误
                event_logger.log_node_error(node_name, e)
                raise
        
        return sync_wrapped_node





# 延迟创建默认工作流，避免循环导入
default_workflow = None

def get_default_workflow():
    """获取默认工作流（延迟创建）"""
    global default_workflow
    if default_workflow is None:
        default_workflow = create_audit_workflow()
    return default_workflow







