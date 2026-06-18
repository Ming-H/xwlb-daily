# -*- coding: utf-8 -*-
"""
央视新闻联播文字稿爬虫
从 tv.cctv.com/lm/xwlb/ 抓取每日新闻文字稿
"""
import re
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}
DATA_DIR = Path(__file__).parent.parent / "data" / "daily"


def fetch(url: str, timeout: int = 20, retries: int = 3):
    """HTTP GET 请求，带重试与超时；全部失败时返回 None（不抛异常）。"""
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 指数退避：1s, 2s
    print(f'  ⚠️ 网络请求失败（{retries} 次重试后）: {type(last).__name__}: {str(last)[:80]}')
    return None


def fetch_daily_list(date_str: str) -> list[dict]:
    """
    抓取某天的新闻列表
    date_str: YYYYMMDD 格式
    返回: [{url, title}, ...]
    """
    url = f'https://tv.cctv.com/lm/xwlb/day/{date_str}.shtml'
    html = fetch(url)
    if not html:
        return []

    # 先提取所有文章链接，去重
    articles = []
    seen_urls = set()
    for m in re.finditer(
        r'<li>\s*.*?href="(https://tv\.cctv\.com/\d{4}/\d{2}/\d{2}/VIDE\w+\.shtml)"',
        html, re.DOTALL
    ):
        link = m.group(1)
        if link not in seen_urls:
            seen_urls.add(link)
            articles.append({'url': link})

    # 为每个链接找对应的标题（从 alt 或 title 属性）
    for art in articles:
        escaped = re.escape(art['url'])
        title_match = re.search(
            escaped + r'[^>]*?(?:alt|title)="([^"]*)"',
            html
        )
        if title_match:
            art['title'] = title_match.group(1).strip()
        else:
            art['title'] = art['url'].split('/')[-1]

    return articles


def fetch_article_detail(url: str) -> dict:
    """抓取单条新闻的详情"""
    html = fetch(url)
    if not html:
        return {'title': '', 'text': '', 'guid': '', 'duration': ''}

    # 提取 content_area 文字
    content_match = re.search(
        r'id="content_area">(.*?)</div>\s*<div class="zebian"',
        html, re.DOTALL
    )
    if content_match:
        text = re.sub(r'<[^>]+>', '', content_match.group(1)).strip()
        text = re.sub(r'\s+', ' ', text)
        # 清理 HTML 实体
        for old, new in [('&ldquo;', '"'), ('&rdquo;', '"'), ('&hellip;', '…'),
                         ('&mdash;', '—'), ('&middot;', '·'), ('&nbsp;', ' '),
                         ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>')]:
            text = text.replace(old, new)
    else:
        text = ''

    # 提取 h1 标题
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ''

    # 提取 video GUID
    guid_match = re.search(r'var guid = "([^"]+)"', html)
    guid = guid_match.group(1) if guid_match else ''

    # 提取时长
    duration_match = re.search(r'<span>(\d+:\d+:\d+)</span>', html)
    duration = duration_match.group(1) if duration_match else ''

    return {
        'title': title,
        'text': text,
        'guid': guid,
        'duration': duration,
    }


def fetch_daily(date_str: str) -> dict:
    """
    抓取某天完整的新闻联播数据
    date_str: YYYYMMDD 格式
    """
    print(f'📅 抓取日期: {date_str}')

    # 获取列表
    articles = fetch_daily_list(date_str)
    if not articles:
        print(f'  ⚠️ 未找到新闻，可能当天无数据')
        return {'date': date_str, 'articles': []}

    print(f'📰 找到 {len(articles)} 条新闻')

    # 逐条抓取详情
    results = []
    for i, art in enumerate(articles, 1):
        try:
            detail = fetch_article_detail(art['url'])
            text = detail.get('text', '')
            results.append({
                'index': i,
                'title': detail.get('title', '') or art.get('title', ''),
                'url': art['url'],
                'guid': detail.get('guid', ''),
                'duration': detail.get('duration', ''),
                'text': text,
                'text_len': len(text),
            })
            status = f'✅ {len(text)}字' if text else '⚠️ 无文字稿'
            print(f'  [{i:2d}/{len(articles)}] {status} {results[-1]["title"][:50]}')
        except Exception as e:
            results.append({
                'index': i,
                'title': art.get('title', ''),
                'url': art['url'],
                'guid': '',
                'duration': '',
                'text': '',
                'text_len': 0,
                'error': str(e),
            })
            print(f'  [{i:2d}/{len(articles)}] ❌ 失败: {e}')

    total_chars = sum(r['text_len'] for r in results)
    print(f'📊 总计: {len(results)} 条, {total_chars} 字')

    data = {
        'date': date_str,
        'fetched_at': datetime.now().isoformat(),
        'total': len(results),
        'total_chars': total_chars,
        'articles': results,
    }

    # 保存 JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / f"{date_str}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'💾 已保存: {out_path}')

    return data


def fetch_recent_days(days: int = 7) -> list[dict]:
    """抓取最近 N 天的数据（跳过已存在的）"""
    results = []
    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y%m%d')
        out_path = DATA_DIR / f"{date_str}.json"

        if out_path.exists():
            print(f'⏭️ {date_str} 已存在，跳过')
            with open(out_path, 'r') as f:
                results.append(json.load(f))
            continue

        try:
            data = fetch_daily(date_str)
            results.append(data)
        except Exception as e:
            print(f'❌ {date_str} 抓取失败: {e}')

    return results


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith('--date='):
            date_str = arg.split('=')[1]
            fetch_daily(date_str)
        elif arg.startswith('--days='):
            days = int(arg.split('=')[1])
            fetch_recent_days(days)
        elif arg == '--today':
            fetch_daily(datetime.now().strftime('%Y%m%d'))
        else:
            print('Usage:')
            print('  python fetch_xwlb.py --today')
            print('  python fetch_xwlb.py --date=20260611')
            print('  python fetch_xwlb.py --days=7')
    else:
        fetch_daily(datetime.now().strftime('%Y%m%d'))
