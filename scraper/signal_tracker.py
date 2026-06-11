# -*- coding: utf-8 -*-
"""
信号追踪 + 异动预警 + 政策生命周期 + 投资信号打分
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from extract_keywords import compute_signal_score

DICT_PATH = Path(__file__).parent / "economic_dict.yaml"
DATA_DIR = Path(__file__).parent.parent / "data"
ANALYTICS_DIR = DATA_DIR / "analytics"
DAILY_DIR = DATA_DIR / "daily"


def load_scoring_config() -> dict:
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        d = yaml.safe_load(f)
    return d.get('scoring', {})


def get_sector_stocks() -> dict:
    with open(DICT_PATH, 'r', encoding='utf-8') as f:
        d = yaml.safe_load(f)
    return {name: data.get('stocks', []) for name, data in d['sectors'].items()}


def get_analytics(date_str: str) -> dict:
    path = ANALYTICS_DIR / f"{date_str}.json"
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_analytics_range(end_date: str, days: int) -> list[dict]:
    """获取一段时间的分析数据"""
    end = datetime.strptime(end_date, '%Y%m%d')
    results = []
    for i in range(days):
        d = (end - timedelta(days=i)).strftime('%Y%m%d')
        data = get_analytics(d)
        if data:
            results.append(data)
    return results


def detect_lifecycle(keyword_or_sector: str, end_date: str, days: int = 90) -> dict:
    """
    检测政策生命周期
    返回: {stage, timeline, first_seen, intensity_trend}
    """
    all_data = get_analytics_range(end_date, days)

    timeline = []
    for day_data in sorted(all_data, key=lambda x: x['date']):
        date = day_data['date']

        # 检查是否在板块中命中
        sector_data = day_data.get('daily_sectors', {})
        hit = False
        intensity = 'none'
        for sector_name, sdata in sector_data.items():
            if sector_name == keyword_or_sector or keyword_or_sector in sdata.get('keywords', []):
                hit = True
                break

        if not hit:
            # 也检查关键词
            kws = day_data.get('daily_keywords', {})
            if keyword_or_sector in kws:
                hit = True

        if hit:
            # 获取当天强度
            intensities = day_data.get('daily_intensities', {})
            if intensities.get('intensive', 0) > 0:
                intensity = 'intensive'
            elif intensities.get('advancing', 0) > 0:
                intensity = 'advancing'
            elif intensities.get('early', 0) > 0:
                intensity = 'early'
            elif intensities.get('results', 0) > 0:
                intensity = 'results'
            else:
                intensity = 'neutral'

        timeline.append({
            'date': date,
            'hit': hit,
            'intensity': intensity if hit else 'none',
        })

    # 确定当前阶段
    hits = [t for t in timeline if t['hit']]
    if not hits:
        return {'keyword': keyword_or_sector, 'stage': '未出现', 'timeline': timeline, 'first_seen': None}

    first_seen = hits[0]['date']

    # 分析最近7天的模式
    recent = [t for t in timeline if t['hit']][-7:] if hits else []
    if not recent:
        return {'keyword': keyword_or_sector, 'stage': '未出现', 'timeline': timeline, 'first_seen': first_seen}

    # 统计强度分布
    intensity_counts = defaultdict(int)
    for t in recent:
        intensity_counts[t['intensity']] += 1

    # 判断阶段
    recent_dates = [t['date'] for t in recent]
    hit_count_last_week = len(recent)

    if hit_count_last_week <= 1 and intensity_counts.get('early', 0) > 0:
        stage = '探索研究'
        stage_code = 1
    elif hit_count_last_week <= 2 and intensity_counts.get('advancing', 0) <= 1:
        stage = '积极推进'
        stage_code = 2
    elif hit_count_last_week >= 3 or intensity_counts.get('intensive', 0) >= 2:
        stage = '密集政策期'
        stage_code = 3
    elif intensity_counts.get('results', 0) >= 2:
        stage = '成果显现'
        stage_code = 4
    else:
        stage = '稳步推进'
        stage_code = 2

    return {
        'keyword': keyword_or_sector,
        'stage': stage,
        'stage_code': stage_code,
        'timeline': timeline,
        'first_seen': first_seen,
        'hit_count': len(hits),
        'recent_hit_count': hit_count_last_week,
    }


def detect_alerts(date_str: str = None) -> list[dict]:
    """
    检测异动预警
    返回: [{type, level, keyword/sector, detail}, ...]
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')

    today = get_analytics(date_str)
    if not today:
        return []

    yesterday = (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
    last_week_data = get_analytics_range(date_str, 7)
    prev_week_data = get_analytics_range(
        (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d'), 7
    )

    alerts = []

    # 1. 板块级别的预警
    today_sectors = today.get('daily_sectors', {})

    # 本周各板块出现次数
    week_sector_counts = defaultdict(int)
    for day in last_week_data:
        for sector, sdata in day.get('daily_sectors', {}).items():
            week_sector_counts[sector] += sdata.get('count', 0)

    # 上周各板块出现次数
    prev_week_sector_counts = defaultdict(int)
    for day in prev_week_data:
        for sector, sdata in day.get('daily_sectors', {}).items():
            prev_week_sector_counts[sector] += sdata.get('count', 0)

    for sector, week_count in week_sector_counts.items():
        prev_count = prev_week_sector_counts.get(sector, 0)

        # 🔴 突发升温: 本周 >= 上周的3倍
        if prev_count == 0 and week_count >= 3:
            alerts.append({
                'type': '突发升温',
                'level': 'red',
                'sector': sector,
                'detail': f'上周0次→本周{week_count}次',
            })
        elif prev_count > 0 and week_count >= prev_count * 3:
            alerts.append({
                'type': '突发升温',
                'level': 'red',
                'sector': sector,
                'detail': f'上周{prev_count}次→本周{week_count}次 (×{week_count/prev_count:.1f})',
            })

        # 🟢 持续升温: 连续3天出现
        consecutive = 0
        for day in last_week_data:
            if sector in day.get('daily_sectors', {}):
                consecutive += 1
            else:
                break  # 从最近一天开始计数
        if consecutive >= 3:
            alerts.append({
                'type': '持续升温',
                'level': 'green',
                'sector': sector,
                'detail': f'连续{consecutive}天出现',
            })

    # 2. 关键词首次密集出现
    today_kws = today.get('daily_keywords', {})
    for kw, count in today_kws.items():
        if count >= 3:
            # 检查之前是否出现过
            appeared_before = False
            for day in prev_week_data:
                if kw in day.get('daily_keywords', {}):
                    appeared_before = True
                    break
            if not appeared_before:
                alerts.append({
                    'type': '首次密集',
                    'level': 'yellow',
                    'keyword': kw,
                    'detail': f'单日出现{count}次，近2周首次',
                })

    # 3. 消失预警
    all_sectors_ever = set()
    for day in prev_week_data:
        all_sectors_ever.update(day.get('daily_sectors', {}).keys())

    recent_sectors = set()
    for day in last_week_data[:7]:  # 最近7天
        recent_sectors.update(day.get('daily_sectors', {}).keys())

    for sector in all_sectors_ever:
        if sector not in recent_sectors:
            prev_count = prev_week_sector_counts.get(sector, 0)
            if prev_count >= 3:  # 之前出现较频繁
                alerts.append({
                    'type': '消失预警',
                    'level': 'white',
                    'sector': sector,
                    'detail': f'前2周出现{prev_count}次，近7天0次',
                })

    return alerts


def compute_sector_scores(date_str: str = None) -> list[dict]:
    """
    计算所有板块的投资信号分数
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')

    scoring_config = load_scoring_config()
    sector_stocks = get_sector_stocks()
    today = get_analytics(date_str)
    if not today:
        return []

    # 本周数据
    week_data = get_analytics_range(date_str, 7)
    # 上周数据
    prev_week_end = (datetime.strptime(date_str, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')
    prev_week_data = get_analytics_range(prev_week_end, 7)

    week_sector_counts = defaultdict(int)
    for day in week_data:
        for sector, sdata in day.get('daily_sectors', {}).items():
            week_sector_counts[sector] += sdata.get('count', 0)

    prev_week_counts = defaultdict(int)
    for day in prev_week_data:
        for sector, sdata in day.get('daily_sectors', {}).items():
            prev_week_counts[sector] += sdata.get('count', 0)

    # 计算每个板块的分数
    scored = []
    all_sectors = set(list(week_sector_counts.keys()) + list(prev_week_counts.keys()))

    for sector in all_sectors:
        week_count = week_sector_counts.get(sector, 0)
        prev_count = prev_week_counts.get(sector, 0)

        if week_count == 0:
            continue

        # 获取最高政策级别
        max_policy = ''
        for day in week_data:
            for art in day.get('articles', []):
                if sector in art.get('hit_sectors', []):
                    pl = art.get('policy_level', '')
                    if pl:
                        max_policy = pl
                        break

        # 获取最高强度
        max_intensity = ''
        intensity_order = {'early': 1, 'advancing': 2, 'intensive': 3, 'results': 4}
        for day in week_data:
            for art in day.get('articles', []):
                if sector in art.get('hit_sectors', []):
                    il = art.get('intensity_level', '')
                    if intensity_order.get(il, 0) > intensity_order.get(max_intensity, 0):
                        max_intensity = il

        # 是否首次出现（之前30天没出现过）
        is_first = prev_count == 0

        score = compute_signal_score(
            frequency=week_count,
            prev_frequency=prev_count,
            policy_level=max_policy,
            intensity_level=max_intensity,
            is_first_mention=is_first,
            scoring_config=scoring_config,
        )

        # 触发新闻
        trigger_articles = []
        for day in week_data:
            for art in day.get('articles', []):
                if sector in art.get('hit_sectors', []):
                    trigger_articles.append({
                        'date': day['date'],
                        'title': art.get('title', ''),
                    })

        scored.append({
            'sector': sector,
            'score': score,
            'week_count': week_count,
            'prev_count': prev_count,
            'trend': f'+{((week_count - prev_count) / prev_count * 100):.0f}%' if prev_count > 0 else 'NEW',
            'policy_level': max_policy,
            'intensity_level': max_intensity,
            'is_first': is_first,
            'stocks': sector_stocks.get(sector, []),
            'trigger_articles': trigger_articles[:5],
        })

    scored.sort(key=lambda x: x['score'], reverse=True)

    # 保存
    out_path = ANALYTICS_DIR / "sector_scores.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'date': date_str, 'scores': scored}, f, ensure_ascii=False, indent=2)

    print(f'📊 板块信号打分完成:')
    for s in scored[:10]:
        emoji = '🔴' if s['score'] >= 80 else '🟡' if s['score'] >= 50 else '⚪'
        print(f'  {emoji} {s["sector"]:10s} {s["score"]:3d}分 {s["trend"]:>6s} ({s["week_count"]}次/周)')

    return scored


def run_signal_analysis(date_str: str = None) -> dict:
    """运行完整信号分析"""
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')

    print(f'🔍 信号分析: {date_str}\n')

    # 1. 异动预警
    print('🚨 异动预警:')
    alerts = detect_alerts(date_str)
    if alerts:
        for a in alerts:
            level_emoji = {'red': '🔴', 'yellow': '🟡', 'green': '🟢', 'white': '⚪'}
            print(f'  {level_emoji.get(a["level"], "⚪")} {a["type"]}: {a.get("sector", a.get("keyword", ""))} - {a["detail"]}')
    else:
        print('  无异动')

    # 2. 板块打分
    print('\n📊 板块信号分数:')
    scores = compute_sector_scores(date_str)

    # 3. 生命周期（对热门板块）
    print('\n🔄 政策生命周期:')
    lifecycles = {}
    for s in scores[:5]:  # Top 5 板块
        lc = detect_lifecycle(s['sector'], date_str)
        lifecycles[s['sector']] = lc
        print(f'  {s["sector"]}: {lc["stage"]} (首次: {lc.get("first_seen", "N/A")}, 近7天: {lc["recent_hit_count"]}次)')

    # 保存完整结果
    result = {
        'date': date_str,
        'alerts': alerts,
        'sector_scores': scores,
        'lifecycles': lifecycles,
    }
    out_path = ANALYTICS_DIR / "signals.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'\n💾 信号分析已保存: {out_path}')
    return result


if __name__ == '__main__':
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    run_signal_analysis(date_str)
