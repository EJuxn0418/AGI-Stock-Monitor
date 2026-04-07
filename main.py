import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1. 核心數據配置 (維持現狀)
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2], '00941.TW': ['00941', 2]}
SHORT_PORTFOLIO = {'1528.TW': ['恩德', 5, 10, 1]} # 剩 1 張
WATCH_LIST = {
    '2344.TW': '華邦電', '3481.TW': '群創', '2408.TW': '南亞科', 
    '2646.TW': '星宇航空', '3374.TWO': '精材', '3037.TW': '欣興'
}
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '3491.TWO': ['昇達科', '低軌衛星'], '2313.TW': ['華通', '低軌衛星'],
    '2359.TW': ['所羅門', 'AI/機器人'], '1528.TW': ['恩德', 'AI/機器人']
}

# --- 數據抓取模組 (維持穩定性) ---
def get_full_ma_status(ticker):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        close = hist_df['Close']
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(close.iloc[-1])
        return curr, float(close.rolling(5).mean().iloc[-1]), float(close.rolling(10).mean().iloc[-1]), float(close.rolling(20).mean().iloc[-1])
    except: return None

def get_long_term_status(ticker):
    try:
        hist_df = yf.download(ticker, period="1y", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        close = hist_df['Close']
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(close.iloc[-1])
        ma20, ma60 = float(close.rolling(20).mean().iloc[-1]), float(close.rolling(60).mean().iloc[-1])
        return curr, ma20, ma60
    except: return None

# --- Discord Embed 發送模組 (Suggestion 2 預演) ---
def send_to_discord(webhook_url, title, description, color=0x2ecc71, fields=[]):
    if not webhook_url: return
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    # 讀取四個 Webhook
    wh_portfolio = os.environ.get('WEBHOOK_PORTFOLIO')
    wh_watchlist = os.environ.get('WEBHOOK_WATCHLIST')
    wh_daily = os.environ.get('WEBHOOK_DAILY')
    wh_log = os.environ.get('WEBHOOK_LOG')
    
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)

    # --- 1. 日報類別：早盤題材 (12:00 執行) ---
    if now.hour < 12:
        theme_fields = []
        for t, info in THEME_POOL.items():
            res = get_full_ma_status(t)
            if res and res[0] >= res[1]: # 站上 5MA
                theme_fields.append({"name": f"🚀 {info[1]} | {info[0]}", "value": f"現價: `{res[0]:.2f}` (強勢站上 5MA)", "inline": True})
        
        send_to_discord(wh_daily, "🌅 早盤題材監測報告", "目前題材池中符合動能篩選之標的：", 0x3498db, theme_fields)
        send_to_discord(wh_log, "⚙️ 系統日誌", f"早盤掃描完成。觸發時間: {now.strftime('%H:%M:%S')}", 0x95a5a6)

    # --- 2. 日報與持倉類別：午盤彙整 (13:00 執行) ---
    else:
        # A. 持倉總表與長線/短線分流
        long_fields = []
        for t, info in LONG_PORTFOLIO.items():
            res = get_long_term_status(t)
            if res:
                curr, ma20, ma60 = res
                advice = "🟢 抱緊" if curr > ma20 else "🟡 季線防禦"
                long_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"現價: `{curr:.2f}` | 建議: **{advice}**", "inline": False})
        
        send_to_discord(wh_portfolio, "🏢 長線部位即時監控", "金字塔建倉區當前位階：", 0x27ae60, long_fields)

        short_fields = []
        for t, info in SHORT_PORTFOLIO.items():
            res = get_full_ma_status(t) # 抓 5, 10MA
            if res:
                curr, ma5, ma10, _ = res
                status = "✅ 穩健" if curr >= ma5 else ("⚠️ 警訊(破5MA)" if curr >= ma10 else "🚫 撤退(破10MA)")
                color = 0x2ecc71 if curr >= ma5 else (0xf1c40f if curr >= ma10 else 0xe74c3c)
                short_fields.append({"name": f"⚔️ {info[0]} ({info[3]}張)", "value": f"現價: `{curr:.2f}` | 5MA: {ma5:.2f} | 10MA: {ma10:.2f}\n狀態: **{status}**", "inline": False})
        
        # 短線除了丟持倉頻道，也要丟日報頻道，因為這是你「最常關注的重點」
        send_to_discord(wh_portfolio, "⚡ 短線動能追蹤", "右側交易部位即時狀態：", color, short_fields)
        send_to_discord(wh_daily, "📊 午盤持倉與重點簡報", "今日持倉核心摘要：", color, long_fields + short_fields)

        # B. 觀察池更新
        watch_fields = []
        for t, name in WATCH_LIST.items():
            res = get_full_ma_status(t)
            if res:
                watch_fields.append({"name": f"🔸 {name}", "value": f"現價: `{res[0]:.2f}` | 5MA: {res[1]:.2f} {'🔺' if res[0]>=res[1] else '🔻'}", "inline": True})
        
        send_to_discord(wh_watchlist, "👀 重點觀察池狀態", "等待均線糾結或突破之標的：", 0xe67e22, watch_fields)
        
        send_to_discord(wh_log, "⚙️ 系統日誌", f"午盤綜合報告發送完成。執行完畢。", 0x95a5a6)

if __name__ == "__main__":
    main()
