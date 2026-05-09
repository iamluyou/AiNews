#!/bin/bash
# 启动新闻爬虫调度器

cd "$(dirname "$0")"

# 创建 logs 目录
mkdir -p logs

# 检查是否已经在运行
if [ -f logs/scheduler.pid ]; then
    PID=$(cat logs/scheduler.pid 2>/dev/null)
    if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
        echo "Scheduler is already running (PID: $PID)"
        exit 1
    fi
fi

echo "Starting news scheduler..."
nohup python3 src/news_agent/main.py > logs/scheduler.log 2>&1 &
echo $! > logs/scheduler.pid
echo "Scheduler started (PID: $(cat logs/scheduler.pid))"
echo "Log file: logs/scheduler.log"
