#!/bin/bash
# 启动新闻爬虫调度器（带自动重启守护 + 防休眠）

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

# 最大连续崩溃重启次数
MAX_RESTARTS=5
RESTART_INTERVAL=60  # 连续重启间隔（秒），超过此间隔重置计数
restart_count=0
last_restart_time=0

echo "Starting news scheduler (with auto-restart & sleep prevention)..."
echo $$ > logs/scheduler.pid

run_scheduler() {
    # caffeinate -s: 防止系统休眠（仅阻止空闲休眠，合盖仍会休眠）
    # 如果系统支持 caffeinate（macOS），则使用
    if command -v caffeinate &>/dev/null; then
        PYTHONPATH=src caffeinate -s python3 src/news_agent/main.py >> logs/scheduler.log 2>&1
    else
        PYTHONPATH=src python3 src/news_agent/main.py >> logs/scheduler.log 2>&1
    fi
    return $?
}

# 带守护的启动
while true; do
    run_scheduler
    exit_code=$?

    current_time=$(date +%s)
    time_since_last=$((current_time - last_restart_time))

    # 如果距上次重启超过 RESTART_INTERVAL 秒，说明运行了一段时间才崩溃，重置计数
    if [ $time_since_last -gt $RESTART_INTERVAL ]; then
        restart_count=0
    fi

    restart_count=$((restart_count + 1))
    last_restart_time=$current_time

    if [ $restart_count -ge $MAX_RESTARTS ]; then
        echo "❌ Scheduler crashed $MAX_RESTARTS times in a row. Stopping auto-restart."
        echo "Check logs/scheduler.log for details."
        rm -f logs/scheduler.pid
        exit 1
    fi

    echo "⚠️ Scheduler exited with code $exit_code. Restarting ($restart_count/$MAX_RESTARTS) in 5s..."
    sleep 5
done
