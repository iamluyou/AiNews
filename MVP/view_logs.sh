#!/bin/bash
# 查看调度器日志

cd "$(dirname "$0")"

LOG_FILE="logs/scheduler.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    exit 1
fi

# 查看最后 100 行，跟随输出
tail -100f "$LOG_FILE"
