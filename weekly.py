"""每週題材池建議：在「候選池」裡，每個產業依市值與成交值排出前兩名，跟目前題材池比較。
只發建議，不會自動改題材池；要換股請自己改試算表。"""
from common import resolve, daily_history, make_embeds, send, env, yf
from config import load_candidates, load_theme_pool

TOP_N = 2


def market_cap(ticker):
    try:
        return float(yf.Ticker(ticker).fast_info["market_cap"] or 0)
    except Exception:
        return 0.0


def rank(cands, hist, caps, ymap):
    """回傳 {產業: [(分數, 候選), ...] 由好到壞}。市值排名與 20 日平均成交值排名各佔一半。"""
    by_sector = {}
    for c in cands:
        h = hist.get(ymap[c["code"]])
        if h is None or len(h) < 20:
            continue
        tail = h.tail(20)
        c = dict(c, turnover=float((tail["Close"] * tail["Volume"]).mean()), cap=caps.get(c["code"], 0.0))
        by_sector.setdefault(c["sector"], []).append(c)
    out = {}
    for sector, items in by_sector.items():
        cap_rank = {c["code"]: i for i, c in enumerate(sorted(items, key=lambda x: -x["cap"]))}
        tov_rank = {c["code"]: i for i, c in enumerate(sorted(items, key=lambda x: -x["turnover"]))}
        scored = sorted(items, key=lambda c: cap_rank[c["code"]] + tov_rank[c["code"]])
        out[sector] = scored
    return out


def run():
    cands = load_candidates()
    if not cands:
        return "沒有候選池分頁，略過"
    ymap = resolve([c["code"] for c in cands])
    hist = daily_history(ymap.values(), period="40d")
    caps = {c["code"]: market_cap(ymap[c["code"]]) for c in cands}
    ranked = rank(cands, hist, caps, ymap)

    current = {}
    for p in load_theme_pool():
        current.setdefault(p["theme"], set()).add(p["code"])
    in_pool = set().union(*current.values()) if current else set()

    fields = []
    for sector, items in ranked.items():
        top = items[:TOP_N]
        lines = []
        for c in top:
            mark = "✅ 已在題材池" if c["code"] in in_pool else "🆕 建議加入"
            lines.append(f"{c['name']} {c['code']}｜市值 {c['cap'] / 1e8:,.0f} 億｜日均成交 {c['turnover'] / 1e8:,.1f} 億｜{mark}")
        others = [c for c in items[TOP_N:] if c["code"] in in_pool]
        for c in others:
            lines.append(f"⬇️ {c['name']} {c['code']} 排名掉出前 {TOP_N}，可考慮移出")
        fields.append({"name": f"🏷️ {sector}", "value": "\n".join(lines)[:1000], "inline": False})

    target = "WH_WEEKLY" if env("WH_WEEKLY") else "WH_SYS_LOG"
    send(target, make_embeds("🗓️ 每週題材池建議（依市值＋成交值）", fields, 0x8E44AD,
                             description="只是建議，要換股請到試算表「題材池」分頁修改。"), label="每週建議")
    return f"{len(ranked)} 個產業完成排名"
