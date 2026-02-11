import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# --- 1. 持倉清單 ---
MY_PORTFOLIO = {
    '0050.TW': ['0050', 20],   
    '00941.TW': ['00941', 10], 
    '2646.TW': ['星宇航空', 20] 
}

# --- 2. 題材池 ---
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'],
    '2317.TW': ['鴻海', 'AI/半導體'],
    '2382.TW': ['廣達', 'AI/半導體'],
    '3231.TW': ['緯創', 'AI/半導體'],
    '2454.TW': ['聯發科', 'AI/半導體'],
    '1513.TW': ['中興電', '儲能/重電'],
    '1503.TW': ['士電', '儲能/重電'],
    '6806.TW': ['森崴能源', '永續/綠能'],
    '1101.TW': ['台泥', '永續/材料'],
    '2881.TW': ['富邦金', '金融'],
    '2882.TW': ['國泰金', '金融'],
    '1301.TW': ['台塑', '化工/材料'],
    '1717.TW': ['長興', '化工/材料']
}

def get_status(ticker, ma_days):
    try:
        df = yf.download(ticker, period="3mo", progress=False)
        if df.empty: return None
        curr = float(df['Close'].iloc[-1])
        ma = float(df['Close'].rolling(window=ma_days).mean().iloc[-1])
        diff = curr - ma
        return curr, ma, diff
    except:
        return None

def main():
    token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    
    if now.hour < 11: # 09:30 模式
        msg = f"🌅 宜駿的早盤題材分析\n📅 {now.strftime('%Y/%m/%d %H:%M')}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "🎯 篩選標準：強勢站上 5MA\n"
        
        categorized = {}
        for t, info in THEME_POOL.items():
            name, cat = info
            res = get_status(t, 5)
            if res and res[2] >= 0:
                if cat not in categorized: categorized[cat] = []
                categorized[cat].append(f"{name}")
        
        if categorized:
            for cat, stocks in categorized.items():
                msg += f"\n【{cat}】\n  🚀 {', '.join(stocks)}\n"
            msg += "\n💡 建議列入今日動能觀察"
        else:
            msg += "\n☕ 目前題材池尚無達標個股"
    
    else: # 13:00 模式
        msg = f"📊 宜駿的 AGI 綜合報告\n📅 {now.strftime('%Y/%m/%d %H:%M')}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "📂 [持倉狀態監測]\n"
        for t, info in MY_PORTFOLIO.items():
            res = get_status(t, info[1])
            if res:
                curr, ma, diff = res
                icon = "🟢" if diff >= 0 else "🔴"
                status = "站上" if diff >= 0 else "跌破"
                msg += f"{icon} {info[0]}: {curr:.2f}\n   ({status}{info[1]}MA | {'+' if diff>=0 else ''}{diff:.2f})\n"
        
        msg += "\n🔥 [題材動能追蹤]\n"
        found = False
        for t, info in THEME_POOL.items():
            name, cat = info
            res = get_status(t, 5)
            if res and res[2] >= 0:
                found = True
                msg += f"🔸 {name} ({res[2]:.2f})\n"
        if not found: msg += "   今日題材動能熄火"

    send_line_push(token, user_id, msg)

def send_line_push(token, user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type":"application/json", "Authorization":f"Bearer {token}"}
    payload = {"to":user_id, "messages":[{"type":"text", "text":text}]}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    main()
