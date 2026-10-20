"""每週龍頭建議：在每個官方產業裡，依市值＋20 日平均成交值排出前 N 名，跟產業雷達比較。
只發建議，不會自動加股票；要加入請到試算表「產業雷達」新增並填題材。"""
from common import resolve, daily_history, send, env
import ui
from config import load_settings, load_radar
import industry

PRESELECT = 6  # 每個產業先用市值挑 6 檔，再抓成交值細排
MIN_TURNOVER = 3e8  # 日均成交值低於 3 億不建議（量太小，均線訊號不可靠）


def run():
    cfg = load_settings()
    n = cfg["top_n"]
    off = industry.official()
    px = industry.day_closes()
    if not off or not px:
        return "官方資料讀取失敗，略過"
    groups = {}
    for code, v in off.items():
        if v["industry"] in industry.SKIP or not v["shares"] or code not in px:
            continue
        groups.setdefault(v["industry"], []).append((v["shares"] * px[code], code))
    pre = {ind: [c for _, c in sorted(items, reverse=True)[:PRESELECT]] for ind, items in groups.items()}
    ymap = resolve([c for cs in pre.values() for c in cs])
    hist = daily_history(ymap.values(), period="40d")

    pool = {p["code"]: p for p in load_radar()}
    groups, new_rows = {}, []
    for ind in sorted(pre):
        cs = pre[ind]
        mcap_rank = {c: i for i, c in enumerate(cs)}
        tov = {}
        for c in cs:
            h = hist.get(ymap[c])
            tov[c] = float((h["Close"] * h["Volume"]).tail(20).mean()) if h is not None and len(h) else 0.0
        tov_rank = {c: i for i, c in enumerate(sorted(cs, key=lambda x: -tov[x]))}
        leaders = sorted(cs, key=lambda c: mcap_rank[c] + tov_rank[c])[:n]
        lines = []
        for c in leaders:
            if c in pool:
                lines.append(f"✅ {off[c]['name']} `{c}`　{tov[c] / 1e8:,.1f}億")
            elif tov[c] >= MIN_TURNOVER:
                lines.append(f"🆕 **{off[c]['name']}** `{c}`　{tov[c] / 1e8:,.1f}億")
                new_rows.append(f"{c}\t{off[c]['name']}\t{ind}\t")
        out = [p["name"] for c, p in pool.items() if industry.info(c)["industry"] == ind and c not in leaders and not p["pinned"]]
        if out:
            lines.append("⬇️ 沒掃到：" + "、".join(out))
        if lines:
            groups[f"▌{ind}"] = lines

    missing = [p["name"] for p in pool.values() if not p["tags"]]
    desc = [f"**🆕 {len(new_rows)} 檔新龍頭**（日均成交 ≥ {MIN_TURNOVER / 1e8:.0f} 億）　✅ 已在池　⬇️ 池內但不在前 {n}、沒釘選"]
    if missing:
        desc.append(f"⚠️ 題材空白：{'、'.join(missing)}")
    desc.append(ui.RULE)
    target = "WH_WEEKLY" if env("WH_WEEKLY") else "WH_SYS_LOG"
    cards = ui.board(f"🗓️ 每週龍頭建議（每產業前 {n} 名）", "\n".join(desc), groups, ui.GRAY)
    if new_rows:
        paste = "要加入就複製下面整段，貼到「產業雷達」最下面一列，再把題材改成你的寫法：\n```\n" + "\n".join(new_rows) + "\n```"
        cards.append(ui.embed("📋 可直接貼上的新龍頭", paste[:4000], ui.GRAY))
    send(target, cards, label="每週建議")
    return f"{len(groups)} 個產業完成排名，{len(new_rows)} 檔新龍頭"
