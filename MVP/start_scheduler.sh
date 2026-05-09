#!/bin/bash
# 启动新闻爬虫调度器（带自动重启守护 + 防休眠 + 脱离终端）

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
    rm -f logs/scheduler.pid
fi

# 创建守护脚本（脱离终端运行）
GUARD_SCRIPT=$(cat <<'EOF'
#!/bin/bash
cd "$1"

MAX_RESTARTS=5
RESTART_INTERVAL=60
restart_count=0
last_restart_time=0

run_scheduler() {
    if command -v caffeinate &>/dev/null; then
        PYTHONPATH=src caffeinate -s python3 src/news_agent/main.py >> logs/scheduler.log 2>&1
    else
        PYTHONPATH=src python3 src/news_agent/main.py >> logs/scheduler.log 2>&1
    fi
    return $?
}

while true; do
    run_scheduler
    exit_code=$?

    current_time=$(date +%s)
    time_since_last=$((current_time - last_restart_time))

    if [ $time_since_last -gt $RESTART_INTERVAL ]; then
        restart_count=0
    fi

    restart_count=$((restart_count + 1))
    last_restart_time=$current_time

    if [ $restart_count -ge $MAX_RESTARTS ]; then
        echo "$(date): Scheduler crashed $MAX_RESTARTS times in a row. Stopping." >> logs/scheduler.log
        rm -f logs/scheduler.pid
        exit 1
    fi

    echo "$(date): Scheduler exited (code $exit_code). Restarting ($restart_count/$MAX_RESTARTS) in 5s..." >> logs/scheduler.log
    sleep 5
done
EOF
)

# 写入守护脚本
GUARD_FILE="logs/_guard.sh"
echo "$GUARD_SCRIPT" > "$GUARD_FILE"
chmod +x "$GUARD_FILE"

# macOS 没有 setsid，用 nohup + 后台 + disown 脱离终端
nohup bash "$GUARD_FILE" "$(pwd)" >> logs/scheduler.log 2>&1 &
GUARD_PID=$!
disown $GUARD_PID

# 记录 PID
echo $GUARD_PID > logs/scheduler.pid

# 等待确认启动
sleep 2

if kill -0 $GUARD_PID 2>/dev/null; then
    echo "✅ Scheduler started (Guard PID: $GUARD_PID)"
    echo "   Close terminal safely - process will continue running."
    echo "   Logs: logs/scheduler.log"
else
    echo "❌ Scheduler failed to start. Check logs/scheduler.log"
    rm -f logs/scheduler.pid
fi
