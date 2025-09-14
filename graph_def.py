#!/usr/bin/env python3
"""
LangGraph 工作流图定义

专门用于 LangGraph Studio 的图定义文件
避免复杂的导入路径问题
"""

import sys
import os

# 确保项目路径在sys.path中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # 导入工作流创建函数
    from src.graph.workflow import create_audit_workflow
    
    # 创建图对象
    graph = create_audit_workflow()
    
    print("✅ LangGraph 工作流图已成功创建")
    
except Exception as e:
    print(f"❌ 创建图失败: {e}")
    import traceback
    traceback.print_exc()
    raise