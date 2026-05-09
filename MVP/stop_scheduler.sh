#!/bin/bash
# 停止新闻爬虫调度器（杀掉整个守护进程组）

cd "$(dirname "$0")"

if [ ! -f logs/scheduler.pid ]; then
    echo "PID file not found. Is scheduler running?"
    exit 1
fi

PID=$(cat logs/scheduler.pid 2>/dev/null)

if [ -z "$PID" ]; then
    echo "PID file is empty."
    exit 1
fi

if ! kill -0 $PID 2>/dev/null; then
    echo "Process $PID is not running."
    rm -f logs/scheduler.pid
    exit 1
fi

echo "Stopping scheduler (PID: $PID)..."

# 杀掉整个进程组（setsid 创建的会话）
# 先尝试优雅关闭
kill -- -$PID 2>/dev/null || kill $PID 2>/dev/null

# 等待进程停止
for i in {1..10}; do
    if ! kill -0 $PID 2>/dev/null; then
        echo "✅ Scheduler stopped."
        rm -f logs/scheduler.pid logs/_guard_*.sh
        exit 0
    fi
    sleep 1
done

# 强制停止
echo "Force stopping scheduler..."
kill -9 -- -$PID 2>/dev/null || kill -9 $PID 2>/dev/null
rm -f logs/scheduler.pid logs/_guard_*.sh
echo "Scheduler force stopped."
