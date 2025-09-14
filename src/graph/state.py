"""
LangGraph工作流状态管理

定义审核流程中的状态结构：
- AuditState: 主要的审核状态
- 各个节点间的状态传递规则
- 状态的序列化和反序列化
- 支持并发安全的状态管理
"""

from typing import Dict, List, Any, Optional, TypedDict, Annotated
from dataclasses import dataclass, field
from pathlib import Path
import operator


def step_reducer(existing: str, new: str) -> str:
    """current_step字段的reducer函数：后写入优先，确保并发安全"""
    # 对于步骤状态，使用最新的值（last write wins）
    return new if new else existing


class AuditState(TypedDict):
    """审核工作流状态定义（支持并发安全）

    注意：此处声明的键必须覆盖所有节点读写的字段；
    未在此处声明的字段在LangGraph状态合并时可能被丢弃，
    因而需要在这里统一、规范地进行声明。
    """
    
    # 输入文件信息
    uploaded_file: Optional[str]  # 上传的ZIP压缩包路径
    file_type: str  # 文件类型 (zip)
    extraction_path: Optional[str]  # ZIP解压后的根目录
    extracted_files: Annotated[List[str], operator.add]  # 解压得到的文件列表（并发安全）
    
    # 文件夹结构验证
    folder_validation: Dict[str, Any]  # 17个标准文件夹验证结果
    folder_classification: Dict[str, List[str]]  # 文件夹分类结果 {文件夹名: [.pdf文件列表]}
    
    # PDF内容提取和分析（新增）
    pdf_extraction_results: Dict[str, Any]  # PDF文件提取结果
    api_extraction_results: Dict[str, Any]  # 通过API提取的JSON结果
    
    # PDF API配置（新增）
    pdf_api_endpoint: Optional[str]  # PDF提取API端点
    
    # 内容提取和分析
    extracted_content: Dict[str, Any]  # 从PDF文件提取的内容信息
    content_analysis: Dict[str, Any]  # AI分析的结构化内容
    core_info: Optional[Dict[str, Any]]  # 核心信息（姓名、身份证号等）
    
    # 验证结果（使用reducer确保并发安全）
    material_validation: Dict[str, List[Any]]  # 材料校验结果
    cross_validation: Annotated[List[Any], operator.add]  # 交叉校验结果（并发安全）
    validation_results: Annotated[List[Dict[str, Any]], operator.add]  # 所有校验结果（并发安全）
    # 详细验证结果与摘要（供报告节点直接消费）
    validation_results_detailed: Annotated[List[Dict[str, Any]], operator.add]  # 详细验证结果
    validation_summary: Optional[Dict[str, Any]]  # 验证摘要
    
    # 规则集处理（新增并行处理支持）
    rules_data: Annotated[List[Dict[str, Any]], operator.add]  # 加载的规则集数据（并发安全）
    parsed_rules: List[Any]  # 🚨 移除reducer，直接替换而不是累加规则（支持RuleInfo对象和字典格式）
    rules_by_category: Dict[str, List[Any]]  # 按1-17项分类的规则集
    
    # 缓存管理（新增）
    validation_cache: Annotated[List[Dict[str, Any]], operator.add]  # 验证结果缓存
    cross_validation_cache: Annotated[List[Dict[str, Any]], operator.add]  # 交叉验证结果缓存
    
    # 报告生成
    audit_report: Optional[str]  # 生成的审核报告
    report_path: Optional[str]  # 报告文件路径
    report_summary: Optional[Dict[str, Any]]  # 报告摘要（便于前端展示）
    quality_score: Optional[float]  # 报告质量评分
    compliance_status: Optional[str]  # 合规性状态（PASS/WARNING/FAIL）

    # 处理统计（可选，供调试/展示）
    processing_stats: Optional[Dict[str, Any]]  # 处理统计信息
    
    # 流程控制（使用reducer确保并发安全）
    current_step: Annotated[str, step_reducer]  # 当前步骤（并发安全）
    error_message: Optional[str]  # 错误信息
    warnings: Annotated[List[str], operator.add]  # 警告信息（并发安全）
    processing_logs: Annotated[List[str], operator.add]  # 处理日志（并发安全）
    is_complete: bool  # 是否完成
    
    # 会话管理（LangGraph官方持久化支持）
    session_id: Optional[str]  # 会话ID


@dataclass
class WorkflowConfig:
    """工作流配置"""
    
    # 文件处理配置
    max_file_size: int = 50 * 1024 * 1024  # 50MB (ZIP压缩包)
    supported_formats: List[str] = field(default_factory=lambda: ['.zip'])
    
    # 文件夹验证配置
    required_folders: List[str] = field(default_factory=lambda: [
        "1.教育经历", "2.工作经历", "3.继续教育(培训情况)", "4.学术技术兼职情况",
        "5.获奖情况", "6.获得荣誉称号情况", "7.主持参与科研项目(基金)情况", 
        "8.主持参与工程技术项目情况", "9.论文", "10.著(译)作(教材)",
        "11.专利(著作权)情况", "12.主持参与指定标准情况", 
        "13.成果被批示、采纳、运用和推广情况", "14.资质证书",
        "15.奖惩情况", "16.考核情况", "17.申报材料附件信息"
    ])
    
    # PDF处理配置
    max_pdf_file_size: int = 20 * 1024 * 1024  # 20MB per PDF file
    pdf_api_timeout: int = 60  # PDF API提取超时时间（秒）
    pdf_api_endpoint: Optional[str] = None  # PDF提取API端点
    
    # AI处理配置
    ai_timeout: int = 300  # AI处理超时时间（秒）
    max_retries: int = 3  # 最大重试次数
    
    # 输出配置
    output_dir: str = 'output'
    report_template: str = 'templates/audit_report.html'


def create_initial_state(
    uploaded_file: str,
    session_id: Optional[str] = None
) -> AuditState:
    """创建初始状态（支持并发安全）"""
    
    file_path = Path(uploaded_file)
    file_type = file_path.suffix.lower()
    
    # 尝试从配置获取PDF API端点
    pdf_api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"  # 默认配置
    try:
        from src.config.api_config import get_pdf_api_config
        api_config = get_pdf_api_config()
        configured_endpoint = api_config.get("pdf_extraction_endpoint")
        if configured_endpoint:
            pdf_api_endpoint = configured_endpoint
            print(f"✅ 从配置文件加载PDF API端点: {pdf_api_endpoint}")
        else:
            print(f"⚠️ 配置文件中未找到PDF API端点，使用默认值: {pdf_api_endpoint}")
    except ImportError:
        print(f"⚠️ 无法导入API配置模块，使用默认PDF API端点: {pdf_api_endpoint}")
    except Exception as e:
        print(f"⚠️ 读取API配置失败: {e}，使用默认PDF API端点: {pdf_api_endpoint}")
    
    # 确保API端点不为空
    if not pdf_api_endpoint:
        pdf_api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
        print(f"🔧 强制设置默认PDF API端点: {pdf_api_endpoint}")
    
    return AuditState(
        # 输入文件信息
        uploaded_file=uploaded_file,
        file_type=file_type,
        extraction_path=None,
        extracted_files=[],
        
        # 文件夹结构验证
        folder_validation={},
        folder_classification={},
        
        # PDF内容提取和分析（新增）
        pdf_extraction_results={},
        api_extraction_results={},
        
        # PDF API配置
        pdf_api_endpoint=pdf_api_endpoint,
        
        # 内容提取和分析
        extracted_content={},
        content_analysis={},
        core_info=None,
        
        # 验证结果（初始化为空列表以支持reducer）
        material_validation={},
        cross_validation=[],
        validation_results=[],
        validation_results_detailed=[],
        validation_summary=None,
        
        # 规则集处理（初始化为空列表以支持reducer）
        rules_data=[],
        parsed_rules=[],  # 支持RuleInfo对象和字典格式
        rules_by_category={},
        
        # 缓存管理（新增）
        validation_cache=[],
        cross_validation_cache=[],
        
        # 报告生成
        audit_report=None,
        report_path=None,
        report_summary=None,
        quality_score=None,
        compliance_status=None,
        processing_stats=None,
        
        # 流程控制
        current_step="zip_extraction",
        error_message=None,
        warnings=[],
        processing_logs=[],
        is_complete=False,
        
        # 会话管理
        session_id=session_id
    )


def update_state_step(state: AuditState, step: str) -> Dict[str, Any]:
    """更新状态步骤（并发安全）"""
    # 使用reducer模式更新step，避免直接赋值
    return {"current_step": step}


def add_warning(state: AuditState, warning: str) -> Dict[str, Any]:
    """添加警告信息"""
    return {"warnings": [warning]}


def set_error(state: AuditState, error: str) -> Dict[str, Any]:
    """设置错误信息"""
    return {"error_message": error}


def mark_complete(state: AuditState) -> Dict[str, Any]:
    """标记流程完成（并发安全）"""
    return {
        "is_complete": True,
        "current_step": "completed"
    }
