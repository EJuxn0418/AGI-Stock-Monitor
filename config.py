"""設定來源：優先讀 Google 試算表；沒設定試算表時，使用這裡的預設值。"""
import re
from common import read_tab, norm_code, enabled, fnum, parse_date, warn

PIN_TRUE = {"是", "Y", "YES", "V", "✅", "1", "TRUE", "釘選", "O"}

SETTINGS = {  # 試算表「說明」分頁可以覆寫（依「項目」欄的關鍵字對應）
    "near_pct": ("快要站上", 1.0),
    "big_vol": ("大量", 2.0),
    "midday_pct": ("午盤", 80.0),
    "top_n": ("龍頭", 3),
}

# ---- 預設值（試算表讀不到時才會用）----
DEFAULT_RADAR = [
    ("2330", "台積電", "晶圓代工、AI"), ("2303", "聯電", "成熟製程、ASIC"), ("3131", "弘塑", "先進封裝設備"),
    ("3017", "奇鋐", "散熱"), ("1503", "士電", "重電"), ("1519", "華城", "重電"), ("4979", "華星光", "CPO"),
    ("3363", "上詮", "CPO矽光子"), ("2492", "華新科", "被動元件"), ("4958", "臻鼎-KY", "PCB"),
    ("2383", "台光電", "CCL銅箔基板"), ("3105", "穩懋", "砷化鎵、矽光子"),
]
DEFAULT_TRADES = [
    {"日期": "2026/06/12", "代號": "00941", "名稱": "中信上游半導體", "動作": "買", "價格": "16.74", "股數": "2000", "類型": "長線"},
    {"日期": "2026/06/12", "代號": "00981A", "名稱": "統一台股增長", "動作": "買", "價格": "29.7625", "股數": "4000", "類型": "長線"},
]


def load_settings():
    cfg = {k: v for k, (_, v) in SETTINGS.items()}
    rows = read_tab("說明", required=("項目", "數值"))
    for r in rows or []:
        item, val = r.get("項目", ""), fnum(r.get("數值"))
        if not item or val is None:
            continue
        for key, (kw, default) in SETTINGS.items():
            if kw in item:
                cfg[key] = int(val) if isinstance(default, int) else float(val)
    return cfg


def load_radar():
    """產業雷達：代號、名稱、題材、釘選。題材空白會提醒。"""
    rows = read_tab("產業雷達", required=("代號", "題材"))
    if rows is None:
        rows = [{"代號": c, "名稱": n, "題材": t} for c, n, t in DEFAULT_RADAR]
    pool, seen = [], set()
    for r in rows:
        code = norm_code(r.get("代號"))
        if not code or code in seen:
            continue
        seen.add(code)
        tags = r.get("題材", "").strip()
        if not tags:
            warn(f"產業雷達 {code} {r.get('名稱', '')} 沒有填題材")
        pool.append({"code": code, "name": r.get("名稱") or code, "tags": tags,
                     "pinned": str(r.get("釘選", "")).strip().upper() in PIN_TRUE})
    return pool


def load_trades(include_seen=False):
    """include_seen=True 時，也回傳動作為「曾持有」的列（side=0，只用於歷史足跡）。"""
    rows = read_tab("交易紀錄", required=("代號", "動作", "價格", "股數"))
    if rows is None:
        rows = DEFAULT_TRADES
    trades = []
    for i, r in enumerate(rows):
        code = norm_code(r.get("代號"))
        act = str(r.get("動作", "")).strip()
        side = 1 if act in ("買", "買進", "買入", "BUY", "buy", "B") else -1 if act in ("賣", "賣出", "SELL", "sell", "S") else 0
        price, qty = fnum(r.get("價格")), fnum(r.get("股數"))
        if code and (act in ("曾持有", "持有過", "舊") or (side == -1 and (not price or not qty))):  # 賣但沒填價量＝曾持有
            if include_seen:
                trades.append({"date": parse_date(r.get("日期")), "code": code, "name": r.get("名稱") or code,
                               "side": 0, "price": 0, "qty": 0, "type": "", "note": r.get("備註", ""), "row": i})
            continue
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
        if not t["side"]:
            continue
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
