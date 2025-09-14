# 企业级职称评审材料审核系统

基于LangGraph框架构建的智能化职称评审材料审核系统，通过AI技术自动化处理和校验职称申报材料。

🔧 **集成LangSmith调试和监控功能** - 提供完整的工作流追踪、性能监控和调试支持。

## 系统架构

系统采用LangGraph图形化工作流设计，包含以下主要模块：

1. **文件处理模块** - ZIP解压、文件分类
2. **PDF智能处理** - 页数检测、智能分片
3. **内容提取** - AI识别、17类材料分类
4. **规则校验** - 各类材料规则验证
5. **交叉校验** - 核心信息一致性检查
6. **报告生成** - HTML格式化输出

## 安装说明

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置API密钥等配置

# 配置LangSmith（可选，用于调试）
# 在.env文件中添加：
# LANGSMITH_API_KEY=your_api_key
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT=Audit_Workflow_Debug
```

## 使用方法

### 基础使用

```python
from src.agent import run_audit

# 运行审核
result = run_audit("path/to/materials.zip")
print(result["audit_report"])
```

### 带LangSmith追踪的调试模式

```python
from src.agent import run_audit_with_tracing, debug_audit

# 带追踪的审核
result = run_audit_with_tracing(
    uploaded_file="path/to/materials.zip",
    run_name="职称材料审核",
    tags=["audit", "production"]
)

# 调试模式
debug_result = debug_audit(
    uploaded_file="path/to/materials.zip",
    breakpoints=["file_processing", "validation"]
)
```

### 命令行调试工具

```bash
# 运行完整测试
python debug_langsmith.py test

# 检查LangSmith配置
python debug_langsmith.py check

# 交互式调试
python debug_langsmith.py interactive
```

## 目录结构

```
d:\Langgraph\
├── src/                    # 主要源代码
│   ├── graph/             # LangGraph工作流定义
│   ├── nodes/             # 各个处理节点
│   ├── tools/             # 工具函数（包含langsmith_utils.py）
│   ├── models/            # 数据模型
│   └── agent.py           # 主入口文件
├── debug_langsmith.py      # LangSmith调试工具
├── LANGSMITH_GUIDE.md      # LangSmith配置指南
├── tests/                 # 测试代码
├── docs/                  # 文档
├── data/                  # 数据存储
└── requirements.txt       # 依赖管理
```

## 开发说明

详细的开发文档请参考：
- 📚 [LangSmith集成指南](./LANGSMITH_GUIDE.md)
- 📝 [API文档](./docs/)
- 🔧 [LangGraph最佳实践](https://langchain-ai.github.io/langgraph/)

### 📈 LangSmith特性

- **自动追踪**: 记录工作流执行过程和性能指标
- **错误处理**: 结构化的重试策略和错误分类
- **调试工具**: 断点支持和流式调试
- **监控分析**: 实时监控和性能分析

## 许可证

MIT License