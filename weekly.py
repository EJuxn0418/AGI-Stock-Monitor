"""每週龍頭建議：在每個官方產業裡，依市值＋20 日平均成交值排出前 N 名，跟產業雷達比較。
只發建議，不會自動加股票；要加入請到試算表「產業雷達」新增並填題材。"""
from common import resolve, daily_history, make_embeds, send, env
from config import load_settings, load_radar
import industry

PRESELECT = 6  # 每個產業先用市值挑 6 檔，再抓成交值細排


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
    fields, new_total = [], 0
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
            mark = "✅ 已在池" if c in pool else "🆕 尚未進池"
            new_total += c not in pool
            lines.append(f"{off[c]['name']} {c}｜日均成交 {tov[c] / 1e8:,.1f} 億｜{mark}")
        out = [p for c, p in pool.items() if industry.info(c)["industry"] == ind and c not in leaders and not p["pinned"]]
        if out:
            lines.append("⬇️ 池內但不在前 " + str(n) + "（每日不會掃描，可考慮釘選或移出）：" + "、".join(p["name"] for p in out))
        fields.append({"name": f"🏷️ {ind}", "value": "\n".join(lines)[:1000], "inline": False})

    missing = [p["name"] for p in pool.values() if not p["tags"]]
    desc = f"共 {new_total} 檔新龍頭尚未進池。加入時請到試算表「產業雷達」新增一列並填題材。"
    if missing:
        desc += f"\n⚠️ 題材空白：{'、'.join(missing)}"
    target = "WH_WEEKLY" if env("WH_WEEKLY") else "WH_SYS_LOG"
    send(target, make_embeds(f"🗓️ 每週龍頭建議（每產業前 {n} 名：市值＋成交值）", fields, 0x8E44AD, description=desc),
         label="每週建議")
    return f"{len(fields)} 個產業完成排名，{new_total} 檔新龍頭"
