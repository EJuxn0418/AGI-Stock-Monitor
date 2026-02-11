import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# --- 宜駿的智慧化持倉清單 ---
MY_STOCKS = {
    '0050.TW': ['0050', 20],   # 月線 (20MA)
    '00941.TW': ['00941', 10], # 10日線
    '2646.TW': ['星宇航空', 20] # 月線 (20MA)
}

def get_stock_data():
    access_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    
    # 修正時區為台灣時間 (UTC+8)
    tz_taiwan = timezone(timedelta(hours=8))
    now_taiwan = datetime.now(tz_taiwan)
    
    report_msg = f"\n📊 宜駿的 AGI 盤中報告 ({now_taiwan.strftime('%m/%d %H:%M')})\n"
    report_msg += "━━━━━━━━━━━━━━━\n"
    
    for ticker, info in MY_STOCKS.items():
        name, ma_days = info
        df = yf.download(ticker, period="3mo", progress=False)
        if df.empty: continue
        
        current_price = float(df['Close'].iloc[-1])
        ma_value = float(df['Close'].rolling(window=ma_days).mean().iloc[-1])
        
        diff = current_price - ma_value
        status = "✅ 站上均線" if diff >= 0 else "⚠️ 跌破均線"
        
        report_msg += f"【{name}】\n"
        report_msg += f" 🔹 現價: {current_price:.2f}\n"
        report_msg += f" 🔹 {ma_days}MA: {ma_value:.2f}\n"
        report_msg += f" 🔹 狀態: {status} ({'+' if diff>=0 else ''}{diff:.2f})\n\n"

    send_line_push(access_token, user_id, report_msg)

def send_line_push(token, user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    get_stock_data()
