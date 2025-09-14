"""
LangSmith集成工具类

提供LangGraph项目的调试、监控和评估功能
"""

import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import getpass

def setup_langsmith_environment():
    """
    设置LangSmith环境变量
    
    根据LangGraph最佳实践配置LangSmith追踪
    """
    def _set_env(var: str):
        """安全地设置环境变量"""
        if not os.environ.get(var):
            # 优先从.env文件读取，如果没有则提示输入
            value = getpass.getpass(f"请输入 {var}: ")
            os.environ[var] = value
    
    # 设置必要的API密钥
    _set_env("LANGSMITH_API_KEY")
    
    # 配置LangSmith追踪
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "Audit_Workflow_Debug")
    os.environ["LANGSMITH_TRACING"] = "true"
    
    print("✅ LangSmith环境配置完成")
    print(f"📊 项目名称: {os.environ['LANGCHAIN_PROJECT']}")


def create_run_config(
    run_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    thread_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建LangGraph运行配置，支持LangSmith追踪
    
    Args:
        run_name: 运行名称
        tags: 标签列表
        metadata: 元数据
        thread_id: 线程ID
        
    Returns:
        配置字典
    """
    config = {}
    
    # 生成唯一的运行ID
    if not config.get("run_id"):
        config["run_id"] = str(uuid.uuid4())
    
    # 设置运行名称
    if run_name:
        config["run_name"] = run_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config["run_name"] = f"audit_workflow_{timestamp}"
    
    # 设置标签
    default_tags = ["audit_workflow", "langgraph", "production"]
    if tags:
        config["tags"] = default_tags + tags
    else:
        config["tags"] = default_tags
    
    # 设置元数据
    default_metadata = {
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "project": "职称评审材料审核系统"
    }
    if metadata:
        default_metadata.update(metadata)
    config["metadata"] = default_metadata
    
    # 设置可配置参数
    configurable = {}
    if thread_id:
        configurable["thread_id"] = thread_id
    
    if configurable:
        config["configurable"] = configurable
    
    return config


def log_workflow_step(step_name: str, status: str, data: Optional[Dict] = None):
    """
    记录工作流步骤，便于调试
    
    Args:
        step_name: 步骤名称
        status: 状态 (started, completed, failed)
        data: 附加数据
    """
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "step": step_name,
        "status": status,
        "data": data or {}
    }
    
    # 使用结构化日志，LangSmith可以捕获
    print(f"🔍 [{timestamp}] {step_name.upper()}: {status}")
    if data:
        print(f"   📝 数据: {data}")


def create_debug_config(breakpoints: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    创建调试配置
    
    Args:
        breakpoints: 断点列表
        
    Returns:
        调试配置
    """
    config = create_run_config(
        run_name="debug_session",
        tags=["debug", "development"],
        metadata={"mode": "debug"}
    )
    
    if breakpoints:
        config["breakpoints"] = breakpoints
    
    # 启用详细追踪
    config["recursion_limit"] = 50
    
    return config


def hide_sensitive_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    隐藏敏感数据，避免在LangSmith中暴露
    
    Args:
        inputs: 输入数据
        
    Returns:
        脱敏后的数据
    """
    copied = inputs.copy()
    
    # 隐藏敏感字段
    sensitive_fields = ["api_key", "password", "token", "secret"]
    
    for key in copied:
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            copied[key] = "***HIDDEN***"
        
        # 隐藏长文本内容
        if isinstance(copied[key], str) and len(copied[key]) > 1000:
            copied[key] = copied[key][:100] + "...[内容过长已截断]"
    
    return copied


class LangSmithEventLogger:
    """LangSmith事件记录器"""
    
    def __init__(self, project_name: str = "Audit_Workflow"):
        self.project_name = project_name
        self.events = []
    
    def log_node_start(self, node_name: str, state: Dict[str, Any]):
        """记录节点开始"""
        event = {
            "type": "node_start",
            "node": node_name,
            "timestamp": datetime.now().isoformat(),
            "state_keys": list(state.keys())
        }
        self.events.append(event)
        log_workflow_step(f"节点开始: {node_name}", "started")
    
    def log_node_complete(self, node_name: str, result: Dict[str, Any]):
        """记录节点完成"""
        event = {
            "type": "node_complete", 
            "node": node_name,
            "timestamp": datetime.now().isoformat(),
            "result_keys": list(result.keys())
        }
        self.events.append(event)
        log_workflow_step(f"节点完成: {node_name}", "completed", {"result_keys": list(result.keys())})
    
    def log_node_error(self, node_name: str, error: Exception):
        """记录节点错误"""
        event = {
            "type": "node_error",
            "node": node_name,
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "error_type": type(error).__name__
        }
        self.events.append(event)
        log_workflow_step(f"节点错误: {node_name}", "failed", {"error": str(error)})
    
    def get_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        return self.events
    
    def clear_events(self):
        """清空事件"""
        self.events.clear()


# 全局事件记录器实例
event_logger = LangSmithEventLogger()


def with_langsmith_tracing(func):
    """
    装饰器：为函数添加LangSmith追踪
    """
    def wrapper(*args, **kwargs):
        from langchain_core.tracers.context import tracing_v2_enabled
        from langsmith import Client
        
        # 创建LangSmith客户端，隐藏敏感数据
        client = Client(
            hide_inputs=hide_sensitive_data,
            hide_outputs=hide_sensitive_data
        )
        
        # 在追踪上下文中执行函数
        with tracing_v2_enabled(client=client):
            return func(*args, **kwargs)
    
    return wrapper


def stream_with_debug(graph, inputs: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
    """
    流式执行图并输出调试信息
    
    Args:
        graph: LangGraph图实例
        inputs: 输入数据
        config: 配置信息
        
    Yields:
        流式输出结果
    """
    if not config:
        config = create_debug_config()
    
    print(f"🚀 开始执行工作流...")
    print(f"📊 运行ID: {config.get('run_id')}")
    print(f"🏷️  标签: {config.get('tags', [])}")
    
    try:
        # 使用debug模式流式执行
        for chunk in graph.stream(inputs, config, stream_mode="debug"):
            print(f"🔍 调试信息: {chunk}")
            yield chunk
            
    except Exception as e:
        print(f"❌ 执行失败: {str(e)}")
        event_logger.log_node_error("workflow", e)
        raise


if __name__ == "__main__":
    # 测试LangSmith配置
    setup_langsmith_environment()
    
    # 测试配置创建
    test_config = create_run_config(
        run_name="test_run",
        tags=["test"],
        metadata={"test": True}
    )
    print(f"测试配置: {test_config}")