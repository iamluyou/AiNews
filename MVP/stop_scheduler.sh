#!/bin/bash
# 停止新闻爬虫调度器

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
kill $PID

# 等待进程停止
for i in {1..10}; do
    if ! kill -0 $PID 2>/dev/null; then
        echo "Scheduler stopped."
        rm -f logs/scheduler.pid
        exit 0
    fi
    sleep 1
done

# 强制停止
echo "Force stopping scheduler..."
kill -9 $PID
rm -f logs/scheduler.pid
echo "Scheduler force stopped."
