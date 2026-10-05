"""資產總表：由交易紀錄自動算出持倉、平均成本與損益。"""
from common import resolve, live_quotes, daily_history, make_embeds, send, mono
from config import load_trades, compute_holdings


def _fmt_qty(q):
    lots, odd = divmod(int(round(q)), 1000)
    if odd == 0:
        return f"{lots}張"
    return f"{lots}張{odd}股" if lots else f"{odd}股"


def run(label):
    trades = load_trades()
    holdings, realized = compute_holdings(trades)
    if not holdings:
        fields = [{"name": "💳 全帳戶", "value": "目前沒有持倉（全現金）。\n" + f"累計已實現損益 {mono(f'{realized:+,.0f} 元')}", "inline": False}]
        send("WH_PORTFOLIO_SUMMARY", make_embeds(f"📊 資產總表｜{label}", fields, 0x34495E), label="總表")
        return "無持倉"

    ymap = resolve([h["code"] for h in holdings])
    live = live_quotes(ymap.values())
    hist = None

    fields, total_cost, total_value, missing = [], 0.0, 0.0, []
    for h in sorted(holdings, key=lambda x: (x["type"] != "長線", x["code"])):
        t = ymap[h["code"]]
        q = live.get(t)
        price = q["price"] if q else None
        if not price:
            if hist is None:
                hist = daily_history(ymap.values(), period="10d")
            if t in hist:
                price = float(hist[t]["Close"].iloc[-1])
        if not price:
            missing.append(h["code"])
            continue
        value = price * h["qty"]
        pnl = value - h["cost"]
        roi = pnl / h["cost"] * 100 if h["cost"] else 0
        total_cost += h["cost"]
        total_value += value
        sign = "🔴" if pnl > 0 else "🟢" if pnl < 0 else "⚪"  # 台股：紅漲綠跌
        tag = "🏛️ 長線" if h["type"] == "長線" else "⚡ 短線"
        avg = h["avg"]
        fields.append({
            "name": f"{tag} | {h['name']} {h['code']}（{_fmt_qty(h['qty'])}）",
            "value": "\n".join([f"均價 {mono(f'{avg:.2f}')}　現價 {mono(f'{price:.2f}')}",
                                f"{sign} {mono(f'{roi:+.2f}%')}　{mono(f'{pnl:+,.0f} 元')}"]),
            "inline": True,
        })

    if total_cost:
        tp = total_value - total_cost
        tr = tp / total_cost * 100
        short_n = sum(1 for h in holdings if h["type"] != "長線")
        status = f"短線持有 {short_n} 檔" if short_n else "短線空手，保留現金主動權"
        fields.insert(0, {
            "name": "💳 全帳戶權益",
            "value": "\n".join([
                f"持倉成本 {mono(f'{total_cost:,.0f} 元')}",
                f"目前市值 {mono(f'{total_value:,.0f} 元')}",
                f"未實現損益 **{mono(f'{tp:+,.0f} 元（{tr:+.2f}%）')}**",
                f"累計已實現 {mono(f'{realized:+,.0f} 元')}",
                f"狀態：{status}",
            ]),
            "inline": False,
        })
    desc = f"⚠️ 抓不到報價：{'、'.join(missing)}" if missing else None
    send("WH_PORTFOLIO_SUMMARY", make_embeds(f"📊 資產總表｜{label}", fields, 0x34495E, description=desc), label="總表")
    return f"{len(holdings)} 檔持倉，未實現 {total_value - total_cost:+,.0f} 元"
