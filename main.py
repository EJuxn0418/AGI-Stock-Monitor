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
    
    if now.hour < 11: # 09:30 模式：早盤推薦
        msg = f"\n🌅 宜駿的早盤題材推薦 ({now.strftime('%m/%d %H:%M')})\n"
        msg += "🎯 標準：強勢站上 5MA\n━━━━━━━━━━━━━━━\n"
        
        categorized_results = {}
        for t, info in THEME_POOL.items():
            name, category = info
            res = get_status(t, 5)
            if res and res[2] >= 0:
                if category not in categorized_results:
                    categorized_results[category] = []
                # 保留正負值資訊
                categorized_results[category].append(f"{name}({t.split('.')[0]}) +{res[2]:.2f}")
        
        if categorized_results:
            for cat, stocks in categorized_results.items():
                msg += f"【{cat}】\n   🚀 {', '.join(stocks)}\n"
            msg += "\n💡 建議加入今日觀察清單"
        else:
            msg += "目前題材池中尚無標的符合篩選標準。"
    
    else: # 13:00 模式：完整綜合報告
        msg = f"\n📊 宜駿的 AGI 綜合報告 ({now.strftime('%H:%M')})\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "📂 [持倉狀態回報]\n"
        for t, info in MY_PORTFOLIO.items():
            res = get_status(t, info[1])
            if res:
                curr, ma, diff = res
                status = "✅ 站上" if diff >= 0 else "⚠️ 跌破"
                msg += f"【{info[0]}】\n"
                msg += f" 🔹 現價: {curr:.2f}\n"
                msg += f" 🔹 {info[1]}MA: {ma:.2f}\n"
                msg += f" 🔹 狀態: {status} ({'+' if diff>=0 else ''}{diff:.2f})\n\n"
        
        msg += "🔥 [早盤題材動能追蹤]\n"
        found_strong = False
        for t, info in THEME_POOL.items():
            name, category = info
            res = get_status(t, 5)
            if res and res[2] >= 0:
                found_strong = True
                msg += f"🔸 [{category}] {name}: {res[0]:.2f} (領先 {res[2]:.2f})\n"
        
        if not found_strong:
            msg += "今日題材股動能較弱，未維持在 5MA 之上。"

    send_line_push(token, user_id, msg)

def send_line_push(token, user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    main()
