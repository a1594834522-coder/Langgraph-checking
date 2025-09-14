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
1.创建虚拟环境 python -m venv venv 

启用   .venv/Scripts/activate    

2.安装依赖 pip install .

pip install requirements.txt

3.打开开发工具 langgraph dev

4.启动网页端 python web_app_v2.py

