"""歷史足跡：交易紀錄出現過的所有股票（含「曾持有」），盤後用同一套訊號掃描。
另外負責把今天新記的交易推到 #操作留痕。"""
from common import resolve, daily_history, send, today_tw
import ui
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

    held_l, hit_l, quiet, dup, changes = [], [], 0, 0, []
    for c in codes:
        in_radar = c in radar.LAST["hits"]
        if in_radar and c not in held:
            dup += 1
            continue
        sig = radar.LAST["hits"][c]["sig"] if in_radar else signals.analyze(hist.get(ymap[c]), cfg)
        if not sig:
            continue
        ind = industry.info(c)["industry"]
        t = pool_tags.get(c, "")
        line = ui.row(names[c], c, sig["price"], sig["chg"], ui.tags(sig) or "—", "⭐" if in_radar else "")
        line += f"　_{t or ind}_"
        if c in held:
            held_l.append((-sig["chg"], line))
            changes.append(sig["chg"])
        elif sig["hit"]:
            hit_l.append((-sig["chg"], line))
            changes.append(sig["chg"])
            radar.LAST["hits"][c] = {"sig": sig, "name": names[c], "industry": ind, "star": False, "source": "footprint"}
        else:
            quiet += 1
    groups = {}
    if held_l:
        groups[f"💼 持有中　{len(held_l)} 檔"] = [l for _, l in sorted(held_l)]
    if hit_l:
        groups[f"📶 經手過、今天有訊號　{len(hit_l)} 檔"] = [l for _, l in sorted(hit_l)]
    desc = f"**持有 {len(held_l)}　有訊號 {len(hit_l)}**　另有 {quiet} 檔無訊號" + (f"、{dup} 檔已列在雷達（⭐）" if dup else "")
    if groups:
        send("WH_KEY_WATCH", ui.board("👣 盤後歷史足跡", desc + "\n" + ui.RULE, groups, ui.tone(changes), foot=ui.LEGEND),
             label="歷史足跡")
    return f"足跡 {len(codes)} 檔：持有 {len(held_l)}、有訊號 {len(hit_l)}、無訊號 {quiet}、與雷達共振 {dup}"


def trade_log():
    today = today_tw()
    todays = [t for t in load_trades() if t["date"] == today]
    if not todays:
        return "今日無新交易"
    lines, buy, sell = [], 0.0, 0.0
    for t in todays:
        amt = t["price"] * t["qty"]
        if t["side"] > 0:
            buy += amt
        else:
            sell += amt
        act = "🟥 買進" if t["side"] > 0 else "🟩 賣出"
        note = f"　_{t['type']}" + (f"｜{t['note']}" if t["note"] else "") + "_"
        lines.append(f"{act} **{t['name']}** `{t['code']}`　{ui.px(t['price'])} × {t['qty']:,.0f} 股 ＝ {amt:,.0f}{note}")
    desc = f"**{len(todays)} 筆**　買進 {buy:,.0f}　賣出 {sell:,.0f}\n{ui.RULE}\n" + "\n".join(lines)
    send("WH_TRADE_LOG", [ui.embed(f"📝 操作留痕｜{today:%m/%d}", desc, ui.GRAY)], label="操作留痕")
    return f"今日 {len(todays)} 筆交易"
