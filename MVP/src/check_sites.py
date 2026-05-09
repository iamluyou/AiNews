#!/usr/bin/env python3
"""
快速检查网站结构
"""
import requests
from bs4 import BeautifulSoup
import json

sites = [
    ("jqzx", "https://www.jiqizhixin.com/"),
    ("kr36", "https://www.36kr.com/information/AI/"),
    ("aiera", "https://aiera.com.cn/"),
    ("radar", "https://radarai.top/"),
    ("qbit", "https://www.qbitai.com/"),
]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

for name, url in sites:
    print(f"\n{'='*60}")
    print(f"Checking: {name} - {url}")
    print(f"{'='*60}")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")

            # 找所有链接
            links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if text and len(text) > 5 and ("http" in href or href.startswith("/")):
                    links.append({"text": text[:60], "href": href})

            print(f"\nFound {len(links)} potential links")
            print("\nFirst 10 links:")
            for i, link in enumerate(links[:10]):
                print(f"  {i+1:2d}. {link['text']:60} -> {link['href']}")

            # 保存HTML
            with open(f"debug_{name}.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"\nSaved HTML to debug_{name}.html")

    except Exception as e:
        print(f"Error: {e}")
