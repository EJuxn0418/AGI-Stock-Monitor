"""產業雷達：依官方產業分組，每個產業掃描市值前 N 名（釘選的另外加），只列出有訊號的股票。
morning：剛站上／快要站上（即時價）　afternoon：加上大量紅K／黑K、族群熱度　midday：午盤量能異常"""
from common import resolve, live_quotes, daily_history, make_embeds, send, env, warn
from config import load_settings, load_radar, load_trades
import industry
import signals

LAST = {"hits": {}, "scanned": set()}  # 給歷史足跡與訊號紀錄用


def target():
    return "WH_RADAR" if env("WH_RADAR") else "WH_RADAR_SEMICON"


def footprint_codes():
    return {t["code"] for t in load_trades(include_seen=True)}


def select(pool, hist, ymap, top_n):
    """每個官方產業取市值前 N 名＋釘選。回傳 [(item, 產業)]。"""
    groups = {}
    for p in pool:
        inf = industry.info(p["code"])
        if inf["industry"] in industry.SKIP:
            continue
        h = hist.get(ymap[p["code"]])
        price = float(h["Close"].iloc[-1]) if h is not None and len(h) else 0.0
        mcap = (inf["shares"] or 0) * price
        groups.setdefault(inf["industry"], []).append((mcap, p))
    chosen = []
    for ind, items in groups.items():
        items.sort(key=lambda x: -x[0])
        top = [p for _, p in items[:top_n]]
        extra = [p for _, p in items[top_n:] if p["pinned"]]
        chosen += [(p, ind) for p in top + extra]
    return chosen


def run(mode):
    cfg = load_settings()
    pool = load_radar()
    foot = footprint_codes()
    ymap = resolve([p["code"] for p in pool] + (list(foot) if mode == "midday" else []))
    hist = daily_history(ymap.values())
    chosen = select(pool, hist, ymap, cfg["top_n"])

    if mode == "midday":
        return _midday(cfg, pool, foot, ymap, hist)

    live = live_quotes([ymap[p["code"]] for p, _ in chosen]) if mode == "morning" else {}
    by_ind, scanned = {}, {}
    LAST["hits"], LAST["scanned"] = {}, set()
    for p, ind in chosen:
        t = ymap[p["code"]]
        sig = signals.analyze(hist.get(t), cfg, live=live.get(t), use_volume=(mode == "afternoon"))
        if not sig:
            continue
        scanned[ind] = scanned.get(ind, 0) + 1
        LAST["scanned"].add(p["code"])
        if not sig["hit"]:
            continue
        star = p["code"] in foot
        LAST["hits"][p["code"]] = {"sig": sig, "name": p["name"], "industry": ind, "star": star, "source": "radar"}
        by_ind.setdefault(ind, []).append(signals.field(p["name"], p["code"], ind, p["tags"], sig, star))

    title = "🌅 09:30 早盤雷達" if mode == "morning" else "🌍 15:00 盤後雷達"
    embeds = []
    if mode == "afternoon" and scanned:
        heat = sorted(scanned, key=lambda k: (-len(by_ind.get(k, [])) / scanned[k], -len(by_ind.get(k, []))))
        top = [k for k in heat if by_ind.get(k)][:3]
        if top:
            desc = "\n".join(f"{i + 1}. **{k}**　{len(by_ind[k])}/{scanned[k]} 檔出現訊號" for i, k in enumerate(top))
            embeds += make_embeds("🔥 今日族群熱度 Top 3", [], 0xE74C3C, description=desc)
    for ind in sorted(by_ind, key=lambda k: -len(by_ind[k])):
        embeds += make_embeds(f"{title}｜{ind}", by_ind[ind], 0xE74C3C if mode == "morning" else 0xC0392B)
    if embeds:
        send(target(), embeds, label="產業雷達")
    n_hits = sum(len(v) for v in by_ind.values())
    return f"掃描 {sum(scanned.values())} 檔（{len(scanned)} 個產業，池內共 {len(pool)} 檔），{n_hits} 檔有訊號"


def _midday(cfg, pool, foot, ymap, hist):
    names = {p["code"]: (p["name"], p["tags"]) for p in pool}
    for t in load_trades(include_seen=True):
        names.setdefault(t["code"], (t["name"], ""))
    codes = list(dict.fromkeys([p["code"] for p in pool] + list(foot)))
    live = live_quotes([ymap[c] for c in codes])
    fields = []
    for c in codes:
        t = ymap[c]
        r = signals.midday_volume(hist.get(t), live.get(t), cfg)
        if not r:
            continue
        kind, ratio, chg = r
        name, tags = names.get(c, (c, ""))
        ind = industry.info(c)["industry"]
        star = "⭐ " if c in foot else ""
        head = f"{star}{name} {c}｜{ind}" + (f"｜{tags}" if tags else "")
        fields.append((ratio, {"name": head[:250], "inline": False,
                               "value": f"{live[t]['price']:,.2f}　{signals.chg_text(chg)}\n⚡ 已達 20 日均量 {ratio * 100:.0f}%（{kind}）"}))
    fields.sort(key=lambda x: -x[0])
    if fields:
        send(target(), make_embeds(f"⚡ 12:00 午盤量能異常（≥ 均量 {cfg['midday_pct']:.0f}%）", [f for _, f in fields], 0xF39C12),
             label="午盤量能")
    return f"檢查 {len(codes)} 檔，{len(fields)} 檔量能異常"
