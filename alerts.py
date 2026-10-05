"""盤中警報引擎：每 5 分鐘檢查一次「警報」分頁的規則。
同一條規則觸發後當天只通知一次；條件解除（例如又站回 5MA）後才會重新武裝。"""
import json
import os
from common import (resolve, live_quotes, daily_history, ma_snapshot, make_embeds, send,
                    mono, today_tw, now_tw)
from config import load_alerts

STATE_FILE = os.path.join("state", "alert_state.json")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
        if s.get("date") == str(today_tw()):
            return s
    except Exception:
        pass
    return {"date": str(today_tw()), "active": {}}


def save_state(s):
    os.makedirs("state", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)


def evaluate(rule, snap):
    """回傳 (條件是否成立, 參考線數值)"""
    if rule["kind"] == "ma":
        line = snap[f"m{rule['target']}"]
    else:
        line = float(rule["target"])
    if line is None:
        return None, None
    hit = snap["price"] < line if rule["direction"] == "below" else snap["price"] > line
    return hit, line


def check(rules, live, hist, ymap, state):
    """純邏輯：回傳要發送的卡片欄位清單，並更新 state。"""
    fired = []
    for r in rules:
        t = ymap[r["code"]]
        q = live.get(t)
        if not q or not q.get("price"):
            continue
        snap = ma_snapshot(hist.get(t), live_price=q["price"]) if r["kind"] == "ma" else {"price": q["price"]}
        if not snap:
            continue
        hit, line = evaluate(r, snap)
        if hit is None:
            continue
        was = state["active"].get(r["id"], False)
        state["active"][r["id"]] = bool(hit)
        if hit and not was:
            gap = (snap["price"] - line) / line * 100
            word = "跌破" if r["direction"] == "below" else "站上"
            what = f"{r['target']} 日線" if r["kind"] == "ma" else f"{line:g} 元"
            price = snap["price"]
            fired.append({
                "direction": r["direction"],
                "field": {
                    "name": f"{'🟢📉' if r['direction'] == 'below' else '🔴📈'} {r['name']} {r['code']}　{word} {what}",
                    "value": "\n".join([f"現價 {mono(f'{price:.2f}')}　參考線 {mono(f'{line:.2f}')}（{gap:+.2f}%）",
                                        f"時間 {q.get('time') or now_tw().strftime('%H:%M')}"]),
                    "inline": False,
                },
            })
    return fired


def run():
    rules = load_alerts()
    if not rules:
        return "沒有啟用的警報規則"
    ymap = resolve([r["code"] for r in rules])
    live = live_quotes(ymap.values())
    need_ma = [ymap[r["code"]] for r in rules if r["kind"] == "ma"]
    hist = daily_history(need_ma) if need_ma else {}
    state = load_state()
    fired = check(rules, live, hist, ymap, state)
    save_state(state)
    for direction, title, color in (("below", "📉 跌破警報", 0x2ECC71), ("above", "📈 站上警報", 0xE74C3C)):  # 台股：紅漲綠跌
        fields = [f["field"] for f in fired if f["direction"] == direction]
        if fields:
            send("WH_ALERT", make_embeds(title, fields, color), label="警報")
    return f"{len(rules)} 條規則，觸發 {len(fired)} 條"
