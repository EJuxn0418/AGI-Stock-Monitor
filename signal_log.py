"""訊號紀錄：盤後把當天所有訊號（含 ⭐ 共振）寫進 logs/signals.csv，之後可以回頭統計哪種訊號比較準。"""
import csv
import os
from common import today_tw


def run():
    import radar
    hits = radar.LAST["hits"]
    if not hits:
        return "今日無訊號"
    os.makedirs("logs", exist_ok=True)
    path = os.path.join("logs", "signals.csv")
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["日期", "代號", "名稱", "產業", "來源", "共振", "收盤", "漲跌%", "剛站上", "快要站上", "量能", "量比"])
        for code, h in hits.items():
            s = h["sig"]
            w.writerow([today_tw().isoformat(), code, h["name"], h["industry"], h["source"], "⭐" if h["star"] else "",
                        f"{s['price']:.2f}", f"{s['chg']:.2f}", "/".join(map(str, s["crossed"])),
                        "/".join(str(n) for n, _ in s["near"]), s["vol"][0] if s["vol"] else "",
                        f"{s['vol'][1]:.2f}" if s["vol"] else ""])
    stars = sum(1 for h in hits.values() if h["star"])
    return f"記錄 {len(hits)} 筆訊號（共振 {stars}）"
