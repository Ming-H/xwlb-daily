# -*- coding: utf-8 -*-
"""
Hugo 内容生成器 — 投资情报广报版
将分析结果 JSON → 结构化 HTML 的 Hugo Markdown（goldmark unsafe=true 允许内联 HTML）。

设计原则：
- 不使用装饰性 emoji；信号严重度、经济相关性等用 CSS 渲染（.dot / .badge / .tag）。
- 关键数值（分数、次数）用 .score 等做 hero 数字。
- 关键词用 .chip 芯片；强度/政策用 .badge 徽章。
- 保留 build_all(date_str) 入口，run_daily.py / GitHub Action 无需改动。
"""
import html
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path(__file__).parent.parent / "data"
ANALYTICS_DIR = DATA_DIR / "analytics"
DAILY_DIR = DATA_DIR / "daily"
CONTENT_DIR = Path(__file__).parent.parent / "site" / "content"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def esc(text) -> str:
    """HTML-escape dynamic text inserted into raw-HTML components."""
    return html.escape(str(text), quote=True)


# ---------------------------------------------------------------- components
def dot(level: str) -> str:
    """严重度色点（CSS 渲染，无 emoji）。"""
    return f'<span class="dot" data-lvl="{esc(level)}" aria-hidden="true"></span>'


def score_num(value, cls: str = "score") -> str:
    """hero 数字（等宽 tabular）。"""
    return f'<span class="{cls}">{esc(value)}</span>'


def chip(text, count=None) -> str:
    """关键词芯片。"""
    inner = esc(text)
    if count is not None:
        inner += f"<b>{esc(count)}</b>"
    return f'<span class="chip">{inner}</span>'


def chips(items) -> str:
    """一组芯片。items: list[str] 或 list[(name, count)]。"""
    parts = []
    for it in items:
        if isinstance(it, (tuple, list)):
            parts.append(chip(it[0], it[1]))
        else:
            parts.append(chip(it))
    return ''.join(parts)


def badge(label, level: str = "", kind: str = "") -> str:
    """徽章。level→颜色（red/yellow/green/...），kind→语义（intensity/policy）。"""
    lvl = f' data-lvl="{esc(level)}"' if level else ''
    knd = f' data-kind="{esc(kind)}"' if kind else ''
    return f'<span class="badge"{lvl}{knd}>{esc(label)}</span>'


def kv(label, value) -> str:
    """键值对（政策级别 / 关键数据 等）。"""
    return f'<span class="kv"><i>{esc(label)}</i><b>{esc(value)}</b></span>'


def level_for_score(score) -> str:
    """分数→严重度等级（用于色点）。"""
    try:
        s = int(score)
    except (TypeError, ValueError):
        return 'muted'
    if s >= 80:
        return 'red'
    if s >= 50:
        return 'yellow'
    return 'muted'


# ---------------------------------------------------------------- pages
def build_daily_page(date_str: str) -> bool:
    """生成每日新闻页面。"""
    analytics = load_json(ANALYTICS_DIR / f"{date_str}.json")
    if not analytics:
        return False

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"
    articles = analytics.get('articles', [])
    economy_count = analytics.get('economy_count', 0)
    total = len(articles)

    fm = f"""---
title: "新闻联播 · {date_fmt}"
date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
draft: false
layout: "daily"
economy_count: {economy_count}
total_count: {total}
---
"""

    # 当日统计条
    stat = (
        f'<div class="daystat">'
        f'<span class="ds-item"><b>{total}</b><i>条新闻</i></span>'
        f'<span class="ds-item"><b>{economy_count}</b><i>条经济相关</i></span>'
        f'<span class="ds-item"><b>{date_fmt}</b><i>《新闻联播》</i></span>'
        f'</div>\n\n'
    )
    body = stat
    body += "---\n\n"

    intensity_map = {
        'early': ('探索', 'yellow'),
        'advancing': ('推进', 'gold'),
        'intensive': ('大力', 'red'),
        'results': ('成果', 'green'),
    }

    for art in articles:
        if not art.get('text') and not art.get('title'):
            continue

        is_econ = art.get('is_economy', False)
        title = esc(art.get('title', ''))
        tag = '<span class="tag tag-econ">经济</span>' if is_econ else '<span class="tag tag-gen">综合</span>'

        # 标题（内联 HTML 徽章 + 标题文本）
        body += f"### {tag} {title}\n\n"

        # 元信息块（关键词 / 强度 / 政策 / 数据）→ HTML block
        meta_parts = []
        tags = []
        if art.get('hit_sectors'):
            tags.extend(art.get('hit_sectors', []))
        if art.get('economy_keywords'):
            tags.extend(art.get('economy_keywords', [])[:5])
        if tags:
            meta_parts.append(f'<span class="chips">{chips(tags[:8])}</span>')

        intensity = art.get('intensity_level', '')
        if intensity:
            label, lvl = intensity_map.get(intensity, (intensity, 'muted'))
            meta_parts.append(badge(f'强度 · {label}', level=lvl, kind='intensity'))

        policy = art.get('policy_level', '')
        if policy:
            meta_parts.append(kv('政策级别', policy))

        numbers = art.get('key_numbers', [])
        if numbers:
            nums = ' · '.join(n.get('value', '') for n in numbers[:5])
            meta_parts.append(kv('关键数据', nums))

        if meta_parts:
            body += f'<div class="art-meta">{"".join(meta_parts)}</div>\n\n'

        # 正文（markdown 段落）
        text = art.get('text', '')
        if text:
            body += f"{text}\n\n"

        # 视频链接（胶囊按钮）
        url = art.get('url', '')
        if url:
            body += f"[查看视频 ↗]({url})\n\n"

        body += "---\n\n"

    out_dir = CONTENT_DIR / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 每日新闻页: {out_path.name}')
    return True


def build_alerts_page(date_str: str) -> bool:
    """生成异动预警页面。"""
    signals = load_json(ANALYTICS_DIR / "signals.json")
    if not signals:
        return False

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"

    fm = f"""---
title: "异动预警 · {date_fmt}"
date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
draft: false
layout: "alerts"
---
"""

    body = ""
    alerts = signals.get('alerts', [])
    if not alerts:
        body += "今日无异动预警。\n"
    else:
        level_info = {
            'red': ('突发升温', '关键词出现频率突然飙升，可能预示板块异动'),
            'yellow': ('首次密集', '关键词首次在单日密集出现，新政策信号'),
            'green': ('持续升温', '关键词连续多天出现，政策持续关注'),
            'white': ('消失预警', '之前高频关键词消失，关注度转移'),
        }
        for level in ['red', 'yellow', 'green', 'white']:
            level_alerts = [a for a in alerts if a.get('level') == level]
            if not level_alerts:
                continue
            title, desc = level_info.get(level, (level, ''))
            body += f"## {title}\n\n"
            body += f'<p class="lead">{esc(desc)}</p>\n\n'
            body += '<ul class="signals">\n'
            for a in level_alerts:
                name = a.get('sector', a.get('keyword', ''))
                detail = a.get('detail', '').replace('→', ' → ')
                body += (
                    f'  <li class="sig" data-lvl="{esc(level)}">'
                    f'{dot(level)}'
                    f'<span class="sig-name">{esc(name)}</span>'
                    f'<span class="sig-detail">{esc(detail)}</span>'
                    f'</li>\n'
                )
            body += '</ul>\n\n'

    out_dir = CONTENT_DIR / "alerts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_index.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 异动预警页: alerts/_index.md')
    return True


def build_sectors_page(date_str: str) -> bool:
    """生成板块热力图页面。"""
    signals = load_json(ANALYTICS_DIR / "signals.json")
    if not signals:
        return False

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"

    fm = f"""---
title: "板块热力图 · {date_fmt}"
date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
draft: false
layout: "sectors"
---
"""

    body = ""
    scores = signals.get('sector_scores', [])
    if not scores:
        body += "暂无板块数据。\n"
    else:
        body += "## 本周板块信号排行\n\n"
        body += "| 信号 | 板块 | 分数 | 趋势 | 次数 | 龙头股 |\n"
        body += "|:----:|:-----|:----:|:----:|:----:|:-------|\n"

        for s in scores:
            lvl = level_for_score(s['score'])
            stocks = s.get('stocks', [])
            stock_names = ' · '.join(st['name'] for st in stocks[:3])
            trend = s.get('trend', '')
            is_up = ('NEW' in str(trend)) or ('+' in str(trend))
            trend_cls = 'up' if is_up else 'down'
            arrow = '↑' if is_up else '↓'
            trend_html = f'<span class="delta {trend_cls}">{arrow} {esc(trend)}</span>'

            body += (
                f"| {dot(lvl)} | **{esc(s['sector'])}** | "
                f"{score_num(s['score'])} | {trend_html} | "
                f"{esc(s.get('week_count', ''))}次/周 | {esc(stock_names)} |\n"
            )

        body += "\n\n"

        body += "## 触发新闻\n\n"
        for s in scores[:5]:
            body += f"### {esc(s['sector'])} · {score_num(s['score'], 'score-inline')}\n\n"
            for art in s.get('trigger_articles', [])[:3]:
                body += f"- {esc(art.get('date', ''))} {esc(art.get('title', ''))}\n"
            body += "\n"

    out_dir = CONTENT_DIR / "sectors"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_index.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 板块热力图: sectors/_index.md')
    return True


def build_lifecycle_page(date_str: str) -> bool:
    """生成政策生命周期页面。"""
    signals = load_json(ANALYTICS_DIR / "signals.json")
    if not signals:
        return False

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"

    fm = f"""---
title: "政策生命周期 · {date_fmt}"
date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
draft: false
layout: "lifecycle"
---
"""

    body = ""
    lifecycles = signals.get('lifecycles', {})
    if not lifecycles:
        body += "暂无生命周期数据。\n"
    else:
        body += '<p class="lead">政策生命周期：探索研究 → 积极推进 → 密集政策期 → 成果显现 → 退潮</p>\n\n'

        stage_order = {'探索研究': 1, '积极推进': 2, '稳步推进': 2, '密集政策期': 3, '成果显现': 4}
        stage_lvl = {'探索研究': 'yellow', '积极推进': 'gold', '稳步推进': 'gold',
                     '密集政策期': 'red', '成果显现': 'green', '未出现': 'muted'}

        body += '<div class="lifecycle">\n'
        for name, lc in sorted(lifecycles.items(),
                               key=lambda x: stage_order.get(x[1].get('stage', ''), 0)):
            stage = lc.get('stage', '未知')
            lvl = stage_lvl.get(stage, 'muted')
            first = lc.get('first_seen', 'N/A')
            recent = lc.get('recent_hit_count', 0)
            total_hits = lc.get('hit_count', 0)

            body += (
                f'  <article class="lc-card" data-lvl="{esc(lvl)}">\n'
                f'    <header class="lc-head">\n'
                f'      {dot(lvl)}'
                f'      <h2>{esc(name)}</h2>\n'
                f'      {badge(stage, level=lvl, kind="stage")}\n'
                f'    </header>\n'
                f'    <div class="lc-stats">\n'
                f'      {kv("首次出现", first)}'
                f'      {kv("近7天", str(recent) + "次")}'
                f'      {kv("累计", str(total_hits) + "次")}'
                f'    </div>\n'
                f'  </article>\n'
            )
        body += '</div>\n\n'

    out_dir = CONTENT_DIR / "lifecycle"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_index.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 生命周期页: lifecycle/_index.md')
    return True


def build_hotspots_page(date_str: str) -> bool:
    """生成经济热点页面。"""
    multi = load_json(ANALYTICS_DIR / "multi_period.json")
    if not multi:
        return False

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"

    fm = f"""---
title: "经济热点 · {date_fmt}"
date: "{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
draft: false
layout: "hotspots"
---
"""

    body = ""
    periods = multi.get('periods', {})
    period_names = {
        'daily': ('今日热点', '当日出现的经济关键词'),
        'weekly': ('本周热点', '近 7 天高频关键词'),
        'monthly': ('本月热点', '近 30 天趋势'),
        'yearly': ('年度热点', '近 365 天 Top 关键词'),
    }

    for period_key, (period_title, period_desc) in period_names.items():
        data = periods.get(period_key, {})
        top_kws = data.get('top_keywords', [])

        body += f"## {period_title}\n\n"
        body += f'<p class="lead">{esc(period_desc)}</p>\n\n'

        if not top_kws:
            body += "暂无数据\n\n"
            continue

        body += "| 排名 | 关键词 | 出现次数 |\n|:----:|:-------|:--------:|\n"
        for i, (kw, count) in enumerate(top_kws[:20], 1):
            body += f"| {i} | **{esc(kw)}** | {score_num(count, 'score-inline')} |\n"
        body += "\n"

        sectors = data.get('sectors', [])
        if sectors:
            items = [(s['name'], s['count']) for s in sectors[:8]]
            body += f'<div class="sectors-row"><i>涉及板块</i>{chips(items)}</div>\n\n'

        body += "---\n\n"

    out_dir = CONTENT_DIR / "hotspots"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "_index.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 经济热点页: hotspots/_index.md')
    return True


def build_homepage(date_str: str) -> bool:
    """生成首页仪表盘。"""
    signals = load_json(ANALYTICS_DIR / "signals.json")
    analytics = load_json(ANALYTICS_DIR / f"{date_str}.json")
    multi = load_json(ANALYTICS_DIR / "multi_period.json")

    date_fmt = f"{date_str[:4]}年{int(date_str[4:6])}月{int(date_str[6:8])}日"
    economy_count = analytics.get('economy_count', 0) if analytics else 0
    total = analytics.get('total_articles', 0) if analytics else 0

    fm = f"""---
title: "央视联播投资参考"
description: "新闻联播经济信号追踪，捕捉投资机会"
layout: "home"
---
"""

    body = ""

    # 当日统计条
    body += (
        f'<div class="daystat">'
        f'<span class="ds-item"><b>{total}</b><i>条新闻</i></span>'
        f'<span class="ds-item"><b>{economy_count}</b><i>条经济相关</i></span>'
        f'<span class="ds-item"><b>{date_fmt}</b><i>最新一期</i></span>'
        f'</div>\n\n'
    )

    # 预警摘要
    if signals:
        alerts = signals.get('alerts', [])
        red_alerts = [a for a in alerts if a.get('level') == 'red']
        if red_alerts:
            body += "## 今日预警\n\n"
            body += '<ul class="signals">\n'
            for a in red_alerts[:5]:
                name = a.get('sector', a.get('keyword', ''))
                detail = a.get('detail', '').replace('→', ' → ')
                body += (
                    f'  <li class="sig" data-lvl="red">'
                    f'{dot("red")}'
                    f'<span class="sig-name">{esc(name)}</span>'
                    f'<span class="sig-detail">{esc(detail)}</span>'
                    f'</li>\n'
                )
            body += '</ul>\n\n'

    # 板块热度 Top 5（hero 数字排行榜）
    if signals:
        scores = signals.get('sector_scores', [])[:5]
        if scores:
            body += "## 板块热度 Top 5\n\n"
            body += '<ol class="board">\n'
            for i, s in enumerate(scores, 1):
                lvl = level_for_score(s['score'])
                stocks = s.get('stocks', [])
                stock_str = ' · '.join(st['name'] for st in stocks[:3])
                body += (
                    f'  <li class="board-row" data-lvl="{esc(lvl)}">\n'
                    f'    <span class="rank">{i}</span>\n'
                    f'    <span class="board-name">{esc(s["sector"])}</span>\n'
                    f'    {score_num(s["score"])}\n'
                    f'    <span class="board-stocks">{esc(stock_str)}</span>\n'
                    f'  </li>\n'
                )
            body += '</ol>\n\n'

    # 导航
    body += "## 板块导航\n\n"
    nav = [
        ("每日新闻", "/daily/", "每日《新闻联播》经济信号逐条解析"),
        ("经济热点", "/hotspots/", "日 / 周 / 月 / 年 高频关键词"),
        ("板块热力", "/sectors/", "板块分数排行与龙头股"),
        ("异动预警", "/alerts/", "关键词频次异动监测"),
        ("生命周期", "/lifecycle/", "政策从探索到退潮的轨迹"),
    ]
    body += '<nav class="navcards">\n'
    for label, url, desc in nav:
        body += (
            f'  <a class="navcard" href="{esc(url)}">\n'
            f'    <span class="navcard-title">{esc(label)}</span>\n'
            f'    <span class="navcard-desc">{esc(desc)}</span>\n'
            f'  </a>\n'
        )
    body += '</nav>\n\n'

    out_path = CONTENT_DIR / "_index.md"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)

    print(f'  ✅ 首页: _index.md')
    return True


def build_all(date_str: str = None):
    """生成所有页面。"""
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')

    print(f'📝 生成 Hugo 内容: {date_str}')
    print('-' * 30)

    build_homepage(date_str)
    build_daily_page(date_str)
    build_hotspots_page(date_str)
    build_sectors_page(date_str)
    build_alerts_page(date_str)
    build_lifecycle_page(date_str)

    print(f'\n✅ 内容生成完成')


if __name__ == '__main__':
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    build_all(date_str)
