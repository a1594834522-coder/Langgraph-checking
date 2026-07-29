# Enterprise-Grade Professional Title Review Materials Audit System

An intelligent professional title review materials audit system built on the LangGraph framework, utilizing AI technology to automate the processing and verification of professional title application materials.

🔧 **Integrated LangSmith Debugging and Monitoring** - Provides complete workflow tracing, performance monitoring, and debugging support.

## System Architecture

The system employs a LangGraph graphical workflow design, consisting of the following main modules:

1. **File Processing Module** - ZIP extraction, file classification
2. **Intelligent PDF Processing** - Page count detection, intelligent chunking
3. **Content Extraction** - AI recognition, classification into 17 types of materials
4. **Rule Verification** - Rule validation for various types of materials
5. **Cross-Verification** - Consistency checks for core information
6. **Report Generation** - HTML formatted output

## Installation Instructions
1. Create a virtual environment: `python -m venv venv`

Activate: `.venv/Scripts/activate`

2. Install dependencies: `pip install .`

`pip install requirements.txt`

3. Open development tools: `langgraph dev`

4. Start the web application: `python web_app_v2.py`
