"""
数据模型包

定义系统中使用的所有数据模型：
- 状态管理模型
- 业务数据模型
- 配置模型

模型使用状态说明：
✅ 高度活跃： CoreInfo, RuleInfo, RuleFileInfo, MaterialProcessingStats
⚠️ 部分使用： ValidationResult, CrossValidationResult, AuditReport
✖️ 已移除： FileInfo, MaterialInfo, ReportSummary
"""

from .state import (
    CoreInfo,
    ValidationResult,
    CrossValidationResult,
    RuleInfo,
    RuleFileInfo,
    AuditReport,
    AuditState,
    MaterialProcessingStats
)

__all__ = [
    "CoreInfo",
    "ValidationResult",
    "CrossValidationResult",
    "RuleInfo",
    "RuleFileInfo",
    "AuditReport",
    "AuditState",
    "MaterialProcessingStats"
]