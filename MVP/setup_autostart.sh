#!/bin/bash
# 安装/卸载 macOS 开机自启服务

PLIST_NAME="com.newsscheduler.agent"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

case "$1" in
    install)
        if [ ! -f "$PLIST_SRC" ]; then
            echo "❌ 找不到 plist 文件: $PLIST_SRC"
            exit 1
        fi

        # 如果已安装，先卸载
        if [ -f "$PLIST_DEST" ]; then
            echo "检测到已安装，先卸载旧服务..."
            launchctl unload "$PLIST_DEST" 2>/dev/null
        fi

        # 复制 plist
        cp "$PLIST_SRC" "$PLIST_DEST"
        echo "已复制 plist 到 $PLIST_DEST"

        # 加载服务
        launchctl load "$PLIST_DEST"
        echo "✅ 开机自启服务已安装并启动"
        echo ""
        echo "管理命令："
        echo "  查看状态: launchctl list | grep newscheduler"
        echo "  停止服务: launchctl unload $PLIST_DEST"
        echo "  启动服务: launchctl load $PLIST_DEST"
        echo "  卸载服务: $0 uninstall"
        ;;

    uninstall)
        if [ -f "$PLIST_DEST" ]; then
            launchctl unload "$PLIST_DEST" 2>/dev/null
            rm -f "$PLIST_DEST"
            echo "✅ 开机自启服务已卸载"
        else
            echo "服务未安装"
        fi
        ;;

    status)
        RESULT=$(launchctl list | grep "$PLIST_NAME" 2>/dev/null)
        if [ -n "$RESULT" ]; then
            echo "✅ 服务已运行:"
            echo "$RESULT"
        else
            echo "❌ 服务未运行"
        fi
        ;;

    *)
        echo "用法: $0 {install|uninstall|status}"
        echo ""
        echo "  install   - 安装开机自启服务"
        echo "  uninstall - 卸载开机自启服务"
        echo "  status    - 查看服务状态"
        exit 1
        ;;
esac
