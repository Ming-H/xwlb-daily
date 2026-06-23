# -*- coding: utf-8 -*-
"""movers.py — 近一月涨幅榜 + 《笑傲股市》看图（L 强度 + N 新高突破 + S 量价）。

问财查近一月涨幅 top，叠加量比/换手/是否创新高，标注技术特征：
- 新高（N：突破/枢轴点候选）
- 放量（S：量价配合）
- 超买⚠（涨幅过大，笑傲股市不追已大涨的）
输出 site/data/picks/movers.json。非投资建议。
"""
import json
import subprocess
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CLI = os.path.expanduser("~/.claude/skills/hithink-market-query/scripts/cli.py")
OUT = os.path.join(ROOT, "site", "data", "picks", "movers.json")
QUERY = "近一个月涨幅最大的前30只A股股票"


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def build():
    r = subprocess.run(["python3", CLI, "--query", QUERY, "--limit", "30"],
                       capture_output=True, text=True, timeout=120)
    raw = r.stdout
    try:
        d = json.loads(raw[raw.find("{"):])
    except Exception:
        print("问财解析失败，跳过")
        return
    items = d.get("datas") or []
    # 找近一月涨幅字段名（涨跌幅[起止8位日期]）
    chkey = None
    if items:
        for k in items[0]:
            if "涨跌幅[" in k and "-" in k:
                chkey = k
                break
    movers = []
    for it in items:
        ch = it.get(chkey) if chkey else None
        vr = it.get("量比")
        tr = it.get("换手率")
        nh = it.get("是否创历史新高")
        # 《笑傲股市》看图标签
        tags = []
        is_new_high = (isinstance(nh, str) and ("是" in nh or "创" in nh)) or (isinstance(nh, bool) and nh)
        if is_new_high:
            tags.append("新高")
        if isinstance(vr, (int, float)) and vr >= 1.5:
            tags.append("放量")
        if isinstance(ch, (int, float)) and ch >= 100:
            tags.append("超买⚠")
        movers.append({
            "code": it.get("股票代码"),
            "name": it.get("股票简称"),
            "price": it.get("最新价"),
            "ch1m": _num(ch),
            "vol_ratio": _num(vr),
            "turnover": _num(tr),
            "new_high": nh,
            "tags": tags,
        })
    movers = [m for m in movers if m["ch1m"] is not None]
    movers.sort(key=lambda x: x["ch1m"], reverse=True)
    res = {"date": "近一月", "count": len(movers), "movers": movers[:30]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ 涨幅榜 {len(movers)} 只 → movers.json")
    for m in movers[:8]:
        print(f"  {m['ch1m']:>6}%  {m['code']:<10} {m['name']:<8}  {','.join(m['tags']) or '—'}")


if __name__ == "__main__":
    build()
