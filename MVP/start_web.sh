#!/bin/bash
# 启动 News Agent Web 管理界面

cd "$(dirname "$0")"

echo "=========================================="
echo "News Agent Web 管理界面"
echo "=========================================="

# 检查虚拟环境
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
fi

# 检查 Flask 是否安装
if ! python3 -c "import flask" 2>/dev/null; then
    echo "安装 Flask 依赖..."
    pip install flask
fi

# 启动 Flask 应用
echo "启动 Web 服务器..."
echo "访问地址: http://localhost:5547"
echo "按 Ctrl+C 停止服务器"
echo ""

PYTHONPATH=src python3 src/news_agent/web/app.py
