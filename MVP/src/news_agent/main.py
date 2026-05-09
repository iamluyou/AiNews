#!/usr/bin/env python3
"""
新闻爬虫与 AI 整理系统
"""
import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from news_agent.scheduler import main

if __name__ == "__main__":
    main()
