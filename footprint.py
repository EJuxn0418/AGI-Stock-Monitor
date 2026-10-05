"""歷史足跡觀察池：交易紀錄出現過的所有股票 + 手動觀察名單，盤後掃描均線型態。
另外負責把今天新記的交易推到 #操作留痕。"""
from common import resolve, daily_history, ma_snapshot, make_embeds, send, mono, today_tw
from config import load_trades, compute_holdings, load_watch


def run():
    trades = load_trades()
    holdings, _ = compute_holdings(trades)
    held = {h["code"] for h in holdings}
    watch = load_watch(trades)
    ymap = resolve([w["code"] for w in watch])
    hist = daily_history(ymap.values())

    rows = []
    for w in watch:
        snap = ma_snapshot(hist.get(ymap[w["code"]]))
        if not snap:
            continue
        if snap["breakout"]:
            rank, status = 0, "🔥 壓縮後站上 5MA"
        elif snap["compressed"]:
            rank, status = 1, "🌐 均線糾結蓄勢"
        elif snap["price"] < snap["m20"]:
            rank, status = 3, "📉 在 20MA 之下"
        else:
            rank, status = 2, "⚪ 均線發散"
        price, ratio, m20 = snap["price"], snap["ratio"], snap["m20"]
        badge = "（持有中）" if w["code"] in held else ""
        rows.append((rank, {
            "name": f"{w['name']} {w['code']}{badge}",
            "value": "\n".join([status, f"現價 {mono(f'{price:.2f}')}　20MA {mono(f'{m20:.2f}')}",
                                f"壓縮率 {mono(f'{ratio:.1f}%')}"]),
            "inline": True,
        }))
    rows.sort(key=lambda r: r[0])
    fields = [r[1] for r in rows]
    hot = sum(1 for r in rows if r[0] <= 1)
    send("WH_KEY_WATCH", make_embeds("👀 盤後追蹤：歷史足跡觀察池", fields, 0xE67E22,
                                     description=f"共 {len(fields)} 檔，其中 {hot} 檔進入壓縮或突破型態"),
         label="歷史足跡")
    return f"觀察 {len(fields)} 檔，{hot} 檔有訊號"


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
