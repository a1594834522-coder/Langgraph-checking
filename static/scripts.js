/**
 * LangGraph 职称评审系统 - 前端JavaScript
 * 支持实时流式更新、文件上传、进度追踪等功能
 */

class AuditApp {
    constructor() {
        this.currentTask = null;
        this.eventSource = null;
        this.isConnected = false;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadTasks();
        this.showWelcomeScreen();
        this.createConnectionStatus();
    }

    /**
     * 绑定事件监听器
     */
    bindEvents() {
        // 文件上传表单
        document.getElementById('uploadForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFileUpload();
        });

        // 任务列表刷新
        document.getElementById('refreshTasks').addEventListener('click', () => {
            this.loadTasks();
        });

        // 操作按钮
        document.getElementById('downloadReport').addEventListener('click', () => {
            this.downloadReport();
        });

        document.getElementById('viewDetails').addEventListener('click', () => {
            this.viewTaskDetails();
        });

        document.getElementById('cancelTask').addEventListener('click', () => {
            this.cancelTask();
        });

        document.getElementById('newTask').addEventListener('click', () => {
            this.showWelcomeScreen();
        });

        document.getElementById('clearLogs').addEventListener('click', () => {
            this.clearLogs();
        });

        // 文件输入变化
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.validateFileInput(e.target);
        });
    }

    /**
     * 创建连接状态指示器
     */
    createConnectionStatus() {
        const statusDiv = document.createElement('div');
        statusDiv.id = 'connectionStatus';
        statusDiv.className = 'connection-status disconnected';
        statusDiv.innerHTML = '<i class="bi bi-wifi-off me-1"></i>未连接';
        document.body.appendChild(statusDiv);
    }

    /**
     * 更新连接状态
     */
    updateConnectionStatus(status) {
        const statusDiv = document.getElementById('connectionStatus');
        if (!statusDiv) {
            console.warn('Connection status element not found');
            return;
        }
        
        const statusMap = {
            'connected': {
                class: 'connected',
                icon: 'bi-wifi',
                text: '已连接'
            },
            'connecting': {
                class: 'connecting',
                icon: 'bi-arrow-repeat',
                text: '连接中...'
            },
            'disconnected': {
                class: 'disconnected',
                icon: 'bi-wifi-off',
                text: '未连接'
            }
        };
        
        const config = statusMap[status] || statusMap['disconnected'];
        statusDiv.className = `connection-status ${config.class}`;
        statusDiv.innerHTML = `<i class="bi ${config.icon} me-1"></i>${config.text}`;
        
        this.isConnected = status === 'connected';
    }

    /**
     * 显示欢迎界面
     */
    showWelcomeScreen() {
        document.getElementById('welcomeScreen').classList.remove('d-none');
        document.getElementById('auditScreen').classList.add('d-none');
        
        // 重置表单
        document.getElementById('uploadForm').reset();
        
        // 关闭事件源
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        this.currentTask = null;
        this.updateConnectionStatus('disconnected');
    }

    /**
     * 显示审核界面
     */
    showAuditScreen() {
        document.getElementById('welcomeScreen').classList.add('d-none');
        document.getElementById('auditScreen').classList.remove('d-none');
    }

    /**
     * 处理文件上传
     */
    async handleFileUpload() {
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        
        if (!fileInput.files.length) {
            this.showError('请选择一个ZIP文件');
            return;
        }

        const file = fileInput.files[0];
        if (!file.name.toLowerCase().endsWith('.zip') && !file.name.toLowerCase().endsWith('.pdf')) {
            this.showError('支持ZIP文件（完整材料包）或PDF文件（单个文档）格式');
            return;
        }

        // 显示上传状态
        uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>上传中...';
        uploadBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('file', file);
            
            // 获取表单数据
            const sessionId = document.getElementById('sessionId').value.trim();
            const withTracing = document.getElementById('withTracing').checked;
            const debugMode = document.getElementById('debugMode').checked;
            const streamMode = document.getElementById('streamMode').value;

            if (sessionId) formData.append('session_id', sessionId);
            formData.append('with_tracing', withTracing);
            formData.append('debug_mode', debugMode);
            formData.append('stream_mode', streamMode);

            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || '上传失败');
            }

            // 保存当前任务信息
            this.currentTask = {
                taskId: result.task_id,
                fileName: file.name,
                fileSize: file.size,
                sessionId: sessionId || result.task_id.substring(0, 8),
                withTracing,
                debugMode,
                streamMode,
                startTime: new Date().toLocaleString(),
                streamUrl: result.stream_url
            };

            // 切换到审核界面
            this.showAuditScreen();
            this.updateTaskInfo();
            this.initWorkflowSteps();
            this.startStreaming();
            this.loadTasks(); // 刷新任务列表

        } catch (error) {
            console.error('Upload error:', error);
            this.showError(error.message);
        } finally {
            uploadBtn.innerHTML = '<i class="bi bi-upload me-2"></i>开始审核';
            uploadBtn.disabled = false;
        }
    }

    /**
     * 验证文件输入
     */
    validateFileInput(input) {
        const file = input.files[0];
        if (!file) return;

        const maxSize = 100 * 1024 * 1024; // 100MB
        if (file.size > maxSize) {
            this.showError('文件大小不能超过100MB');
            input.value = '';
            return;
        }

        if (!file.name.toLowerCase().endsWith('.zip') && !file.name.toLowerCase().endsWith('.pdf')) {
            this.showError('支持ZIP文件（完整材料包）或PDF文件（单个文档）格式');
            input.value = '';
            return;
        }
    }

    /**
     * 更新任务信息显示
     */
    updateTaskInfo() {
        if (!this.currentTask) return;

        const elements = {
            'currentTaskId': this.currentTask.taskId,
            'currentFileName': this.currentTask.fileName,
            'currentFileSize': this.formatFileSize(this.currentTask.fileSize),
            'currentSessionId': this.currentTask.sessionId,
            'currentStartTime': this.currentTask.startTime
        };
        
        // 安全地更新每个元素
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            } else {
                console.warn(`Element with id '${id}' not found`);
            }
        });
        
        this.updateStatus('started', '已开始');
    }

    /**
     * 初始化工作流步骤
     */
    initWorkflowSteps() {
        const steps = [
            { id: 'file_processing', name: '文件处理', description: '解压和分类文件', icon: 'bi-file-zip' },
            { id: 'pdf_analysis', name: 'PDF分析', description: '分析PDF文档结构', icon: 'bi-file-pdf' },
            { id: 'content_extraction', name: '内容提取', description: '提取关键信息', icon: 'bi-search' },
            { id: 'validation', name: '规则校验', description: '验证材料完整性', icon: 'bi-check-circle' },
            { id: 'cross_validation', name: '交叉校验', description: '核验信息一致性', icon: 'bi-arrows-angle-contract' },
            { id: 'report_generation', name: '报告生成', description: '生成审核报告', icon: 'bi-file-text' }
        ];

        const container = document.getElementById('workflowSteps');
        if (!container) {
            console.warn('Workflow steps container not found');
            return;
        }
        
        container.innerHTML = '';

        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = 'workflow-step';
            stepElement.id = `step-${step.id}`;
            stepElement.innerHTML = `
                <div class="workflow-step-icon">
                    <i class="${step.icon}"></i>
                </div>
                <div class="workflow-step-content">
                    <h6>${step.name}</h6>
                    <p>${step.description}</p>
                </div>
            `;
            container.appendChild(stepElement);
        });
    }

    /**
     * 检查任务是否存在
     */
    async checkTaskExists() {
        if (!this.currentTask) return false;
        
        try {
            const response = await fetch(`/api/status/${this.currentTask.taskId}`);
            return response.ok; // 200表示任务存在，404表示不存在
        } catch (error) {
            console.error('Error checking task:', error);
            return false;
        }
    }

    /**
     * 开始流式连接
     */
    startStreaming() {
        if (!this.currentTask) return;

        this.updateConnectionStatus('connecting');
        this.addLogEntry('started', '正在建立流式连接...');

        const streamUrl = `/api/stream/${this.currentTask.taskId}`;
        this.eventSource = new EventSource(streamUrl);

        this.eventSource.onopen = () => {
            this.updateConnectionStatus('connected');
            this.addLogEntry('started', '流式连接已建立');
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleStreamEvent(data);
            } catch (error) {
                console.error('Stream event parse error:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('Stream error:', error);
            this.updateConnectionStatus('disconnected');
            
            // 检查是否是404错误（任务不存在）
            if (this.eventSource.readyState === EventSource.CLOSED) {
                // 获取任务状态以确认是否为404
                this.checkTaskExists()
                    .then(exists => {
                        if (!exists) {
                            this.addLogEntry('error', '任务不存在或已被清理，请开始新的任务');
                            this.showError('任务不存在或已被清理，请开始新的任务');
                            this.updateStatus('failed', '任务不存在');
                            return;
                        } else {
                            this.addLogEntry('error', '流式连接出现错误，尝试重连...');
                            
                            // 重连逻辑
                            setTimeout(() => {
                                if (this.currentTask && this.eventSource.readyState === EventSource.CLOSED) {
                                    this.startStreaming();
                                }
                            }, 5000);
                        }
                    })
                    .catch(err => {
                        console.error('Error checking task status:', err);
                        this.addLogEntry('error', '流式连接出现错误');
                    });
            }
        };

        this.eventSource.onclose = () => {
            this.updateConnectionStatus('disconnected');
            this.addLogEntry('completed', '流式连接已关闭');
        };
    }

    /**
     * 处理流式事件
     */
    handleStreamEvent(event) {
        const { event_type, data, node_name, timestamp } = event;

        switch (event_type) {
            case 'started':
                this.updateStatus('processing', '处理中');
                this.addLogEntry('started', data.message);
                break;

            case 'progress':
                this.updateProgress(data.percent, data.description);
                this.addLogEntry('progress', `${data.description} (${data.percent}%)`);
                break;

            case 'node_update':
                this.updateWorkflowStep(data.node_name, data.status);
                this.addLogEntry('progress', `${data.node_name}: ${data.message}`);
                break;

            case 'completed':
                this.updateStatus('completed', '已完成');
                this.updateProgress(100, '审核完成');
                this.addLogEntry('completed', data.message);
                this.enableDownloadButton(data.report_available);
                break;

            case 'error':
                this.updateStatus('failed', '失败');
                this.addLogEntry('error', data.message);
                this.showError(data.message);
                break;

            case 'log':
                this.addLogEntry('log', data.message);
                break;

            default:
                console.log('Unknown event type:', event_type, data);
        }
    }

    /**
     * 更新进度条
     */
    updateProgress(percent, description) {
        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const progressDescription = document.getElementById('progressDescription');

        if (progressBar) {
            progressBar.style.width = `${percent}%`;
            progressBar.setAttribute('aria-valuenow', percent);
        }
        
        if (progressPercent) {
            progressPercent.textContent = `${percent}%`;
        }
        
        if (progressDescription) {
            progressDescription.textContent = description;
        }

        if (percent === 100 && progressBar) {
            progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
            progressBar.classList.add('bg-success');
        }
    }

    /**
     * 更新状态显示
     */
    updateStatus(status, text) {
        const statusElement = document.getElementById('currentStatus');
        if (!statusElement) {
            console.warn('Status element not found');
            return;
        }
        
        const statusClasses = {
            'started': 'bg-primary',
            'processing': 'bg-warning',
            'completed': 'bg-success',
            'failed': 'bg-danger'
        };

        statusElement.className = `badge ${statusClasses[status] || 'bg-secondary'}`;
        statusElement.textContent = text;
    }

    /**
     * 更新工作流步骤状态
     */
    updateWorkflowStep(stepId, status) {
        const stepElement = document.getElementById(`step-${stepId}`);
        if (!stepElement) return;

        // 移除之前的状态类
        stepElement.classList.remove('active', 'completed', 'error');
        
        // 添加新状态类
        if (status === 'processing') {
            stepElement.classList.add('active');
            
            // 移除之前步骤的active状态
            const allSteps = document.querySelectorAll('.workflow-step');
            allSteps.forEach(step => {
                if (step !== stepElement) {
                    step.classList.remove('active');
                    if (!step.classList.contains('completed')) {
                        // 如果不是已完成状态，则设为完成
                        const stepIndex = Array.from(step.parentNode.children).indexOf(step);
                        const currentIndex = Array.from(stepElement.parentNode.children).indexOf(stepElement);
                        if (stepIndex < currentIndex) {
                            step.classList.add('completed');
                        }
                    }
                }
            });
        } else if (status === 'completed') {
            stepElement.classList.add('completed');
        } else if (status === 'error') {
            stepElement.classList.add('error');
        }
    }

    /**
     * 添加日志条目
     */
    addLogEntry(type, message) {
        const logContainer = document.getElementById('logContainer');
        if (!logContainer) {
            console.warn('Log container not found');
            return;
        }
        
        const timestamp = new Date().toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-message">${this.escapeHtml(message)}</span>
        `;
        
        logContainer.appendChild(logEntry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    /**
     * 清空日志
     */
    clearLogs() {
        const logContainer = document.getElementById('logContainer');
        if (logContainer) {
            logContainer.innerHTML = '';
        }
    }

    /**
     * 启用下载按钮
     */
    enableDownloadButton(available) {
        const downloadBtn = document.getElementById('downloadReport');
        const viewDetailsBtn = document.getElementById('viewDetails');
        
        if (downloadBtn) {
            downloadBtn.disabled = !available;
            if (available) {
                downloadBtn.classList.remove('btn-outline-success');
                downloadBtn.classList.add('btn-success');
            }
        }
        
        if (viewDetailsBtn) {
            viewDetailsBtn.disabled = false;
        }
    }

    /**
     * 下载报告
     */
    async downloadReport() {
        if (!this.currentTask) return;

        try {
            const response = await fetch(`/api/report/${this.currentTask.taskId}`);
            
            if (!response.ok) {
                throw new Error('报告下载失败');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `audit_report_${this.currentTask.taskId.substring(0, 8)}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.addLogEntry('completed', '报告下载完成');

        } catch (error) {
            console.error('Download error:', error);
            this.showError(error.message);
        }
    }

    /**
     * 查看任务详情
     */
    async viewTaskDetails() {
        if (!this.currentTask) return;

        try {
            const response = await fetch(`/api/status/${this.currentTask.taskId}`);
            const details = await response.json();

            if (!response.ok) {
                throw new Error(details.detail || '获取详情失败');
            }

            const taskDetailsElement = document.getElementById('taskDetails');
            const detailsModal = document.getElementById('detailsModal');
            
            if (taskDetailsElement) {
                taskDetailsElement.textContent = JSON.stringify(details, null, 2);
            }
            
            if (detailsModal && typeof bootstrap !== 'undefined') {
                const modal = new bootstrap.Modal(detailsModal);
                modal.show();
            }

        } catch (error) {
            console.error('Details error:', error);
            this.showError(error.message);
        }
    }

    /**
     * 取消任务
     */
    async cancelTask() {
        if (!this.currentTask) return;

        if (!confirm('确定要取消当前任务吗？')) return;

        try {
            const response = await fetch(`/api/task/${this.currentTask.taskId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.addLogEntry('error', '任务已取消');
                if (this.eventSource) {
                    this.eventSource.close();
                }
                this.loadTasks();
            }

        } catch (error) {
            console.error('Cancel error:', error);
            this.showError('取消任务失败');
        }
    }

    /**
     * 加载任务列表
     */
    async loadTasks() {
        try {
            const response = await fetch('/api/tasks');
            const data = await response.json();

            if (!response.ok) {
                throw new Error('加载任务列表失败');
            }

            this.renderTaskList(data.tasks);

        } catch (error) {
            console.error('Load tasks error:', error);
        }
    }

    /**
     * 渲染任务列表
     */
    renderTaskList(tasks) {
        const container = document.getElementById('taskList');
        if (!container) {
            console.warn('Task list container not found');
            return;
        }
        
        if (!tasks.length) {
            container.innerHTML = `
                <div class="text-center p-4 text-muted">
                    <i class="bi bi-inbox display-4"></i>
                    <p class="mt-2">暂无任务</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        
        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.className = 'task-item';
            taskElement.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="fw-bold text-truncate">${this.escapeHtml(task.original_filename)}</div>
                        <div class="small text-muted">${task.task_id.substring(0, 8)}</div>
                        <div class="small text-muted">${new Date(task.timestamp).toLocaleString()}</div>
                    </div>
                    <div class="text-end">
                        <span class="task-status ${task.status}">${this.getStatusText(task.status)}</span>
                    </div>
                </div>
            `;
            
            taskElement.addEventListener('click', () => {
                this.selectTask(task);
            });
            
            container.appendChild(taskElement);
        });
    }

    /**
     * 选择任务
     */
    selectTask(task) {
        // 实现任务选择逻辑
        console.log('Selected task:', task);
    }

    /**
     * 获取状态文本
     */
    getStatusText(status) {
        const statusMap = {
            'started': '已开始',
            'processing': '处理中',
            'completed': '已完成',
            'failed': '失败'
        };
        return statusMap[status] || status;
    }

    /**
     * 显示错误信息
     */
    showError(message) {
        const errorMessageElement = document.getElementById('errorMessage');
        const errorModalElement = document.getElementById('errorModal');
        
        if (errorMessageElement) {
            errorMessageElement.textContent = message;
        }
        
        if (errorModalElement && typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(errorModalElement);
            modal.show();
        } else {
            // 如果模态框不可用，使用原生警告
            alert('错误: ' + message);
        }
    }

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * HTML转义
     */
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    new AuditApp();
});

// 全局错误处理
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});

// 网络状态监听
window.addEventListener('online', () => {
    console.log('Network online');
});

window.addEventListener('offline', () => {
    console.log('Network offline');
});