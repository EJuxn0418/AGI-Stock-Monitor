"""訊號引擎：剛站上 MA、快要站上 MA、盤後大量紅K／黑K、午盤量能異常。"""
import pandas as pd
from common import today_tw

MAS = (5, 10, 20, 60)


def _with_live(hist, live, today):
    df = hist[["Open", "Close", "Volume"]].astype(float).copy()
    if live and live.get("price"):
        if len(df) and df.index[-1] == today:
            df = df.iloc[:-1]
        row = {"Open": live.get("open") or live["price"], "Close": live["price"],
               "Volume": (live.get("volume") or 0) * 1000}
        df = pd.concat([df, pd.DataFrame([row], index=[today])])
    return df


def analyze(hist, cfg, live=None, use_volume=True, today=None):
    """回傳 {price, chg, crossed:[n], near:[(n, 距離%)], vol:(標籤, 倍數)|None, hit}；資料不足回傳 None。"""
    if hist is None or len(hist) < 25:
        return None
    today = today or today_tw()
    df = _with_live(hist, live, today)
    c = df["Close"]
    price, prev = float(c.iloc[-1]), float(c.iloc[-2])
    out = {"price": price, "chg": (price - prev) / prev * 100 if prev else 0.0,
           "crossed": [], "near": [], "vol": None}
    for n in MAS:
        if len(c) < n + 4:
            continue
        ma = float(c.iloc[-n:].mean())
        ma_prev = float(c.iloc[-n - 1:-1].mean())
        ma_3ago = float(c.iloc[-n - 3:-3].mean())
        if price > ma and prev <= ma_prev:
            out["crossed"].append(n)
        elif price < ma and (ma - price) / ma * 100 <= cfg["near_pct"] and ma >= ma_3ago:
            out["near"].append((n, (price - ma) / ma * 100))
    if use_volume:
        v = df["Volume"]
        avg = float(v.iloc[-21:-1].mean())
        if avg > 0:
            ratio = float(v.iloc[-1]) / avg
            if ratio >= cfg["big_vol"]:
                red = price >= float(df["Open"].iloc[-1])
                out["vol"] = ("大量紅K" if red else "大量黑K", ratio)
    out["hit"] = bool(out["crossed"] or out["near"] or out["vol"])
    return out


def midday_volume(hist, live, cfg, today=None):
    """12:00 累計量 ÷ 20 日均量 ≥ 門檻 → (紅K/黑K, 比例, 漲跌%)，否則 None。"""
    if hist is None or not live or not live.get("price") or not live.get("volume"):
        return None
    today = today or today_tw()
    df = hist[["Open", "Close", "Volume"]].astype(float)
    if len(df) and df.index[-1] == today:
        df = df.iloc[:-1]
    if len(df) < 20:
        return None
    avg = float(df["Volume"].iloc[-20:].mean())
    if avg <= 0:
        return None
    ratio = live["volume"] * 1000 / avg
    if ratio * 100 < cfg["midday_pct"]:
        return None
    prev = float(df["Close"].iloc[-1])
    red = live["price"] >= (live.get("open") or prev)
    return ("紅K" if red else "黑K", ratio, (live["price"] - prev) / prev * 100 if prev else 0.0)


def chg_text(chg):
    if chg > 0:
        return f"🔴 +{chg:.2f}%"
    if chg < 0:
        return f"🟢 {chg:.2f}%"
    return "⚪ 0.00%"


def lines(sig):
    out = []
    if sig["crossed"]:
        out.append("✅ 剛站上 " + "、".join(f"{n}MA" for n in sig["crossed"]))
    if sig["near"]:
        out.append("　".join(f"⏳ 距 {n}MA {d:+.2f}%" for n, d in sig["near"]))
    if sig["vol"]:
        tag, ratio = sig["vol"]
        out.append(f"{'🔥' if tag == '大量紅K' else '🧊'} {tag}（{ratio:.1f} 倍）")
    return out


def field(name, code, industry, tags, sig, star=False):
    head = f"{'⭐ ' if star else ''}{name} {code}｜{industry}" + (f"｜{tags}" if tags else "")
    price = sig["price"]
    body = [f"{price:,.2f}　{chg_text(sig['chg'])}"] + lines(sig)
    return {"name": head[:250], "value": "\n".join(body)[:1000], "inline": False}
