# -*- coding: utf-8 -*-
"""engine + score 本地逻辑测试（不依赖网络，用样本数据）。CI/本地均可跑。"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
from score import score_C, score_A, score_N, lighthouse_score
from engine import quick_screen, final_score


def test_score_edges():
    assert score_C(120) == 100, "C +120% 应封顶 100"
    assert 0 <= score_C(-10) <= 20, "C 亏损应 0~20"
    assert score_A(30, 20) == 100, "A cagr30/roe20 应 100"
    assert score_N(2, True) == 100, "N 距高2%+催化 应 100"
    # M 防守总开关压制
    f = {"C": 100, "A": 100, "N": 100, "S": 100, "L": 90, "I": 60}
    assert lighthouse_score(f, "defense")["score"] < lighthouse_score(f, "offense")["score"]
    print("✓ score 边界 + M 总开关")


def test_quick_screen():
    spot = pd.DataFrame([
        {"code": "300750", "name": "宁德时代", "price": 200, "volume_ratio": 1.8, "turnover": 3, "float_mv_yi": 8000, "ch60d": 25, "ch_ytd": 30, "st": False, "board": "SZ"},
        {"code": "600519", "name": "贵州茅台", "price": 1500, "volume_ratio": 2.1, "turnover": 5, "float_mv_yi": 18000, "ch60d": 12, "ch_ytd": 20, "st": False, "board": "SH"},
        {"code": "000001", "name": "平安银行", "price": 12, "volume_ratio": 0.9, "turnover": 1.5, "float_mv_yi": 2000, "ch60d": -3, "ch_ytd": -5, "st": False, "board": "SZ"},
        {"code": "000333", "name": "*ST测试", "price": 3, "volume_ratio": 5, "turnover": 8, "float_mv_yi": 50, "ch60d": 40, "ch_ytd": 50, "st": True, "board": "SZ"},
    ])
    q = quick_screen(spot, "watch")
    assert "*ST测试" not in q["name"].tolist(), "ST 应被排除"
    assert q.iloc[0]["code"] == "300750", f"最强应是宁德,实际 {q.iloc[0]['code']}"
    assert q.iloc[-1]["code"] == "000001", "最弱应是平安"
    print("✓ quick_screen：ST 排除 + 排序（宁德>茅台>平安）")
    print(q[["code", "name", "quick_score", "L", "S", "ch60d"]].to_string(index=False))


def test_final_score():
    row = {"code": "600519", "name": "贵州茅台", "L": 80, "S": 60, "catalyst": False,
           "enrich": {"pct_from_high52": 8, "main_net_5d": 2.5}}
    r = final_score(row, "watch")
    assert 0 <= r["score"] <= 100
    print(f"✓ final_score 茅台(观望) = {r['score']}，七要素 = {r['factors']}")


if __name__ == "__main__":
    test_score_edges()
    test_quick_screen()
    test_final_score()
    print("\n全部通过 ✅（engine 打分逻辑正确；真实取数依赖 CI/网络环境）")
