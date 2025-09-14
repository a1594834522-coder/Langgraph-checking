"""
主要的职称评审材料审核代理

基于LangGraph框架的完整审核系统入口
集成LangSmith调试和监控功能
"""

import os
from typing import Dict, Any, Optional

# 定义RunnableConfig为类型别名，避免对langchain_core的依赖
RunnableConfig = Dict[str, Any]

# 导入工作流模块
try:
    # 优先使用绝对导入
    from src.graph.workflow import create_audit_workflow
except ImportError:
    try:
        # 如果绝对导入失败，尝试相对导入
        import sys
        import os
        # 添加项目根目录到Python路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.graph.workflow import create_audit_workflow
    except ImportError:
        try:
            # 最后尝试从当前目录导入
            from graph.workflow import create_audit_workflow
        except ImportError:
            raise ImportError("无法导入工作流模块，请检查项目结构")

# 导入状态模块
try:
    from src.graph.state import (
        AuditState,
        create_initial_state
    )
except ImportError:
    try:
        from graph.state import (
            AuditState,
            create_initial_state
        )
    except ImportError:
        # 如果都失败，尝试使用系统路径
        import sys
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        try:
            from src.graph.state import (
                AuditState,
                create_initial_state
            )
        except ImportError:
            raise ImportError("无法导入状态模块，请检查项目结构")

try:
    from src.config.api_config import configure_pdf_api
except ImportError:
    try:
        from config.api_config import configure_pdf_api
    except ImportError:
        def configure_pdf_api(*args, **kwargs):
            print("⚠️ API配置模块未加载，使用默认配置")

# 删除未使用的 configure_pdf_api_endpoint 导入

try:
    from src.tools.langsmith_utils import setup_langsmith_environment
except ImportError:
    try:
        from tools.langsmith_utils import setup_langsmith_environment
    except ImportError:
        def setup_langsmith_environment():
            print("⚠️ LangSmith工具未加载")

# 初始化主工作流
if os.getenv("LANGSMITH_API_KEY"):
    setup_langsmith_environment()
    print("✅ LangSmith追踪已启用")
    
# 使用统一的主工作流
graph = create_audit_workflow()
print("✅ 主审核工作流已就绪")

# 导出主要接口
__all__ = [
    "graph",
    "run_audit",
    "run_audit_with_tracing",
    "debug_audit",
    "configure_pdf_api",
    "run_pdf_audit",
    "AuditState",
    "create_initial_state"
]


async def run_audit(uploaded_file: str, session_id: Optional[str] = None) -> dict:
    """
    运行审核工作流的便捷函数（异步版本）
    
    Args:
        uploaded_file: 上传的文件路径
        session_id: 会话ID（可选）
        
    Returns:
        审核结果
    """
    # 创建初始状态
    initial_state = create_initial_state(uploaded_file, session_id)
    
    # 确保PDF API端点配置（修复：在ZIP文件审核中也设置）
    if not initial_state.get("pdf_api_endpoint"):
        api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
        initial_state["pdf_api_endpoint"] = api_endpoint
        print(f"🔧 为ZIP文件审核设置PDF API端点: {api_endpoint}")
    
    # 为基础审核模式创建配置
    config = None
    if session_id:
        config = {"configurable": {"thread_id": session_id}}
    
    try:
        # 执行工作流（使用异步API）
        print(f"🚀 开始审核流程: {uploaded_file}")
        if config:
            result = await graph.ainvoke(initial_state, config)  # type: ignore
        else:
            result = await graph.ainvoke(initial_state)
        
        print(f"✅ 审核完成! 最终状态: {result.get('current_step', '未知')}")
        return result
        
    except Exception as e:
        print(f"❌ 审核失败: {str(e)}")
        return {
            "error": str(e), 
            "current_step": "failed",
            "error_message": str(e)
        }


async def run_audit_with_tracing(
    uploaded_file: str, 
    session_id: Optional[str] = None,
    run_name: Optional[str] = None,
    tags: Optional[list] = None
) -> dict:
    """
    运行带LangSmith追踪的审核工作流（异步版本）
    
    Args:
        uploaded_file: 上传的文件路径
        session_id: 会话ID（可选）
        run_name: 运行名称
        tags: 标签列表
        
    Returns:
        审核结果
    """
    try:
        from src.tools.langsmith_utils import create_run_config, with_langsmith_tracing
        
        # 创建初始状态
        initial_state = create_initial_state(uploaded_file, session_id)
        
        # 确保PDF API端点配置（修复：在带追踪审核中也设置）
        if not initial_state.get("pdf_api_endpoint"):
            api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
            initial_state["pdf_api_endpoint"] = api_endpoint
            print(f"🔧 为带追踪审核设置PDF API端点: {api_endpoint}")
        
        # 创建带追踪的配置
        config = create_run_config(
            run_name=run_name or f"audit_with_tracing_{session_id or 'default'}",
            tags=tags or ["web", "tracing", "production"],
            thread_id=session_id
        )
        
        print(f"🔍 开始带追踪的审核流程: {uploaded_file}")
        print(f"📊 运行名称: {config.get('run_name')}")
        print(f"🏷️  标签: {config.get('tags', [])}")
        
        # 使用带追踪的图执行（异步版本）
        @with_langsmith_tracing
        async def traced_audit():
            return await graph.ainvoke(initial_state, config)  # type: ignore
        
        result = await traced_audit()
        
        print(f"✅ 带追踪审核完成! 最终状态: {result.get('current_step', '未知')}")
        return result
        
    except Exception as e:
        print(f"❌ 带追踪审核失败: {str(e)}")
        return {
            "error": str(e),
            "current_step": "failed", 
            "error_message": str(e)
        }


async def debug_audit(
    uploaded_file: str,
    session_id: Optional[str] = None,
    breakpoints: Optional[list] = None
) -> dict:
    """
    运行调试模式的审核工作流（异步版本）
    
    Args:
        uploaded_file: 上传的文件路径
        session_id: 会话ID（可选）
        breakpoints: 断点列表
        
    Returns:
        审核结果
    """
    try:
        from src.tools.langsmith_utils import create_debug_config, event_logger
        
        # 创建初始状态
        initial_state = create_initial_state(uploaded_file, session_id)
        
        # 确保PDF API端点配置（修复：在调试模式中也设置）
        if not initial_state.get("pdf_api_endpoint"):
            api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
            initial_state["pdf_api_endpoint"] = api_endpoint
            print(f"🔧 为调试模式设置PDF API端点: {api_endpoint}")
        
        # 创建调试配置
        config = create_debug_config(breakpoints=breakpoints)
        if session_id:
            config["configurable"] = {"thread_id": session_id}
        
        print(f"🐛 开始调试模式审核流程: {uploaded_file}")
        print(f"🔧 断点: {breakpoints or ['无']}")
        
        # 清空事件日志
        event_logger.clear_events()
        
        # 执行工作流（异步版本）
        result = await graph.ainvoke(initial_state, config)  # type: ignore
        
        # 收集调试信息
        debug_events = event_logger.get_events()
        
        print(f"✅ 调试模式审核完成! 最终状态: {result.get('current_step', '未知')}")
        print(f"📝 记录了 {len(debug_events)} 个调试事件")
        
        # 在结果中包含调试信息
        result["debug_events"] = debug_events
        return result
        
    except Exception as e:
        print(f"❌ 调试模式审核失败: {str(e)}")
        return {
            "error": str(e),
            "current_step": "failed",
            "error_message": str(e)
        }


async def run_pdf_audit(
    uploaded_file: str,
    api_endpoint: str,
    session_id: Optional[str] = None,
    with_tracing: bool = False
) -> dict:
    """
    运行PDF审核工作流（异步版本）
    
    Args:
        uploaded_file: 上传的ZIP文件路径
        api_endpoint: PDF提取API端点
        session_id: 会话ID（可选）
        with_tracing: 是否启用LangSmith追踪
        
    Returns:
        审核结果
    """
    try:
        # 配置PDF API端点
        configure_pdf_api(api_endpoint)
        print(f"🔧 已配置PDF提取API: {api_endpoint}")
        
        # 创建初始状态
        initial_state = create_initial_state(uploaded_file, session_id)
        
        # 直接设置API端点（现在AuditState已经支持这个字段）
        initial_state["pdf_api_endpoint"] = api_endpoint
        
        # 选择执行模式
        if with_tracing:
            print(f"🔍 开始PDF审核流程（启用追踪）: {uploaded_file}")
            return await run_audit_with_tracing(
                uploaded_file, 
                session_id, 
                run_name=f"pdf_audit_{session_id or 'default'}",
                tags=["pdf", "api_extraction", "production"]
            )
        else:
            print(f"🚀 开始PDF审核流程: {uploaded_file}")
            
            # 为基础审核模式创建配置
            config = None
            if session_id:
                config = {"configurable": {"thread_id": session_id}}
            
            # 执行工作流（异步版本）
            if config:
                result = await graph.ainvoke(initial_state, config)  # type: ignore
            else:
                result = await graph.ainvoke(initial_state)
            
            print(f"✅ PDF审核完成! 最终状态: {result.get('current_step', '未知')}")
            return result
            
    except Exception as e:
        print(f"❌ PDF审核失败: {str(e)}")
        return {
            "error": str(e),
            "current_step": "failed",
            "error_message": str(e),
            "pdf_api_endpoint": api_endpoint
        }





async def main_async():
    """命令行入口点（异步版本）"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='LangGraph 职称材料审核系统')
    parser.add_argument('file_path', help='要审核的ZIP文件路径')
    parser.add_argument('--session-id', help='会话ID（可选）')

    
    args = parser.parse_args()
    
    # 统一使用主审核函数（异步版本）
    result = await run_audit(args.file_path, args.session_id)
    print(f"✅ 审核结果: {result}")
    
    return result

def main():
    """命令行入口点（用于pyproject.toml脚本配置）"""
    import asyncio
    return asyncio.run(main_async())


if __name__ == "__main__":
    # 示例用法
    import os
    import asyncio
    
    async def example_usage():
        # 检查测试数据
        test_file = "test_data/sample.zip"
        
        if os.path.exists(test_file):
            print("🧪 运行测试审核...")
            result = await run_audit(test_file)
            print(f"📊 审核结果: {result}")
        else:
            print("📋 主代理已就绪，可以通过以下方式使用:")
            print("  from src.agent import run_audit")
            print("  import asyncio")
            print("  result = asyncio.run(run_audit('path/to/your/file.zip'))")
            print("\n🔧 或者直接使用图对象:")
            print("  from src.agent import graph")
            print("  result = await graph.ainvoke(initial_state)")
    
    asyncio.run(example_usage())