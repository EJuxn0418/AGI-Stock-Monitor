"""歷史足跡：交易紀錄出現過的所有股票（含「曾持有」），盤後用同一套訊號掃描。
另外負責把今天新記的交易推到 #操作留痕。"""
from common import resolve, daily_history, make_embeds, send, mono, today_tw
from config import load_trades, compute_holdings, load_radar, load_settings
import industry
import signals


def run():
    """盤後：經手過的股票。持有中的一定列出；其他只列有訊號的；已在產業雷達出現的不重複（雷達卡片上有 ⭐）。"""
    import radar
    cfg = load_settings()
    seen = load_trades(include_seen=True)
    holdings, _ = compute_holdings([t for t in seen if t["side"]])
    held = {h["code"] for h in holdings}
    names = {}
    for t in seen:
        names[t["code"]] = t["name"]
    pool_tags = {p["code"]: p["tags"] for p in load_radar()}
    codes = list(names)
    ymap = resolve(codes)
    hist = daily_history(ymap.values())

    held_f, hit_f, quiet, dup = [], [], 0, 0
    for c in codes:
        if c in radar.LAST["hits"]:
            dup += 1
            continue
        sig = signals.analyze(hist.get(ymap[c]), cfg)
        if not sig:
            continue
        ind = industry.info(c)["industry"]
        f = signals.field(names[c], c, ind, pool_tags.get(c, ""), sig)
        if c in held:
            if not sig["hit"]:
                f["value"] += "\n（無訊號）"
            f["name"] = "💼 " + f["name"]
            held_f.append(f)
        elif sig["hit"]:
            hit_f.append(f)
            radar.LAST["hits"][c] = {"sig": sig, "name": names[c], "industry": ind, "star": False, "source": "footprint"}
        else:
            quiet += 1
    desc = f"另有 {quiet} 檔無訊號" + (f"；{dup} 檔已列在產業雷達（⭐）" if dup else "")
    send("WH_KEY_WATCH", make_embeds("👣 盤後歷史足跡", held_f + hit_f, 0xE67E22, description=desc), label="歷史足跡")
    return f"足跡 {len(codes)} 檔：持有 {len(held_f)}、有訊號 {len(hit_f)}、無訊號 {quiet}、與雷達共振 {dup}"


def trade_log():
    today = today_tw()
    todays = [t for t in load_trades() if t["date"] == today]
    if not todays:
        return "今日無新交易"
    fields = []
    for t in todays:
        act = "🟥 買進" if t["side"] > 0 else "🟩 賣出"
        price, qty = t["price"], t["qty"]
        value = "\n".join(x for x in [f"價格 {mono(f'{price:.2f}')}　股數 {mono(f'{qty:,.0f}')}",
                                      f"{t['type']}" + (f"｜{t['note']}" if t["note"] else "")] if x)
        fields.append({"name": f"{act} {t['name']} {t['code']}", "value": value, "inline": True})
    send("WH_TRADE_LOG", make_embeds(f"📝 操作留痕｜{today:%Y/%m/%d}", fields, 0x34495E), label="操作留痕")
    return f"今日 {len(todays)} 筆交易"
