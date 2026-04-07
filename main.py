import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1. 核心數據配置 (保持最新操作紀錄)
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2], '00941.TW': ['00941', 2]}
SHORT_PORTFOLIO = {'1528.TW': ['恩德', 5, 10, 1]} # 今日減持 1，剩 1
WATCH_LIST = {
    '2344.TW': '華邦電', '3481.TW': '群創', '2408.TW': '南亞科', 
    '2646.TW': '星宇航空', '3374.TWO': '精材', '3037.TW': '欣興'
}
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '3491.TWO': ['昇達科', '低軌衛星'], '2313.TW': ['華通', '低軌衛星'],
    '2359.TW': ['所羅門', 'AI/機器人'], '1528.TW': ['恩德', 'AI/機器人']
}

# --- 功能模組：數據抓取 ---
def get_stock_data(ticker, days=60):
    try:
        hist = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist.empty: return None
        curr = float(live['Close'].iloc[-1]) if not live.empty else float(hist['Close'].iloc[-1])
        return {
            "price": curr,
            "m5": float(hist['Close'].rolling(5).mean().iloc[-1]),
            "m10": float(hist['Close'].rolling(10).mean().iloc[-1]),
            "m20": float(hist['Close'].rolling(20).mean().iloc[-1]),
            "m60": float(hist['Close'].rolling(60).mean().iloc[-1])
        }
    except: return None

# --- 功能模組：Discord Embed 發送器 ---
def send_embed(webhook_url, title, fields, color=0x2ecc71, description=""):
    if not webhook_url: return
    payload = {
        "embeds": [{
            "title": title, "description": description, "color": color,
            "fields": fields, "footer": {"text": "AGI 投資戰情室"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    # 讀取 Webhooks
    wh = {k: os.environ.get(k) for k in [
        'WH_MORNING_REPORT', 'WH_AFTERNOON_REPORT', 'WH_PORTFOLIO_SUMMARY',
        'WH_LONG_HOLDING', 'WH_SHORT_HOLDING', 'WH_MACRO_WATCH',
        'WH_KEY_WATCH', 'WH_SYS_LOG', 'WH_TRADE_LOG'
    ]}
    
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)

    # --- 早盤：12:00 以前執行 ---
    if now.hour < 12:
        morning_fields = []
        for t, info in THEME_POOL.items():
            data = get_stock_data(t)
            if data and data['price'] >= data['m5']:
                morning_fields.append({"name": f"🚀 {info[1]} | {info[0]}", "value": f"現價: `{data['price']:.2f}` (站上 5MA)", "inline": True})
        
        send_embed(wh['WH_MORNING_REPORT'], "🌅 今日強勢題材掃描", morning_fields, 0x3498db)
        send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "狀態", "value": "早盤掃描執行成功"}], 0x95a5a6)

    # --- 午盤：12:00 以後執行 ---
    else:
        # 1. 持倉分流：長線持倉
        long_fields = []
        for t, info in LONG_PORTFOLIO.items():
            data = get_stock_data(t, 120)
            if data:
                advice = "🟢 安全" if data['price'] > data['m20'] else "🟡 季線防護"
                long_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"價: `{data['price']:.2f}` | 季線: {data['m60']:.2f}\n策略: {advice}", "inline": True})
        send_embed(wh['WH_LONG_HOLDING'], "🏢 長線左側部位狀態", long_fields, 0x27ae60)

        # 2. 持倉分流：短線持倉
        short_fields = []
        status_color = 0x2ecc71
        for t, info in SHORT_PORTFOLIO.items():
            data = get_stock_data(t)
            if data:
                status = "✅ 站穩" if data['price'] >= data['m5'] else ("⚠️ 警訊(破5MA)" if data['price'] >= data['m10'] else "🚫 撤退(破10MA)")
                if data['price'] < data['m5']: status_color = 0xf1c40f
                if data['price'] < data['m10']: status_color = 0xe74c3c
                short_fields.append({"name": f"⚔️ {info[0]} ({info[3]}張)", "value": f"價: `{data['price']:.2f}` | 5MA: {data['m5']:.2f}\n狀態: **{status}**", "inline": True})
        send_embed(wh['WH_SHORT_HOLDING'], "⚡ 短線右側部位狀態", short_fields, status_color)

        # 3. 持倉總表 (匯總資訊)
        send_embed(wh['WH_PORTFOLIO_SUMMARY'], "📊 當前持倉彙整總表", long_fields + short_fields, 0x34495e)

        # 4. 午盤日報 (精華簡報)
        send_embed(wh['WH_AFTERNOON_REPORT'], "📋 今日重點簡報", long_fields + short_fields, status_color, "今日核心持倉動向摘要：")

        # 5. 觀察池：重點與宏觀
        key_fields = []
        for t, name in WATCH_LIST.items():
            data = get_stock_data(t)
            if data: key_fields.append({"name": f"🔸 {name}", "value": f"`{data['price']:.2f}` (5MA: {data['m5']:.2f})", "inline": True})
        send_embed(wh['WH_KEY_WATCH'], "👀 重點觀察池追蹤", key_fields, 0xe67e22)

        macro_fields = []
        for t, info in THEME_POOL.items():
            data = get_stock_data(t)
            if data: macro_fields.append({"name": f"🌐 {info[0]} {info[1]}", "value": f"`{data['price']:.2f}`", "inline": True})
        send_embed(wh['WH_MACRO_WATCH'], "🌍 宏觀題材池快訊", macro_fields, 0x1abc9c)

        # 6. 操作留痕 (記錄今日持倉變化)
        send_embed(wh['WH_TRADE_LOG'], "✍️ 系統操作留痕", [{"name": "持倉變動", "value": "1528 恩德 今日減持 1 張 (剩 1 張)"}], 0x7f8c8d)

        send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "狀態", "value": "午盤綜合報告發送完成"}], 0x95a5a6)

if __name__ == "__main__":
    main()
