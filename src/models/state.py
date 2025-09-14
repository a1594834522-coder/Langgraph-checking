"""
数据模型定义

定义审核流程中使用的数据模型（不包括LangGraph状态）

模型使用状态：
- CoreInfo: ✅ 高度活跃 - 在多个节点中实际使用
- RuleInfo: ✅ 高度活跃 - 规则处理核心模型
- ValidationResult: ⚠️ 部分使用 - 主要用作类型注解
- CrossValidationResult: ⚠️ 部分使用 - 主要用作类型注解
- MaterialProcessingStats: ✅ 有效使用 - 在报告生成中实际使用
- AuditReport: ⚠️ 部分功能未启用 - 完善但使用有限

已移除未使用模型：
- FileInfo: ✖️ 已移除 - 几乎未使用
- MaterialInfo: ✖️ 已移除 - 使用场景有限，可用Dict替代
- ReportSummary: ✖️ 已移除 - 完全未使用
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


# ============================================================================
# 核心业务模型（高度活跃）
# ============================================================================
class CoreInfo(BaseModel):
    """核心信息模型（简化版） - ✅ 高度活跃模型"""
    name: str = Field(description="姓名，统一格式，去除空格", default="")
    gender: str = Field(description="性别，男/女", default="")
    id_number: str = Field(description="身份证号，18位标准格式", default="")
    extracted_from: List[str] = Field(description="信息来源材料", default_factory=list)


# ============================================================================
# 校验结果模型（部分使用）
# ============================================================================
class ValidationResult(BaseModel):
    """校验结果模型 - 增强版，完整存储validation节点的所有输出信息"""
    rule_id: str
    rule_name: str
    status: str  # PASS, WARNING, ERROR
    result: str  # "✅通过", "⚠️警告", "❌不通过"
    message: str
    details: str = Field(description="详细描述信息")
    priority: str = Field(description="优先级：高/中/低")
    material_type: str = Field(description="材料类型")
    rule_content: str = Field(description="应用的规则内容", default="")
    ai_powered: bool = Field(description="是否AI驱动的校验", default=False)
    rules_applied: int = Field(description="应用的规则数量", default=0)
    timestamp: str = Field(description="校验时间戳")
    
    @classmethod
    def from_validation_output(cls, validation_dict: Dict[str, Any]) -> "ValidationResult":
        """从validation节点输出的字典创建ValidationResult对象"""
        return cls(
            rule_id=validation_dict.get('rule_name', '').replace(' ', '_'),
            rule_name=validation_dict.get('rule_name', ''),
            status=cls._convert_result_to_status(validation_dict.get('result', '')),
            result=validation_dict.get('result', ''),
            message=validation_dict.get('details', ''),
            details=validation_dict.get('details', ''),
            priority=validation_dict.get('priority', '中'),
            material_type=validation_dict.get('material_type', ''),
            rule_content=validation_dict.get('rule_content', ''),
            ai_powered=validation_dict.get('ai_powered', False),
            rules_applied=validation_dict.get('rules_applied', 0),
            timestamp=validation_dict.get('timestamp', '')
        )
    
    @staticmethod
    def _convert_result_to_status(result: str) -> str:
        """将结果转换为状态"""
        if result.startswith('✅'):
            return 'PASS'
        elif result.startswith('⚠️'):
            return 'WARNING'
        elif result.startswith('❌'):
            return 'ERROR'
        else:
            return 'WARNING'


class ValidationSummary(BaseModel):
    """验证结果摘要模型 - 存储validation节点的完整统计信息"""
    total_materials_processed: int = Field(description="处理的材料数量")
    total_validations: int = Field(description="总校验数量")
    successful_materials: int = Field(description="成功校验的材料数量")
    error_count: int = Field(description="错误数量")
    warning_count: int = Field(description="警告数量")
    pass_count: int = Field(description="通过数量")
    ai_powered_validations: int = Field(description="AI驱动的校验数量")
    total_rules_applied: int = Field(description="应用的规则总数")
    materials_by_type: Dict[str, int] = Field(description="按材料类型统计", default_factory=dict)
    validation_start_time: Optional[str] = Field(description="校验开始时间", default=None)
    validation_end_time: Optional[str] = Field(description="校验结束时间", default=None)
    
    @classmethod
    def from_validation_results(cls, validation_results: List[ValidationResult]) -> "ValidationSummary":
        """从验证结果列表创建摘要"""
        error_count = sum(1 for r in validation_results if r.status == 'ERROR')
        warning_count = sum(1 for r in validation_results if r.status == 'WARNING')
        pass_count = sum(1 for r in validation_results if r.status == 'PASS')
        ai_powered_count = sum(1 for r in validation_results if r.ai_powered)
        total_rules = sum(r.rules_applied for r in validation_results)
        
        materials_by_type = {}
        for result in validation_results:
            mat_type = result.material_type
            materials_by_type[mat_type] = materials_by_type.get(mat_type, 0) + 1
        
        return cls(
            total_materials_processed=len(set(r.material_type for r in validation_results)),
            total_validations=len(validation_results),
            successful_materials=len(set(r.material_type for r in validation_results if r.status != 'ERROR')),
            error_count=error_count,
            warning_count=warning_count,
            pass_count=pass_count,
            ai_powered_validations=ai_powered_count,
            total_rules_applied=total_rules,
            materials_by_type=materials_by_type
        )


class CrossValidationResult(BaseModel):
    """交叉校验结果模型 - ⚠️ 主要用作类型注解，实际多使用Dict"""
    validation_type: str  # name_consistency, id_consistency, time_logic, data_rationality
    status: str  # PASS, WARNING, ERROR
    message: str
    conflicts: List[str] = []


# ============================================================================
# 规则相关模型（高度活跃）
# ============================================================================
class RuleInfo(BaseModel):
    """规则信息模型 - ✅ 高度活跃模型，在rules_processing和validation中大量使用"""
    rule_id: str = Field(description="规则唯一标识")
    content: str = Field(description="规则内容")
    source_file: str = Field(description="来源文件名")
    category: str = Field(description="1-17中的分类编号", default="17")
    priority: str = Field(description="优先级", default="normal")


class RuleFileInfo(BaseModel):
    """规则文件信息模型 - ✅ 在rules_processing中使用"""
    file_name: str = Field(description="规则文件名")
    file_path: str = Field(description="文件完整路径")
    file_type: str = Field(description="文件类型 (.xlsx 或 .md)")
    size: int = Field(description="文件大小或规则数量")
    content: Optional[str] = Field(description="文件原始内容（仅Markdown文件）", default=None)
    extracted_rules: Optional[List[RuleInfo]] = Field(description="提取的规则列表（仅Excel文件）", default=None)


# ============================================================================
# 状态管理模型
# ============================================================================
class AuditState(BaseModel):
    """审核工作流状态定义（业务数据模型）"""
    
    # 输入文件信息
    uploaded_file: Optional[str] = None  # 上传的文件路径
    file_type: str = ""  # 文件类型 (zip/pdf/doc等)
    
    # 文件处理结果
    extracted_files: List[str] = Field(default_factory=list)  # 解压后的文件列表
    file_classification: Dict[str, str] = Field(default_factory=dict)  # 文件分类结果
    
    # PDF处理
    pdf_analysis: Dict[str, Any] = Field(default_factory=dict)  # PDF页数分析结果
    pdf_chunks: Dict[str, List[str]] = Field(default_factory=dict)  # PDF分片结果
    
    # 内容提取
    extracted_content: Dict[str, Any] = Field(default_factory=dict)  # 提取的内容信息
    core_info: Optional[Dict[str, Any]] = None  # 核心信息（姓名、身份证号）
    
    # 规则处理
    rules_data: List[RuleFileInfo] = Field(default_factory=list)  # 加载的规则文件数据
    parsed_rules: List[RuleInfo] = Field(default_factory=list)  # 解析后的规则列表
    rules_by_category: Dict[str, List[RuleInfo]] = Field(default_factory=dict)  # 按1-17项分类的规则
    
    # 验证结果（完整存储）
    validation_results_detailed: List[ValidationResult] = Field(description="详细的验证结果列表", default_factory=list)
    validation_summary: Optional[ValidationSummary] = Field(description="验证结果摘要", default=None)
    material_validation: Dict[str, List[Any]] = Field(default_factory=dict)  # 材料校验结果（兼容）
    cross_validation: List[Any] = Field(default_factory=list)  # 交叉校验结果（并发安全）
    validation_results: List[Dict[str, Any]] = Field(default_factory=list)  # 所有校验结果（兼容）
    
    # 报告生成
    audit_report: Optional["AuditReport"] = None  # 生成的审核报告对象
    report_path: Optional[str] = None  # 报告文件路径
    
    # 流程控制
    current_step: str = "file_processing"  # 当前步骤
    error_message: Optional[str] = None  # 错误信息
    warnings: List[str] = Field(default_factory=list)  # 警告信息
    processing_logs: List[str] = Field(default_factory=list)  # 处理日志
    is_complete: bool = False  # 是否完成
    
    # Redis缓存相关
    session_id: Optional[str] = None  # 会话ID


# ============================================================================
# 报告相关模型（部分功能未启用）
# ============================================================================


class AuditReport(BaseModel):
    """审核报告模型（增强版） - ⚠️ 完善但使用有限，主要作为类型注解"""
    
    # 报告基本信息
    report_id: str = Field(description="报告唯一标识")
    generated_at: str = Field(description="生成时间")
    report_version: str = Field(description="报告版本", default="v2.0")
    
    # 申报人信息
    applicant_info: CoreInfo = Field(description="申报人核心信息")
    
    # 审核摘要
    summary: Dict[str, Any] = Field(description="审核结果摘要", default_factory=dict)
    
    # 材料处理统计
    processing_stats: Dict[str, Any] = Field(description="处理统计信息", default_factory=dict)
    
    # 校验结果分类（按严重程度）
    severe_issues: List[ValidationResult] = Field(description="严重问题", default_factory=list)
    warnings: List[ValidationResult] = Field(description="警告问题", default_factory=list)
    suggestions: List[ValidationResult] = Field(description="建议优化", default_factory=list)
    passed_validations: List[ValidationResult] = Field(description="通过的校验", default_factory=list)
    
    # 交叉校验结果
    cross_validation_results: List[CrossValidationResult] = Field(description="交叉校验结果", default_factory=list)
    
    # 按材料分类的结果
    material_results: Dict[str, List[ValidationResult]] = Field(description="按材料类型分类的结果", default_factory=dict)
    
    # 规则应用统计
    rules_applied: Dict[str, Any] = Field(description="应用的规则统计", default_factory=dict)
    
    # HTML报告内容
    html_content: Optional[str] = Field(description="生成的HTML报告内容", default=None)
    
    # 报告文件路径
    file_path: Optional[str] = Field(description="报告文件保存路径", default=None)
    
    # 质量评分
    quality_score: Optional[float] = Field(description="材料质量评分(0-100)", default=None)
    
    # 合规性评估
    compliance_status: str = Field(description="合规性状态", default="PENDING")  # PASS/WARNING/FAIL/PENDING
    
    # 建议措施
    recommendations: List[str] = Field(description="改进建议", default_factory=list)
    
    # 审核日志
    audit_logs: List[str] = Field(description="审核过程日志", default_factory=list)
    
    @classmethod
    def create_from_state(cls, state: Any, report_id: str) -> "AuditReport":
        """从审核状态创建报告"""
        from datetime import datetime
        
        # 获取核心信息
        core_info = state.get('core_info') or {} if hasattr(state, 'get') else getattr(state, 'core_info', None) or {}
        
        # 处理字典和对象访问
        def get_state_value(key: str, default=None):
            if hasattr(state, 'get'):  # 字典类型
                return state.get(key, default)
            else:  # 对象类型
                return getattr(state, key, default)
        
        applicant_info = CoreInfo(
            name=core_info.get('name', '') if isinstance(core_info, dict) else '',
            gender=core_info.get('gender', '') if isinstance(core_info, dict) else '',
            id_number=core_info.get('id_number', '') if isinstance(core_info, dict) else '',
            extracted_from=core_info.get('extracted_from', []) if isinstance(core_info, dict) else []
        )
        
        # 创建报告实例
        audit_logs = get_state_value('processing_logs', [])
        if not isinstance(audit_logs, list):
            audit_logs = []
        
        return cls(
            report_id=report_id,
            generated_at=datetime.now().isoformat(),
            applicant_info=applicant_info,
            processing_stats=MaterialProcessingStats.from_state(state).dict(),
            audit_logs=audit_logs
        )
    
    def calculate_quality_score(self) -> float:
        """计算质量评分"""
        total_validations = len(self.severe_issues) + len(self.warnings) + len(self.passed_validations)
        if total_validations == 0:
            return 100.0
        
        # 计算分数：错误扣分更多，警告扣分较少
        error_penalty = len(self.severe_issues) * 10
        warning_penalty = len(self.warnings) * 3
        total_penalty = error_penalty + warning_penalty
        
        score = max(0, 100 - total_penalty)
        return score
    
    def determine_compliance_status(self) -> str:
        """确定合规性状态"""
        if len(self.severe_issues) > 0:
            return "FAIL"
        elif len(self.warnings) > 0:
            return "WARNING"
        else:
            return "PASS"
    
    def get_summary_dict(self) -> Dict[str, Any]:
        """获取摘要字典"""
        return {
            "total_validations": len(self.severe_issues) + len(self.warnings) + len(self.passed_validations),
            "error_count": len(self.severe_issues),
            "warning_count": len(self.warnings),
            "passed_count": len(self.passed_validations),
            "cross_validation_count": len(self.cross_validation_results),
            "quality_score": self.quality_score or self.calculate_quality_score(),
            "compliance_status": self.compliance_status
        }


# ============================================================================
# 统计模型（有效使用）
# ============================================================================


class MaterialProcessingStats(BaseModel):
    """材料处理统计模型 - ✅ 在AuditReport中有实际应用"""
    files_extracted: int = Field(description="解压文件数量", default=0)
    pdfs_processed: int = Field(description="处理的PDF数量", default=0)
    content_extracted: bool = Field(description="内容提取成功", default=False)
    core_info_extracted: bool = Field(description="核心信息提取成功", default=False)
    categories_classified: List[str] = Field(description="已分类的材料类型", default_factory=list)
    
    @classmethod
    def from_state(cls, state: Any) -> "MaterialProcessingStats":
        """从审核状态创建处理统计"""
        # 处理字典和对象访问
        def get_state_value(key: str, default=None):
            if hasattr(state, 'get'):  # 字典类型
                return state.get(key, default)
            else:  # 对象类型
                return getattr(state, key, default)
        
        extracted_files = get_state_value('extracted_files', []) or []
        extracted_content = get_state_value('extracted_content', {}) or {}
        core_info = get_state_value('core_info')
        
        return cls(
            files_extracted=len(extracted_files),
            pdfs_processed=len([f for f in extracted_files if f.lower().endswith('.pdf')]),
            content_extracted=len(extracted_content) > 0,
            core_info_extracted=bool(core_info and (
                core_info.get('name') or core_info.get('id_number') 
                if isinstance(core_info, dict) else False
            )),
            categories_classified=list(extracted_content.keys()) if extracted_content else []
        )