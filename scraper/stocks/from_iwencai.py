# -*- coding: utf-8 -*-
"""
from_iwencai.py — 把 canslim_screener --json（问财实筛）输出转成灯塔 picks JSON。

CAN SLIM 子分用 score.py；叠加「静水」景气行业 α（时代主线半导体/电子/算力/新材料等
给予加成），体现 CAN SLIM + 静水的融合。CI 海外取不到 akshare 时，用本地问财实筛走这条路。
非投资建议。
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))
from score import score_C, score_A, score_N, score_S, score_L, score_I, lighthouse_score

# 静水：2026 时代景气主线关键词（半导体/电子/AI 硬件/算力/新材料）
HOT_KEYS = ["半导体", "芯片", "电子", "光", "芯", "算力", "电路", "钨", "材",
            "智能", "微", "讯", "科技", "讯", "创", "新材"]
HOT_ALPHA = 5  # 景气行业 α 加成


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def hot_alpha(name: str) -> bool:
    return any(k in str(name) for k in HOT_KEYS)


def parse(path):
    """canslim_screener 输出 markdown 体检表，直接解析表格行。"""
    import re
    text = open(path, encoding="utf-8").read()
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or "（" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 8:
            continue
        m = re.match(r"(.+?)（(\d{6})\.\w{2}）", cells[1])
        if not m:
            continue
        name, code = m.group(1).strip(), m.group(2)

        def val(cell, key):
            mm = re.search(re.escape(key) + r"=(-?[\d.]+)", cell)
            return float(mm.group(1)) if mm else None

        c_cell, a_cell, s_cell, l_cell, i_cell = cells[2], cells[3], cells[5], cells[6], cells[7]
        rows.append(dict(
            name=name, code=code, price=None,
            c_yoy=val(c_cell, "归母净利润同比增长率[20260331]"),
            a_yoy=val(c_cell, "归母净利润同比增长率[20251231]"),
            roe=val(a_cell, "净资产收益率[20260331]"),
            vr=val(s_cell, "量比"),
            turn=val(s_cell, "换手率[20260618]"),
            chg_year=val(l_cell, "涨跌幅[20250619-20260618]"),
            main_net=val(i_cell, "主力资金流向"),
            inst=val(i_cell, "机构持股占流通股比例[20260331]"),
        ))
    return rows


def build(rows, market_state="watch", top=20):
    # L 用近一年涨幅在候选内排名百分位（替代 IBD RS Rating）
    chgs = sorted([r["chg_year"] or 0 for r in rows])
    n = max(1, len(chgs))
    out = []
    for r in rows:
        cy = r["chg_year"] if r["chg_year"] is not None else 0
        rank = sum(1 for c in chgs if c <= cy) / n * 100
        is_hot = hot_alpha(r["name"])
        f = {
            "C": score_C(r["c_yoy"]),
            "A": score_A(r["a_yoy"], r["roe"]),
            "N": score_N(2, has_catalyst=is_hot),      # 候选已创120日新高；景气=催化
            "S": score_S(r["vr"], r["turn"], None),
            "L": score_L(rank),
            "I": score_I((r["main_net"] or 0) / 1e8 if r["main_net"] else None, r["inst"]),
        }
        res = lighthouse_score(f, market_state)
        score = min(100, res["score"] + (HOT_ALPHA if is_hot else 0))
        out.append({
            "code": r["code"], "name": r["name"], "price": r["price"],
            "score": round(score, 1),
            "ch60d": round(cy, 1),
            "L": round(f["L"]), "S": round(f["S"]),
            "catalyst": is_hot,
            "factors": {k: round(v) for k, v in res["factors"].items()},
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return {"market_state": market_state, "updated": "2026-06-18 问财实筛（CAN SLIM+静水）",
            "count": len(rows), "top20": out[:top]}


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(__file__), "..", "..", "site", "data", "picks", "latest.json")
    rows = parse(src)
    res = build(rows)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    hot = sum(1 for s in res["top20"] if s["catalyst"])
    print(f"✓ 写入 {len(res['top20'])} 只（其中景气行业 {hot} 只）→ {dst}")
    for s in res["top20"][:12]:
        flag = "🚩景气" if s["catalyst"] else "     "
        print(f"  {s['score']:>5}  {s['code']:<7} {s['name']:<8} 近年{s['ch60d']:>+7.1f}%  {flag}")
    # 快照到 history（命中回看）
    try:
        import snapshot as _s
        _s.snapshot()
    except Exception as e:
        print(f"snapshot 跳过：{e}")
