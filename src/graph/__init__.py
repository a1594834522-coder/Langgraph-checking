"""
LangGraph工作流定义模块

包含系统的主要工作流：
- workflow.py: 主要的审核工作流定义
- state.py: 工作流状态管理
- edges.py: 边和路由逻辑定义
"""

from .workflow import (
    create_audit_workflow,
    get_default_workflow
)

from .state import (
    AuditState,
    WorkflowConfig,
    create_initial_state,
    update_state_step,
    add_warning,
    set_error,
    mark_complete
)

from .edges import (
    should_continue_processing,
    route_folder_validation,
    route_to_cross_validation,
    should_generate_report,
    check_core_info_for_cross_validation,
    check_pdf_extraction_status
)

__all__ = [
    # Workflow functions (优化后的版本，只保留主工作流)
    "create_audit_workflow",
    "get_default_workflow",
    
    # State management
    "AuditState",
    "WorkflowConfig",
    "create_initial_state",
    "update_state_step",
    "add_warning",
    "set_error",
    "mark_complete",
    
    # Edge routing functions
    "should_continue_processing",
    "route_folder_validation",
    "route_to_cross_validation",
    "should_generate_report",
    "check_core_info_for_cross_validation",
    "check_pdf_extraction_status"
]