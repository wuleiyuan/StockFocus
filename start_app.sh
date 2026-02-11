#!/bin/bash

echo "🚀 正在启动 StockFocus 投研系统..."

# 1. 检查并启动 Docker 数据库
if [ "$(docker ps -q -f name=stock_db)" ]; then
    echo "✅ 数据库容器已经在运行中。"
else
    echo "⚙️ 正在启动 Docker 数据库..."
    docker start stock_db || docker-compose up -d db
fi

# 2. 检查 Python 依赖（仅在第一次执行时可能较慢）
echo "📦 检查本地 Python 环境依赖..."
pip install -q streamlit akshare pandas psycopg2-binary plotly openpyxl requests

# 3. 启动 Streamlit 网站
echo "🌐 正在打开 Web 界面..."
streamlit run app_web.py