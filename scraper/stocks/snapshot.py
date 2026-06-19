# -*- coding: utf-8 -*-
"""snapshot.py — 把 latest.json 的 TOP20 快照追加到 history.json（按日期去重，留近 60 期）。

配合命中回看：每日存档候选，未来跟踪其相对沪深 300 的超额收益，
用结果验证 CAN SLIM 选股在 A 股是否有效。非投资建议。
"""
import os
import json

PICKS = os.path.join(os.path.dirname(__file__), "..", "..", "site", "data", "picks")


def snapshot(date=None):
    latest_path = os.path.join(PICKS, "latest.json")
    hist_path = os.path.join(PICKS, "history.json")
    if not os.path.exists(latest_path):
        print("无 latest.json，跳过")
        return
    latest = json.load(open(latest_path, encoding="utf-8"))
    date = date or (latest.get("updated", "").split(" ")[0] or "unknown")
    hist = []
    if os.path.exists(hist_path):
        try:
            hist = json.load(open(hist_path, encoding="utf-8"))
        except Exception:
            hist = []
    hist = [h for h in hist if h.get("date") != date]
    hist.insert(0, {
        "date": date,
        "market_state": latest.get("market_state"),
        "count": latest.get("count", 0),
        "top20": [{"code": s["code"], "name": s["name"], "score": s["score"],
                   "catalyst": s.get("catalyst", False)} for s in latest.get("top20", [])],
    })
    hist = hist[:60]
    json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ snapshot {date}：累计 {len(hist)} 期 → history.json")


if __name__ == "__main__":
    import sys
    snapshot(sys.argv[1] if len(sys.argv) > 1 else None)
