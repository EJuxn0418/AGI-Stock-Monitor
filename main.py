import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# --- 1. 持倉清單 (13:00 報告) ---
MY_PORTFOLIO = {
    '0050.TW': ['0050', 20],   # 月線
    '00941.TW': ['00941', 10], # 10日線
    '2646.TW': ['星宇航空', 20] # 月線
}

# --- 2. 題材池 (09:30 篩選) ---
THEME_POOL = {
    'AI/半導體': ['2330.TW', '2317.TW', '2382.TW', '3231.TW', '2454.TW'],
    '儲能/永續': ['1513.TW', '1503.TW', '6806.TW', '1101.TW'],
    '金融/材料': ['2881.TW', '2882.TW', '1301.TW', '1717.TW']
}

def get_status(ticker, ma_days):
    df = yf.download(ticker, period="3mo", progress=False)
    if df.empty: return None
    curr = float(df['Close'].iloc[-1])
    ma = float(df['Close'].rolling(window=ma_days).mean().iloc[-1])
    return curr, ma, (curr >= ma)

def main():
    token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    hour = now.hour
    
    if hour < 11: # 09:30 模式：推薦名單
        msg = f"🌅 宜駿的早盤題材推薦 ({now.strftime('%H:%M')})\n"
        msg += "篩選標準：強勢站上 5MA\n━━━━━━━━━━━━━━━\n"
        for category, tickers in THEME_POOL.items():
            found = []
            for t in tickers:
                res = get_status(t, 5) # 推薦看 5MA 強勢股
                if res and res[2]: found.append(t.split('.')[0])
            if found: msg += f"【{category}】: {', '.join(found)}\n"
        msg += "\n💡 建議加入今日觀察清單"
    
    else: # 13:00 模式：綜合分析
        msg = f"📊 宜駿的 AGI 綜合報告 ({now.strftime('%H:%M')})\n━━━━━━━━━━━━━━━\n"
        msg += "【持倉狀態】\n"
        for t, info in MY_PORTFOLIO.items():
            res = get_status(t, info[1])
            if res:
                status = "✅ 站上" if res[2] else "⚠️ 跌破"
                msg += f"• {info[0]}: {res[0]:.2f} ({status}{info[1]}MA)\n"
        
        msg += "\n【早盤題材後續追蹤】\n"
        for _, tickers in THEME_POOL.items():
            for t in tickers:
                res = get_status(t, 5)
                if res and res[2]: # 依然維持在 5MA 之上
                    msg += f"🔥 {t.split('.')[0]} 持續強勢\n"

    send_line_push(token, user_id, msg)

def send_line_push(token, user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    main()
