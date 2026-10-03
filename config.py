"""設定來源：優先讀 Google 試算表；沒設定試算表時，使用這裡的預設值。"""
import re
from common import read_tab, norm_code, enabled, fnum, parse_date, warn

CHANNELS = {
    "SEMICON": "WH_RADAR_SEMICON", "半導體": "WH_RADAR_SEMICON",
    "COOLING": "WH_RADAR_COOLING", "散熱": "WH_RADAR_COOLING",
    "POWER": "WH_RADAR_POWER", "重電": "WH_RADAR_POWER", "重電能源": "WH_RADAR_POWER",
    "OPTICS": "WH_RADAR_OPTICS", "光通訊": "WH_RADAR_OPTICS",
    "OTHER": "WH_RADAR_OTHER", "其他": "WH_RADAR_OTHER", "台股其他": "WH_RADAR_OTHER",
}

# ---- 預設值（試算表設定好之後就不會用到）----
DEFAULT_THEME = [
    ("2330", "台積電", "半導體核心", "SEMICON"), ("3131", "弘塑", "先進封裝設備", "SEMICON"),
    ("3583", "辛耘", "先進封裝設備", "SEMICON"), ("3324", "雙鴻", "散熱", "COOLING"),
    ("3017", "奇鋐", "散熱", "COOLING"), ("1503", "士電", "重電能源", "POWER"),
    ("1514", "亞力", "重電能源", "POWER"), ("3450", "聯鈞", "CPO矽光子", "OPTICS"),
    ("3363", "上詮", "CPO矽光子", "OPTICS"), ("1815", "富喬", "高階玻纖布", "OPTICS"),
    ("3491", "昇達科", "低軌衛星", "OPTICS"), ("6806", "雲豹能源", "綠能", "OTHER"),
    ("2646", "星宇航空", "航空觀光", "OTHER"), ("1795", "美時", "生技", "OTHER"),
    ("6472", "保瑞", "生技CDMO", "OTHER"), ("2548", "華固", "營建", "OTHER"),
    ("1101", "台泥", "儲能轉型", "OTHER"),
]
DEFAULT_WATCH = [
    ("0050", "元大台灣50"), ("2317", "鴻海"), ("2454", "聯發科"), ("1528", "恩德"),
    ("3481", "群創"), ("2421", "建準"), ("1513", "中興電"), ("2489", "瑞軒"),
    ("2344", "華邦電"), ("2646", "星宇航空"), ("3037", "欣興"),
]
DEFAULT_TRADES = [
    {"日期": "2026/06/12", "代號": "00941", "名稱": "中信上游半導體", "動作": "買", "價格": "16.74", "股數": "2000", "類型": "長線"},
    {"日期": "2026/06/12", "代號": "00981A", "名稱": "統一台股增長", "動作": "買", "價格": "29.7625", "股數": "4000", "類型": "長線"},
]


def load_theme_pool():
    rows = read_tab("題材池", required=("代號", "頻道"))
    if rows is None:
        rows = [{"代號": c, "名稱": n, "題材": t, "頻道": ch} for c, n, t, ch in DEFAULT_THEME]
    pool = []
    for r in rows:
        code = norm_code(r.get("代號"))
        if not code or not enabled(r.get("啟用")):
            continue
        ch = CHANNELS.get(r.get("頻道", "").strip().upper()) or CHANNELS.get(r.get("頻道", "").strip())
        if not ch:
            warn(f"題材池 {code} 的頻道「{r.get('頻道')}」看不懂，改送到台股其他")
            ch = "WH_RADAR_OTHER"
        pool.append({"code": code, "name": r.get("名稱") or code, "theme": r.get("題材", ""), "webhook": ch})
    return pool


def load_trades():
    rows = read_tab("交易紀錄", required=("代號", "動作", "價格", "股數"))
    if rows is None:
        rows = DEFAULT_TRADES
    trades = []
    for i, r in enumerate(rows):
        code = norm_code(r.get("代號"))
        act = str(r.get("動作", "")).strip()
        side = 1 if act in ("買", "買進", "買入", "BUY", "buy", "B") else -1 if act in ("賣", "賣出", "SELL", "sell", "S") else 0
        price, qty = fnum(r.get("價格")), fnum(r.get("股數"))
        if not code or not side or not price or not qty:
            if code:
                warn(f"交易紀錄第 {i + 2} 列看不懂（代號/動作/價格/股數），已略過")
            continue
        trades.append({"date": parse_date(r.get("日期")), "code": code, "name": r.get("名稱") or code,
                       "side": side, "price": price, "qty": qty, "type": r.get("類型") or "長線",
                       "note": r.get("備註", ""), "row": i})
    trades.sort(key=lambda t: (t["date"] is None, t["date"] or 0, t["row"]))
    return trades


def compute_holdings(trades):
    """移動平均成本法：買進加權平均，賣出按平均成本扣除並計算已實現損益。"""
    pos, realized = {}, 0.0
    for t in trades:
        p = pos.setdefault(t["code"], {"code": t["code"], "name": t["name"], "qty": 0.0, "cost": 0.0, "type": t["type"]})
        p["name"] = t["name"] or p["name"]
        if t["side"] > 0:
            p["qty"] += t["qty"]
            p["cost"] += t["qty"] * t["price"]
            p["type"] = t["type"] or p["type"]
        else:
            if p["qty"] <= 0:
                warn(f"{t['code']} 賣出時沒有持股紀錄（可能少記了買進），已略過這筆賣出")
                continue
            q = min(t["qty"], p["qty"])
            avg = p["cost"] / p["qty"]
            realized += (t["price"] - avg) * q
            p["qty"] -= q
            p["cost"] -= avg * q
    holdings = [p for p in pos.values() if p["qty"] > 0.5]
    for p in holdings:
        p["avg"] = p["cost"] / p["qty"]
    return holdings, realized


def load_watch(trades):
    """觀察清單 = 交易紀錄裡出現過的所有股票 + 「觀察」分頁手動加的。"""
    items = {}
    for t in trades:
        items.setdefault(t["code"], {"code": t["code"], "name": t["name"], "note": "曾經操作"})
    rows = read_tab("觀察", required=("代號",))
    if rows is None:
        rows = [{"代號": c, "名稱": n, "備註": ""} for c, n in DEFAULT_WATCH]
    for r in rows:
        code = norm_code(r.get("代號"))
        if code and enabled(r.get("啟用")):
            items.setdefault(code, {"code": code, "name": r.get("名稱") or code, "note": r.get("備註", "")})
    return list(items.values())


def load_alerts():
    rows = read_tab("警報", required=("代號", "條件"))
    if rows is None:
        return []
    rules = []
    for i, r in enumerate(rows):
        code = norm_code(r.get("代號"))
        cond = str(r.get("條件", "")).replace(" ", "")
        if not code or not cond or not enabled(r.get("啟用")):
            continue
        if any(k in cond for k in ("跌破", "低於", "跌下")):
            direction = "below"
        elif any(k in cond for k in ("站上", "突破", "漲破", "高於", "站回")):
            direction = "above"
        else:
            warn(f"警報第 {i + 2} 列條件「{cond}」看不懂（要有 跌破 或 站上）")
            continue
        val = fnum(r.get("數值"))
        if "日線" in cond or "MA" in cond.upper() or "均線" in cond:
            m = re.search(r"(\d+)", cond)
            n = int(m.group(1)) if m else int(val or 0)
            if n not in (5, 10, 20, 60):
                warn(f"警報第 {i + 2} 列均線天數只支援 5/10/20/60")
                continue
            kind, target = "ma", n
        else:
            if not val:
                warn(f"警報第 {i + 2} 列沒有填價格")
                continue
            kind, target = "price", val
        rules.append({"id": f"{code}|{direction}|{kind}|{target}", "code": code, "name": r.get("名稱") or code,
                      "direction": direction, "kind": kind, "target": target, "label": cond})
    return rules


def load_candidates():
    rows = read_tab("候選池", required=("代號", "產業"))
    if not rows:
        return []
    out = []
    for r in rows:
        code = norm_code(r.get("代號"))
        if code and r.get("產業"):
            out.append({"code": code, "name": r.get("名稱") or code, "sector": r["產業"].strip()})
    return out
