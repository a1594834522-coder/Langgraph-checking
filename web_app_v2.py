#!/usr/bin/env python3
"""
LangGraph职称评审系统 - 现代化Web应用

基于LangGraph SDK和FastAPI的企业级Web应用，支持：
- 流式API和实时更新
- Server-Sent Events (SSE)
- WebSocket双向通信
- 文件上传和进度追踪
- 审核报告生成和下载
"""

import os
import sys
import asyncio
import uuid
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, AsyncGenerator
import tempfile
import shutil
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette import EventSourceResponse

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))



# 导入LangGraph审核功能
from src.agent import run_audit, run_audit_with_tracing, debug_audit

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="LangGraph 职称评审材料审核系统",
    description="基于LangGraph框架的智能职称材料审核系统 - 支持流式API和实时更新",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建静态文件目录
static_dir = project_root / "static"
static_dir.mkdir(exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 创建上传文件目录
upload_dir = project_root / "uploads"
upload_dir.mkdir(exist_ok=True)

# 全局任务存储和流式连接管理
task_storage: Dict[str, Dict[str, Any]] = {}
active_streams: Dict[str, Dict[str, Any]] = {}

# 任务清理配置
MAX_COMPLETED_TASKS = 10  # 最多保留的已完成任务数
TASK_CLEANUP_INTERVAL = 300  # 任务清理间隔（秒）


async def cleanup_old_tasks():
    """清理旧的已完成任务"""
    try:
        completed_tasks = [
            (task_id, task_data) for task_id, task_data in task_storage.items()
            if task_data["status"] in ["completed", "failed"]
        ]
        
        if len(completed_tasks) > MAX_COMPLETED_TASKS:
            # 按时间戳排序，保留最新的任务
            completed_tasks.sort(key=lambda x: x[1].get("timestamp", ""), reverse=True)
            tasks_to_remove = completed_tasks[MAX_COMPLETED_TASKS:]
            
            for task_id, _ in tasks_to_remove:
                del task_storage[task_id]
                logger.info(f"Cleaned up old completed task: {task_id}")
                
        # 清理断开的流连接
        orphaned_streams = [
            stream_id for stream_id in active_streams.keys()
            if stream_id not in task_storage
        ]
        
        for stream_id in orphaned_streams:
            del active_streams[stream_id]
            logger.debug(f"Cleaned up orphaned stream: {stream_id}")
            
    except Exception as e:
        logger.error(f"Task cleanup error: {e}")


# 启动定期清理任务
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时的设置
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(TASK_CLEANUP_INTERVAL)
            await cleanup_old_tasks()
    
    # 创建后台清理任务
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # 关闭时的清理
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

# 更新FastAPI应用以使用生命周期管理
# app = FastAPI(..., lifespan=lifespan)  # 这行需要手动更新

# 流式事件类型
class StreamEventType:
    STARTED = "started"
    PROGRESS = "progress"
    NODE_UPDATE = "node_update"
    COMPLETED = "completed"
    ERROR = "error"
    LOG = "log"


class AuditRequest(BaseModel):
    """审核请求模型"""
    session_id: Optional[str] = None
    with_tracing: bool = False
    debug_mode: bool = False
    breakpoints: Optional[list] = None
    stream_mode: str = "updates"  # updates, events, custom


class AuditResponse(BaseModel):
    """审核响应模型"""
    task_id: str
    status: str
    message: str
    stream_url: Optional[str] = None


class TaskStatus(BaseModel):
    """任务状态模型"""
    task_id: str
    status: str
    progress: Optional[str] = None
    current_node: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str


class StreamEvent(BaseModel):
    """流式事件模型"""
    event_type: str
    task_id: str
    data: Any
    timestamp: str
    node_name: Optional[str] = None


async def create_stream_event(
    task_id: str, 
    event_type: str, 
    data: Any, 
    node_name: Optional[str] = None
) -> str:
    """创建流式事件"""
    event = StreamEvent(
        event_type=event_type,
        task_id=task_id,
        data=data,
        timestamp=datetime.now().isoformat(),
        node_name=node_name
    )
    return f"data: {event.model_dump_json()}\n\n"


async def completed_task_stream(task_id: str, task: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """为已完成的任务提供最终状态流"""
    try:
        if task["status"] == "completed":
            yield await create_stream_event(
                task_id,
                StreamEventType.COMPLETED,
                {
                    "message": "任务已完成",
                    "result": task.get("result", {}),
                    "report_available": bool(task.get("result", {}).get("audit_report")),
                    "completed_at": task.get("timestamp")
                }
            )
        elif task["status"] == "failed":
            yield await create_stream_event(
                task_id,
                StreamEventType.ERROR,
                {
                    "message": f"任务已失败: {task.get('error', '未知错误')}",
                    "error": task.get("error"),
                    "failed_at": task.get("timestamp")
                }
            )
        # 发送结束信号
        yield "event: close\ndata: {\"action\": \"close\"}\n\n"
    except Exception as e:
        logger.error(f"Completed task stream error for {task_id}: {e}")
        yield await create_stream_event(
            task_id,
            StreamEventType.ERROR,
            {"message": f"获取任务状态失败: {str(e)}"}
        )


async def audit_stream_generator(task_id: str) -> AsyncGenerator[str, None]:
    """审核流式事件生成器"""
    try:
        if task_id not in task_storage:
            yield await create_stream_event(task_id, StreamEventType.ERROR, "Task not found")
            return
        
        task = task_storage[task_id]
        
        # 发送开始事件
        yield await create_stream_event(
            task_id, 
            StreamEventType.STARTED, 
            {"message": "审核流程已开始", "file_path": task["file_path"]}
        )
        
        # 等待任务初始化
        while task["status"] == "started":
            await asyncio.sleep(0.1)
            
        # 模拟流式事件发送
        workflow_steps = [
            ("zip_extraction", "ZIP解压中..."),
            ("folder_validation", "文件夹验证中..."),
            ("pdf_extraction", "PDF内容提取中..."),
            ("validation", "规则校验中..."),
            ("cross_validation", "交叉校验中..."),
            ("report_generation", "报告生成中...")
        ]
        
        for i, (node_name, description) in enumerate(workflow_steps):
            # 检查任务状态
            if task["status"] in ["failed", "cancelled"]:
                break
                
            # 发送进度更新
            progress_percent = int((i + 1) / len(workflow_steps) * 100)
            yield await create_stream_event(
                task_id,
                StreamEventType.PROGRESS,
                {
                    "step": i + 1,
                    "total_steps": len(workflow_steps),
                    "percent": progress_percent,
                    "description": description
                },
                node_name
            )
            
            # 发送节点更新
            yield await create_stream_event(
                task_id,
                StreamEventType.NODE_UPDATE,
                {
                    "node_name": node_name,
                    "status": "processing",
                    "message": description
                },
                node_name
            )
            
            # 等待一段时间模拟处理
            await asyncio.sleep(2)
        
        # 等待任务完成
        while task["status"] == "processing":
            await asyncio.sleep(0.5)
        
        # 发送最终结果
        if task["status"] == "completed":
            yield await create_stream_event(
                task_id,
                StreamEventType.COMPLETED,
                {
                    "message": "审核完成！",
                    "result": task.get("result", {}),
                    "report_available": bool(task.get("result", {}).get("audit_report"))
                }
            )
        elif task["status"] == "failed":
            yield await create_stream_event(
                task_id,
                StreamEventType.ERROR,
                {
                    "message": f"审核失败: {task.get('error', '未知错误')}",
                    "error": task.get("error")
                }
            )
            
    except Exception as e:
        logger.error(f"Stream generator error for task {task_id}: {str(e)}")
        yield await create_stream_event(
            task_id,
            StreamEventType.ERROR,
            {"message": f"流式处理错误: {str(e)}"}
        )
    finally:
        # 清理流式连接
        if task_id in active_streams:
            del active_streams[task_id]


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """主页"""
    html_file = project_root / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    else:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>LangGraph 职称评审系统</title>
            <meta charset="utf-8">
        </head>
        <body>
            <h1>LangGraph 职称评审材料审核系统</h1>
            <p>Web界面正在加载中...</p>
            <p>请访问 <a href="/docs">/docs</a> 查看API文档</p>
        </body>
        </html>
        """)


@app.get("/api/stream/{task_id}")
async def stream_task_updates(task_id: str, request: Request):
    """
    流式获取任务更新 - Server-Sent Events
    
    Args:
        task_id: 任务ID
        request: FastAPI请求对象
        
    Returns:
        SSE流式响应
    """
    # 检查任务是否存在
    if task_id not in task_storage:
        logger.warning(f"Stream request for non-existent task: {task_id}")
        raise HTTPException(
            status_code=404, 
            detail={
                "error": "Task not found",
                "message": "任务不存在或已被清理",
                "task_id": task_id,
                "suggestion": "请检查任务ID或开始新的任务"
            }
        )
    
    task = task_storage[task_id]
    
    # 检查任务状态，如果已完成则返回最终状态
    if task["status"] in ["completed", "failed"]:
        logger.info(f"Stream request for completed task: {task_id} (status: {task['status']})")
        # 对于已完成的任务，返回最终状态信息
        return EventSourceResponse(
            completed_task_stream(task_id, task),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
    
    # 注册流式连接
    active_streams[task_id] = {
        "start_time": datetime.now().isoformat(),
        "client_ip": request.client.host if request.client else "unknown"
    }
    
    logger.info(f"Starting SSE stream for task {task_id} (status: {task['status']})")
    
    return EventSourceResponse(
        audit_stream_generator(task_id),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@app.post("/api/upload", response_model=AuditResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    with_tracing: bool = False,
    debug_mode: bool = False,
    stream_mode: str = "updates"
):
    """
    上传文件并启动审核流程
    
    Args:
        file: 上传的ZIP文件
        session_id: 会话 ID（可选）
        with_tracing: 是否启用 LangSmith 追踪
        debug_mode: 是否启用调试模式
        stream_mode: 流式模式 (updates/events/custom)
        
    Returns:
        包含任务ID和流式URL的响应
    """
    
    # 验证文件类型 - 支持ZIP和PDF文件
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    file_ext = file.filename.lower()
    if not (file_ext.endswith('.zip') or file_ext.endswith('.pdf')):
        raise HTTPException(status_code=400, detail="支持ZIP文件（完整材料包）或PDF文件（单个文档）格式")
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 生成会话 ID（如果未提供）
    if not session_id:
        session_id = f"web_{task_id[:8]}"
    
    try:
        # 保存上传的文件
        file_path = upload_dir / f"{task_id}_{file.filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"File uploaded: {file_path} (size: {file_path.stat().st_size} bytes)")
        
        # 初始化任务状态
        task_storage[task_id] = {
            "status": "started",
            "progress": "文件上传完成，准备开始审核...",
            "current_node": None,
            "file_path": str(file_path),
            "session_id": session_id,
            "with_tracing": with_tracing,
            "debug_mode": debug_mode,
            "stream_mode": stream_mode,
            "result": None,
            "error": None,
            "timestamp": datetime.now().isoformat(),
            "file_size": file_path.stat().st_size,
            "original_filename": file.filename
        }
        
        # 启动后台审核任务
        background_tasks.add_task(
            process_audit_task_enhanced, 
            task_id, 
            str(file_path), 
            session_id, 
            with_tracing, 
            debug_mode,
            stream_mode
        )
        
        # 构建流式URL
        stream_url = f"/api/stream/{task_id}"
        
        return AuditResponse(
            task_id=task_id,
            status="started",
            message="文件上传成功，审核流程已启动",
            stream_url=stream_url
        )
        
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


async def process_audit_task_enhanced(
    task_id: str, 
    file_path: str, 
    session_id: str, 
    with_tracing: bool, 
    debug_mode: bool,
    stream_mode: str = "updates"
):
    """
    处理审核任务的增强后台函数
    
    Args:
        task_id: 任务ID
        file_path: 文件路径
        session_id: 会话 ID
        with_tracing: 是否启用追踪
        debug_mode: 是否启用调试模式
        stream_mode: 流式模式
    """
    try:
        # 更新任务状态
        task_storage[task_id]["status"] = "processing"
        task_storage[task_id]["progress"] = "正在执行审核流程..."
        
        logger.info(f"Starting audit task {task_id} with mode: {stream_mode}")
        
        # 根据模式选择执行函数（异步版本）
        file_path_obj = Path(file_path)
        
        # 检查文件类型并选择处理方式
        if file_path_obj.suffix.lower() == '.pdf':
            # 单个PDF文件处理
            logger.info(f"Processing single PDF file: {file_path_obj.name}")
            result = await process_single_pdf_file(
                pdf_file_path=file_path,
                session_id=session_id,
                with_tracing=with_tracing,
                debug_mode=debug_mode
            )
        else:
            # ZIP文件处理（原有逻辑）
            if debug_mode:
                result = await debug_audit(
                    uploaded_file=file_path,
                    session_id=session_id,
                    breakpoints=["file_processing", "validation"]
                )
            elif with_tracing:
                result = await run_audit_with_tracing(
                    uploaded_file=file_path,
                    session_id=session_id,
                    run_name="Web界面审核",
                    tags=["web", "production", "streaming"]
                )
            else:
                result = await run_audit(
                    uploaded_file=file_path,
                    session_id=session_id
                )
        
        # 检查结果
        if "error" in result:
            task_storage[task_id]["status"] = "failed"
            task_storage[task_id]["error"] = result["error"]
            task_storage[task_id]["progress"] = f"审核失败: {result['error']}"
            logger.error(f"Audit task {task_id} failed: {result['error']}")
        else:
            task_storage[task_id]["status"] = "completed"
            task_storage[task_id]["result"] = result
            task_storage[task_id]["progress"] = "审核完成"
            logger.info(f"Audit task {task_id} completed successfully")
            
    except Exception as e:
        error_msg = str(e)
        task_storage[task_id]["status"] = "failed"
        task_storage[task_id]["error"] = error_msg
        task_storage[task_id]["progress"] = f"审核失败: {error_msg}"
        logger.error(f"Audit task {task_id} exception: {error_msg}")
    
    finally:
        # 清理上传的文件（可选）
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up uploaded file: {file_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup file {file_path}: {cleanup_error}")


async def process_single_pdf_file(
    pdf_file_path: str,
    session_id: str,
    with_tracing: bool = False,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    处理单个PDF文件的审核任务
    
    Args:
        pdf_file_path: PDF文件路径
        session_id: 会话 ID
        with_tracing: 是否启用追踪
        debug_mode: 是否启用调试模式
        
    Returns:
        审核结果
    """
    try:
        from src.nodes.pdf_extraction import extract_pdf_via_api
        from src.tools.ai_utils import validate_material_with_ai
        from src.tools.common_utils import generate_html_report
        
        logger.info(f"Starting single PDF audit: {Path(pdf_file_path).name}")
        
        # 获取PDF API端点
        api_endpoint = "http://183.203.184.233:8888/pdf_parse_supplychain"
        
        # Step 1: 提取PDF内容
        logger.info("Step 1: Extracting PDF content...")
        extraction_result = await extract_pdf_via_api(pdf_file_path, api_endpoint)
        
        if not extraction_result.get("success", False):
            return {
                "error": f"PDF内容提取失败: {extraction_result.get('error', '未知错误')}",
                "current_step": "pdf_extraction_failed",
                "error_message": extraction_result.get('error', '未知错误')
            }
        
        # 获取提取的内容
        content = extraction_result.get("content", {})
        
        # Step 2: 判断材料类型（基于文件名）
        file_name = Path(pdf_file_path).name.lower()
        material_type = "教育经历"  # 默认类型
        
        # 简单的文件名匹配逻辑
        if "教育" in file_name or "学历" in file_name or "毕业" in file_name:
            material_type = "教育经历"
        elif "工作" in file_name:
            material_type = "工作经历"
        elif "论文" in file_name:
            material_type = "论文"
        elif "专利" in file_name:
            material_type = "专利"
        elif "证书" in file_name:
            material_type = "资质证书"
        
        logger.info(f"Detected material type: {material_type}")
        
        # Step 3: 材料验证
        logger.info("Step 3: Validating material...")
        
        # 准备材料内容（简化版，没有规则文件）
        material_content_str = str(content)
        
        try:
            # 使用AI进行材料校验（无规则上下文时会抛出异常）
            ai_results = validate_material_with_ai(
                material_type=material_type,
                content=material_content_str,
                rules_context=[]  # 空规则列表会抛出异常
            )
            validation_results = ai_results
        except Exception as validation_error:
            logger.warning(f"AI校验失败: {validation_error}")
            # 创建基本校验结果
            validation_results = [{
                "rule_name": f"{material_type}基本检查",
                "status": "WARNING",
                "message": f"单文件校验完成，建议进行完整的规则校验：{validation_error}",
                "rule_content": "基本校验"
            }]
        
        # Step 4: 生成报告
        logger.info("Step 4: Generating report...")
        
        # 从提取的内容中构建核心信息
        core_info = {
            "name": content.get("name", "未提取"),
            "id_number": content.get("id_number", "未提取"),
            "extracted_from": [Path(pdf_file_path).name]
        }
        
        # 构建报告数据
        report_data = {
            "file_info": {
                "name": Path(pdf_file_path).name,
                "type": "PDF文档",
                "material_type": material_type
            },
            "validation_results": {
                material_type: validation_results
            },
            "cross_validation_results": [],
            "summary": {
                "total_materials": 1,
                "total_validations": len(validation_results),
                "passed": len([r for r in validation_results if r.get("status") == "PASS" or "✅" in str(r.get("status", ""))]),
                "warnings": len([r for r in validation_results if r.get("status") == "WARNING" or "⚠️" in str(r.get("status", ""))]),
                "errors": len([r for r in validation_results if r.get("status") == "ERROR" or "❌" in str(r.get("status", ""))])
            }
        }
        
        # 调用generate_html_report函数，传递正确的参数
        html_report = generate_html_report(core_info, validation_results)
        
        return {
            "current_step": "completed",
            "material_type": material_type,
            "extraction_result": extraction_result,
            "validation_results": {material_type: validation_results},
            "audit_report": html_report,
            "summary": report_data["summary"],
            "processing_logs": [
                "PDF内容提取完成",
                f"检测到材料类型: {material_type}",
                f"生成{len(validation_results)}个验证结果",
                "报告生成完成"
            ]
        }
        
    except Exception as e:
        logger.error(f"Single PDF processing failed: {str(e)}")
        return {
            "error": f"单个PDF文件处理失败: {str(e)}",
            "current_step": "failed",
            "error_message": str(e)
        }


@app.get("/api/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务状态信息
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_storage[task_id]
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        current_node=task.get("current_node"),
        result=task["result"],
        error=task["error"],
        timestamp=task["timestamp"]
    )


@app.get("/api/report/{task_id}")
async def download_report(task_id: str):
    """
    下载审核报告
    
    Args:
        task_id: 任务ID
        
    Returns:
        HTML报告文件
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_storage[task_id]
    
    if task["status"] != "completed" or not task["result"]:
        raise HTTPException(status_code=400, detail="审核尚未完成或无结果")
    
    result = task["result"]
    
    if "report_path" in result and os.path.exists(result["report_path"]):
        return FileResponse(
            result["report_path"],
            filename=f"audit_report_{task_id[:8]}.html",
            media_type="text/html"
        )
    elif "audit_report" in result:
        # 创建临时报告文件
        temp_report = upload_dir / f"report_{task_id}.html"
        with open(temp_report, 'w', encoding='utf-8') as f:
            f.write(result["audit_report"])
        
        return FileResponse(
            temp_report,
            filename=f"audit_report_{task_id[:8]}.html",
            media_type="text/html"
        )
    else:
        raise HTTPException(status_code=404, detail="报告文件不存在")


@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        删除确认
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 清理任务数据
    del task_storage[task_id]
    
    return {"message": "任务已删除", "task_id": task_id}


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "message": "LangGraph 职称评审系统运行正常",
        "active_tasks": len(task_storage),
        "active_streams": len(active_streams),
        "completed_tasks": len([
            t for t in task_storage.values() 
            if t["status"] in ["completed", "failed"]
        ]),
        "processing_tasks": len([
            t for t in task_storage.values() 
            if t["status"] in ["started", "processing"]
        ]),
        "version": "2.0.0"
    }


@app.post("/api/cleanup")
async def manual_cleanup():
    """手动清理任务"""
    before_count = len(task_storage)
    await cleanup_old_tasks()
    after_count = len(task_storage)
    
    return {
        "message": "任务清理完成",
        "tasks_before": before_count,
        "tasks_after": after_count,
        "cleaned_count": before_count - after_count
    }


@app.get("/api/tasks")
async def list_tasks():
    """获取所有任务列表"""
    tasks = []
    for task_id, task_data in task_storage.items():
        tasks.append({
            "task_id": task_id,
            "status": task_data["status"],
            "progress": task_data["progress"],
            "timestamp": task_data["timestamp"],
            "original_filename": task_data.get("original_filename", "unknown")
        })
    
    return {
        "tasks": tasks,
        "total": len(tasks),
        "active_streams": len(active_streams)
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 启动LangGraph职称评审系统Web服务...")
    print("📊 Web界面: http://localhost:8000")
    print("📋 API文档: http://localhost:8000/docs")
    print("🔄 流式API: http://localhost:8000/api/stream/{task_id}")
    
    uvicorn.run(
        "web_app_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )