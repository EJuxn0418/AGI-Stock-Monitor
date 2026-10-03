"""產業分流雷達：09:30 抓壓縮突破、15:00 抓均線高度壓縮。"""
from common import resolve, live_quotes, daily_history, ma_snapshot, make_embeds, send, mono
from config import load_theme_pool

LABEL = {"WH_RADAR_SEMICON": "半導體", "WH_RADAR_COOLING": "散熱", "WH_RADAR_POWER": "重電",
         "WH_RADAR_OPTICS": "光通訊", "WH_RADAR_OTHER": "台股其他"}


def run(mode):
    """mode = 'breakout'（早盤）或 'compression'（盤後）"""
    pool = load_theme_pool()
    ymap = resolve([p["code"] for p in pool])
    hist = daily_history(ymap.values())
    live = live_quotes(ymap.values()) if mode == "breakout" else {}

    groups = {}
    scanned = 0
    for p in pool:
        t = ymap[p["code"]]
        q = live.get(t)
        snap = ma_snapshot(hist.get(t), live_price=q["price"] if q else None)
        if not snap:
            continue
        scanned += 1
        hit = snap["breakout"] if mode == "breakout" else snap["compressed"]
        if not hit:
            continue
        icon = "🔥 壓縮突破" if mode == "breakout" else "🌐 籌碼蓄積"
        price, m5, ratio = snap["price"], snap["m5"], snap["ratio"]
        groups.setdefault(p["webhook"], []).append({
            "name": f"{icon} | {p['name']} {p['code']}",
            "value": "\n".join([f"現價 {mono(f'{price:.2f}')}", f"5MA {mono(f'{m5:.2f}')}",
                                f"壓縮率 {mono(f'{ratio:.1f}%')}", p["theme"]]),
            "inline": True,
        })

    if mode == "breakout":
        title, color = "🌅 早盤雷達：均線壓縮後站上 5MA", 0xE74C3C
    else:
        title, color = "🌍 盤後雷達：均線高度壓縮（≦3%）", 0x1ABC9C
    for wh, fields in groups.items():
        send(wh, make_embeds(title, fields, color), label=f"雷達-{LABEL.get(wh, wh)}")

    hits = sum(len(v) for v in groups.values())
    detail = "、".join(f"{LABEL.get(k, k)} {len(v)}" for k, v in groups.items()) or "無"
    return f"掃描 {scanned}/{len(pool)} 檔，命中 {hits} 檔（{detail}）"
