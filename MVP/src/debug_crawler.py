#!/usr/bin/env python3
"""
调试爬虫：查看网页实际结构
"""
import sys
from pathlib import Path

src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import requests
from bs4 import BeautifulSoup


def fetch_and_debug(url, name):
    """获取网页并打印结构"""
    print(f"\n{'='*60}")
    print(f"正在调试: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")

            # 打印标题
            print(f"\n网页标题: {soup.title.string if soup.title else 'None'}")

            # 查找所有链接
            print("\n--- 前 20 个链接 ---")
            links = soup.find_all("a", href=True)
            for i, a in enumerate(links[:20]):
                text = a.get_text(strip=True)[:50]
                href = a.get("href")
                if text:
                    print(f"{i+1:2d}. {text:50} -> {href}")

            # 查找所有文章相关的标签
            print("\n--- 查找文章相关标签 ---")
            article_tags = ["article", "div", "section", "li"]
            for tag in article_tags:
                elements = soup.find_all(tag, class_=lambda x: x and any(k in str(x).lower() for k in ["article", "news", "item", "post", "card"]))
                if elements:
                    print(f"\n找到 {len(elements)} 个 <{tag}> 包含相关 class:")
                    for i, elem in enumerate(elements[:3]):
                        print(f"\n--- {tag} {i+1} ---")
                        print(elem.get("class"))
                        print(str(elem)[:300])

            # 保存 HTML 到文件
            html_file = Path(__file__).parent / f"debug_{name}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"\nHTML 已保存到: {html_file}")

    except Exception as e:
        print(f"错误: {e}")


def main():
    """主函数"""
    sites = [
        ("机器之心", "https://www.jiqizhixin.com/"),
        ("36氪", "https://www.36kr.com/information/AI/"),
        ("Aiera", "https://aiera.com.cn/"),
        ("RadarAI", "https://radarai.top/"),
        ("QbitAI", "https://www.qbitai.com/"),
    ]

    for name, url in sites:
        fetch_and_debug(url, name)
        input("\n按回车继续下一个...")


if __name__ == "__main__":
    main()
