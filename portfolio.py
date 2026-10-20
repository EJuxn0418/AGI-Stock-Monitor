"""資產總表：由交易紀錄自動算出持倉、平均成本與損益。"""
from common import resolve, live_quotes, daily_history, send
import ui
from config import load_trades, compute_holdings


def _fmt_qty(q):
    lots, odd = divmod(int(round(q)), 1000)
    if odd == 0:
        return f"{lots}張"
    return f"{lots}張{odd}股" if lots else f"{odd}股"


def _wan(x):
    """金額縮寫：12,345 → 1.2萬"""
    return f"{x / 1e4:+,.1f}萬" if abs(x) >= 1e4 else f"{x:+,.0f}"


def run(label):
    trades = load_trades()
    holdings, realized = compute_holdings(trades)
    title = f"💰 資產總表｜{label}"
    if not holdings:
        send("WH_PORTFOLIO_SUMMARY", [ui.embed(title, f"目前全現金，沒有持倉\n累計已實現 **{realized:+,.0f}**", ui.GRAY)],
             label="總表")
        return "無持倉"

    ymap = resolve([h["code"] for h in holdings])
    live = live_quotes(ymap.values())
    hist = None
    rows, total_cost, total_value, day_pnl, missing = [], 0.0, 0.0, 0.0, []
    for h in holdings:
        t = ymap[h["code"]]
        q = live.get(t) or {}
        price, prev = q.get("price"), q.get("prev_close")
        if not price or not prev:
            if hist is None:
                hist = daily_history(ymap.values(), period="10d")
            if t in hist and len(hist[t]) >= 2:
                price = price or float(hist[t]["Close"].iloc[-1])
                prev = prev or float(hist[t]["Close"].iloc[-2])
        if not price:
            missing.append(h["code"])
            continue
        value = price * h["qty"]
        pnl = value - h["cost"]
        roi = pnl / h["cost"] * 100 if h["cost"] else 0
        today = (price - prev) / prev * 100 if prev else 0.0
        day_pnl += (price - prev) * h["qty"] if prev else 0.0
        total_cost += h["cost"]
        total_value += value
        sign = "🔴" if pnl > 0 else "🟢" if pnl < 0 else "⚪"
        kind = "⚡" if h["type"] != "長線" else "🏛️"
        rows.append((h["type"] != "長線", -roi,
                     f"{sign} **{h['name']}** `{h['code']}` {_fmt_qty(h['qty'])}\n"
                     f"　　{roi:+.1f}% {ui.bar(roi)} {_wan(pnl)}　今日 {ui.chg(today)}　{kind}"))
    tp = total_value - total_cost
    tr = tp / total_cost * 100 if total_cost else 0
    fields = [
        {"name": "持倉成本", "value": f"**{total_cost / 1e4:,.1f} 萬**", "inline": True},
        {"name": "目前市值", "value": f"**{total_value / 1e4:,.1f} 萬**", "inline": True},
        {"name": "未實現損益", "value": f"{'🔴' if tp > 0 else '🟢' if tp < 0 else '⚪'} **{_wan(tp)}（{tr:+.1f}%）**", "inline": True},
    ]
    groups = {}
    for is_short, _, line in sorted(rows):
        groups.setdefault("⚡ 短線" if is_short else "🏛️ 長線", []).append(line)
    fields += ui.sections(groups)
    desc = f"今日 {'🔴' if day_pnl > 0 else '🟢' if day_pnl < 0 else '⚪'} **{_wan(day_pnl)}**　累計已實現 {_wan(realized)}"
    if missing:
        desc += f"\n⚠️ 抓不到報價：{'、'.join(missing)}"
    color = ui.RED if tp > 0 else ui.GREEN if tp < 0 else ui.GRAY
    send("WH_PORTFOLIO_SUMMARY", [ui.embed(title, desc, color, fields[:25], "損益條每格 2%")], label="總表")
    return f"{len(holdings)} 檔持倉，未實現 {tp:+,.0f} 元"
