#!/bin/bash
# 停止新闻爬虫调度器（杀掉所有相关进程）

cd "$(dirname "$0")"

STOPPED=0

# 1. 如果有 PID 文件，先按 PID 文件杀
if [ -f logs/scheduler.pid ]; then
    PID=$(cat logs/scheduler.pid 2>/dev/null)
    if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
        echo "Stopping guard process (PID: $PID)..."
        kill -- -$PID 2>/dev/null || kill $PID 2>/dev/null
        sleep 1
        kill -9 -- -$PID 2>/dev/null || kill -9 $PID 2>/dev/null 2>/dev/null
        STOPPED=1
    fi
fi

# 2. 兜底：杀掉所有 main.py / _guard.sh / caffeinate 相关进程
ORPHANS=$(pgrep -f "news_agent/main.py" 2>/dev/null)
if [ -n "$ORPHANS" ]; then
    echo "Found orphan scheduler processes, stopping..."
    echo "$ORPHANS" | xargs kill 2>/dev/null
    sleep 1
    echo "$ORPHANS" | xargs kill -9 2>/dev/null
    STOPPED=1
fi

GUARD_ORPHANS=$(pgrep -f "_guard.sh" 2>/dev/null)
if [ -n "$GUARD_ORPHANS" ]; then
    echo "$GUARD_ORPHANS" | xargs kill 2>/dev/null
    sleep 1
    echo "$GUARD_ORPHANS" | xargs kill -9 2>/dev/null
    STOPPED=1
fi

# 3. 等待进程完全退出
for i in {1..10}; do
    REMAINING=$(pgrep -f "news_agent/main.py" 2>/dev/null)
    if [ -z "$REMAINING" ]; then
        break
    fi
    sleep 1
done

# 4. 清理
rm -f logs/scheduler.pid logs/_guard_*.sh

if [ $STOPPED -eq 1 ]; then
    echo "✅ Scheduler stopped."
else
    echo "No scheduler processes found."
fi
