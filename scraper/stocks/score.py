# -*- coding: utf-8 -*-
"""
score.py — CAN SLIM 七要素子分（纯函数，不依赖网络）。

每个要素输出 0–100 子分，合成「灯塔分」0–100。阈值参考威廉·欧奈尔
《笑傲股市》CAN SLIM 与 IBD 体系，按 A 股本土化校准。
设计依据：docs/plans/2026-06-19-lighthouse-design.md §4。

声明：这是选股框架的评分逻辑，非投资建议，不给买卖点承诺。
"""
from __future__ import annotations

# 七要素权重（和为 1.0）。M 在合成时作为总开关额外加权。
WEIGHTS = {"C": 0.20, "A": 0.15, "N": 0.15, "S": 0.10, "L": 0.20, "I": 0.10, "M": 0.10}

MARKET_STATES = ("offense", "watch", "defense")


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ---------- C 当季收益：当季净利同比 ----------
def score_C(quarter_yoy: float | None) -> float:
    """当季净利润同比增长率（%，None=数据缺失→0）。
    原版 +25% 起为佳；A 股放宽：<0 → 0~20；0~25 → 20~60；25~100 → 60~95；>100 → 100。"""
    if quarter_yoy is None:
        return 0.0
    y = quarter_yoy
    if y < 0:
        return _clamp(20 + y * 0.4, 0, 20)
    if y < 25:
        return _clamp(20 + (y / 25) * 40, 20, 60)
    if y < 100:
        return _clamp(60 + ((y - 25) / 75) * 35, 60, 95)
    return 100.0


# ---------- A 年度收益：3年复合增速 + ROE ----------
def score_A(annual_cagr3: float | None, roe: float | None) -> float:
    """近3年净利润复合增速（%）+ ROE（%）。原版 +25%/ROE≥17%。"""
    s_cagr = 0.0
    if annual_cagr3 is not None:
        c = annual_cagr3
        if c >= 25:
            s_cagr = 55
        elif c >= 0:
            s_cagr = (c / 25) * 55
        else:
            s_cagr = max(0, 15 + c * 0.3)
    s_roe = _clamp((roe / 17) * 45, 0, 45) if roe is not None else 0.0  # ROE 17% → 45
    return _clamp(s_cagr + s_roe)


# ---------- N 新催化 / 新高 ----------
def score_N(pct_from_high52: float | None, has_catalyst: bool = False) -> float:
    """距 52 周高的距离（%，正=低于高点）+ 是否命中政策催化。"""
    base = 0.0
    if pct_from_high52 is not None:
        d = pct_from_high52
        if d <= 3:
            base = 85
        elif d <= 10:
            base = 70
        elif d <= 25:
            base = 50
        elif d <= 40:
            base = 30
        else:
            base = 15
    if has_catalyst:
        base = min(100, base + 15)
    return _clamp(base)


# ---------- S 供需：量比 / 换手 / 流通市值 ----------
def score_S(volume_ratio: float | None, turnover: float | None, float_mv_yi: float | None) -> float:
    """量比、换手率（%）、流通市值（亿）。放量+换手适中+盘适中=高分。"""
    s = 0.0
    if volume_ratio is not None:
        vr = volume_ratio
        if 1.5 <= vr <= 3:
            s += 35
        elif 1.2 <= vr < 1.5 or 3 < vr <= 5:
            s += 25
        elif vr >= 1.0:
            s += 15
    if turnover is not None:
        if 2 <= turnover <= 10:
            s += 30
        elif 1 <= turnover < 2 or 10 < turnover <= 20:
            s += 20
        else:
            s += 8
    if float_mv_yi is not None:
        mv = float_mv_yi
        if 50 <= mv <= 500:
            s += 35
        elif 20 <= mv < 50 or 500 < mv <= 1500:
            s += 22
        else:
            s += 10
    return _clamp(s)


# ---------- L 领涨强度：阶段涨幅在全市场百分位（替代 IBD RS Rating） ----------
def score_L(rank_pct: float | None) -> float:
    """近 6 月涨幅在全市场的百分位（0~100，越大越强）。"""
    return _clamp(rank_pct) if rank_pct is not None else 0.0


# ---------- I 机构：主力资金 + 机构持股 ----------
def score_I(main_net_5d: float | None, inst_pct: float | None) -> float:
    """主力 5 日净流入（亿元，正=流入）+ 机构/基金持股比例（%）。"""
    s = 0.0
    if main_net_5d is not None:
        if main_net_5d > 0:
            s += min(50, 20 + main_net_5d * 3)
        else:
            s += max(0, 15 + main_net_5d * 2)
    if inst_pct is not None:
        s += _clamp((inst_pct / 20) * 50, 0, 50)  # 机构 20% → 50
    return _clamp(s)


# ---------- M 大盘方向：三色 ----------
def score_M(market_state: str) -> float:
    return {"offense": 100.0, "watch": 50.0, "defense": 0.0}.get(market_state, 50.0)


# ---------- 合成灯塔分 ----------
def lighthouse_score(factors: dict, market_state: str = "watch") -> dict:
    """合成灯塔分。
    factors = {'C','A','N','S','L','I'} 各为子分 0–100（或 None 视为 0 权重跳过）。
    返回 {'score','factors','m_state'}。M 防守时整体 ×0.6（总开关压制）。"""
    m = score_M(market_state)
    subs = {"C": factors.get("C"), "A": factors.get("A"), "N": factors.get("N"),
            "S": factors.get("S"), "L": factors.get("L"), "I": factors.get("I"), "M": m}
    total = 0.0
    for k, w in WEIGHTS.items():
        v = subs.get(k)
        if v is None:
            continue
        total += v * w
    if market_state == "defense":
        total *= 0.6
    return {"score": round(_clamp(total), 1), "factors": subs, "m_state": market_state}


# ---------- 排除池 ----------
def is_excluded(meta: dict, exclude_bj: bool = True) -> tuple[bool, str]:
    """meta 含 st/delisting/listed_months/halted/board 等。返回 (是否排除, 原因)。"""
    if meta.get("st"):
        return True, "ST"
    if meta.get("delisting"):
        return True, "退市风险"
    if meta.get("listed_months", 999) < 6:
        return True, "次新(<6月)"
    if meta.get("halted"):
        return True, "停牌"
    if exclude_bj and meta.get("board") == "BJ":
        return True, "北交所"
    return False, ""


if __name__ == "__main__":
    # 自检
    f = {"C": score_C(120), "A": score_A(30, 20), "N": score_N(2, True),
         "S": score_S(2, 5, 200), "L": score_L(92), "I": score_I(3, 15)}
    print("C +120% →", score_C(120))
    print("A cagr30/roe20 →", score_A(30, 20))
    print("N 距高2%+催化 →", score_N(2, True))
    print("S 量比2/换手5/流通200亿 →", score_S(2, 5, 200))
    print("L 前8% →", score_L(92))
    print("I 流入+3亿/机构15% →", score_I(3, 15))
    print("灯塔分(进攻) →", lighthouse_score(f, "offense"))
    print("灯塔分(观望) →", lighthouse_score(f, "watch"))
    print("灯塔分(防守) →", lighthouse_score(f, "defense"))
    print("排除 ST →", is_excluded({"st": True}))
    print("排除 次新3月 →", is_excluded({"listed_months": 3}))
