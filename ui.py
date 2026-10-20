"""Discord 版面系統：所有頻道共用的色條、符號、單行格式與彙整卡片。
色條意義：紅＝偏多　綠＝偏空　金＝特別注意（共振、爆量）　灰＝系統資訊（台股慣例：紅漲綠跌）"""
from datetime import datetime, timezone
from common import now_tw, VERSION

RED, GREEN, GOLD, GRAY = 0xE74C3C, 0x2ECC71, 0xF1C40F, 0x95A5A6
LEGEND = "✅剛站上 ⏳快站上 🔥大量紅K 🧊大量黑K ⭐經手過 💼持有中"
RULE = "━━━━━━━━━━━━━━"


def footer(extra=""):
    return f"AGI 戰情室 {VERSION} · {now_tw():%m/%d %H:%M}" + (f" · {extra}" if extra else "")


def embed(title, description="", color=GRAY, fields=None, foot=""):
    e = {"title": title[:256], "color": color, "footer": {"text": footer(foot)[:2048]},
         "timestamp": datetime.now(timezone.utc).isoformat()}
    if description:
        e["description"] = description[:4096]
    if fields:
        e["fields"] = fields
    return e


def chg(c):
    if c > 0:
        return f"🔴+{c:.2f}%"
    if c < 0:
        return f"🟢{c:.2f}%"
    return "⚪0.00%"


def px(p):
    return f"{p:,.2f}" if p < 1000 else f"{p:,.0f}"


def tags(sig):
    """把訊號壓成一小段文字：✅5·20MA ⏳20MA-0.3% 🔥2.6x"""
    out = []
    if sig.get("crossed"):
        out.append("✅" + "·".join(map(str, sig["crossed"])) + "MA")
    for n, d in sig.get("near", []):
        out.append(f"⏳{n}MA{d:+.1f}%")
    if sig.get("vol"):
        kind, ratio = sig["vol"]
        out.append(("🔥" if kind == "大量紅K" else "🧊") + f"{ratio:.1f}x")
    return " ".join(out)


def row(name, code, price, change, extra="", mark=""):
    """一檔股票一行：⭐**友達** 2409　40.45 🔴+1.80%　✅5MA"""
    line = f"{mark}**{name}** `{code}`　{px(price)} {chg(change)}"
    return line + (f"　{extra}" if extra else "")


def bar(pct, full=10.0):
    """損益條：每格 2%，最多 5 格"""
    n = min(5, int(abs(pct) / (full / 5) + 0.5))
    return "▰" * n + "▱" * (5 - n)


def sections(groups):
    """{區塊標題: [行]} → 卡片欄位；行太多時自動切成多個欄位（每欄 ≤1000 字）"""
    fields = []
    for head, lines in groups.items():
        chunk, size, part = [], 0, 0
        for ln in lines:
            if chunk and size + len(ln) + 1 > 1000:
                fields.append({"name": head if part == 0 else f"{head}（續）", "value": "\n".join(chunk), "inline": False})
                chunk, size, part = [], 0, part + 1
            chunk.append(ln)
            size += len(ln) + 1
        if chunk:
            fields.append({"name": head if part == 0 else f"{head}（續）", "value": "\n".join(chunk), "inline": False})
    return fields


def board(title, description, groups, color, foot=""):
    """彙整卡片：盡量一張；超過 Discord 上限（25 欄 / 5500 字）才接續第二張，仍在同一則訊息裡。"""
    fields = sections(groups)
    cards, cur, size = [], [], len(title) + len(description)
    for f in fields:
        fs = len(f["name"]) + len(f["value"])
        if cur and (len(cur) >= 25 or size + fs > 5500):
            cards.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += fs
    cards.append(cur)
    out = []
    for i, fs in enumerate(cards):
        out.append(embed(title if i == 0 else f"{title}（續 {i + 1}）", description if i == 0 else "",
                         color, fs, foot if i == len(cards) - 1 else ""))
    return out


def tone(changes):
    """依整體漲跌決定色條：上漲家數多＝紅，下跌多＝綠"""
    up = sum(1 for c in changes if c > 0)
    down = sum(1 for c in changes if c < 0)
    return RED if up >= down else GREEN
