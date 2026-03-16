import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1. 持倉清單 (Portfolio) - 監控特定均線
# ---------------------------------------------------
MY_PORTFOLIO = {
    '0050.TW': ['0050', 20],   # 月線防守
    '00941.TW': ['00941', 20], # 月線防守
    '2646.TW': ['星宇航空', 20]  # 月線防守
}

# ---------------------------------------------------
# 2. 重點觀察池 (Watch List) - 全均線追蹤 (5/10/20MA)
# ---------------------------------------------------
WATCH_LIST = {
    '3481.TW': '群創',     # 伺機尋找下一次 5MA 突破點
    '2408.TW': '南亞科',   # 記憶體雙箭頭
    '2344.TW': '華邦電',   # 記憶體雙箭頭 (NEW)
    '4967.TW': '十銓',     # 記憶體模組高彈性
    '3374.TWO': '精材',    # 先進封裝
    '2449.TW': '京元電子', # AI 測試實質受惠
    '2354.TW': '鴻準'      # 鴻海集團低基期轉機
}

# ---------------------------------------------------
# 3. 題材掃描池 (Themes) - 早盤動能快篩
# ---------------------------------------------------
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], 
    '2317.TW': ['鴻海', 'AI/半導體'],
    '3231.TW': ['緯創', 'AI/半導體'],
    '2454.TW': ['聯發科', 'AI/半導體'],
    '2376.TW': ['技嘉', 'AI/伺服器'],   # NEW: 伺服器強勢指標
    '3017.TW': ['奇鋐', 'AI/散熱'],     # NEW: 散熱高動能指標
    '1513.TW': ['中興電', '儲能/重電'],
    '1503.TW': ['士電', '儲能/重電'],
    '9958.TW': ['世紀鋼', '永續/綠能'], # NEW: 實質風電獲利強勢股
    '2891.TW': ['中信金', '金融'],       
    '2881.TW': ['富邦金', '金融'],
    '2603.TW': ['長榮', '航運'],         
    '2618.TW': ['長榮航', '航運']       
}

# --- 核心功能：取得「即時」價格與單一均線 ---
def get_realtime_status(ticker, ma_days):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if hist_df.empty: return None

        ma_value = float(hist_df['Close'].rolling(window=ma_days).mean().iloc[-1])

        if not live_df.empty:
            current_price = float(live_df['Close'].iloc[-1])
        else:
            current_price = float(hist_df['Close'].iloc[-1])

        diff = current_price - ma_value
        return current_price, ma_value, diff
    except:
        return None

# --- 新功能：取得「即時」價格與三條均線 (5/10/20) ---
def get_full_ma_status(ticker):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if hist_df.empty: return None

        close = hist_df['Close']
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])

        if not live_df.empty:
            curr = float(live_df['Close'].iloc[-1])
        else:
            curr = float(close.iloc[-1])

        return curr, ma5, ma10, ma20
    except:
        return None

def main():
    token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    
    if now.hour < 12: 
        msg = f"\n🌅 宜駿的早盤題材推薦 ({now.strftime('%m/%d %H:%M')})\n"
        msg += "🎯 標準：強勢站上 5MA (即時)\n━━━━━━━━━━━━━━━\n"
        
        categorized_results = {}
        for t, info in THEME_POOL.items():
            name, category = info
            res = get_realtime_status(t, 5)
            if res and res[2] >= 0:
                if category not in categorized_results:
                    categorized_results[category] = []
                categorized_results[category].append(f"{name} (+{res[2]:.2f})")
        
        if categorized_results:
            for cat, stocks in categorized_results.items():
                msg += f"【{cat}】\n   🚀 {', '.join(stocks)}\n"
            msg += "\n💡 以上為即時動能強勢股"
        else:
            msg += "目前題材池中尚無標的符合篩選標準。"
    
    else: 
        msg = f"\n📊 宜駿的 AGI 綜合報告 ({now.strftime('%H:%M')})\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        msg += "📂 [持倉狀態回報]\n"
        for t, info in MY_PORTFOLIO.items():
            res = get_realtime_status(t, info[1])
            if res:
                curr, ma, diff = res
                status = "✅ 站上" if diff >= 0 else "⚠️ 跌破"
                msg += f"【{info[0]}】\n"
                msg += f" 🔹 現價: {curr:.2f}\n"
                msg += f" 🔹 {info[1]}MA: {ma:.2f}\n"
                msg += f" 🔹 狀態: {status} ({'+' if diff>=0 else ''}{diff:.2f})\n\n"
        
        if WATCH_LIST:
            msg += "👀 [重點觀察池追蹤]\n"
            for t, name in WATCH_LIST.items():
                res = get_full_ma_status(t)
                if res:
                    curr, ma5, ma10, ma20 = res
                    msg += f"🔸 {name} ({curr:.2f})\n"
                    msg += f"   5MA: {ma5:.2f} {'🔺' if curr>=ma5 else '🔻'}\n"
                    msg += f"   10MA: {ma10:.2f} {'🔺' if curr>=ma10 else '🔻'}\n"
                    msg += f"   20MA: {ma20:.2f} {'🔺' if curr>=ma20 else '🔻'}\n"
                    msg += "\n"

        msg += "🔥 [早盤題材動能追蹤]\n"
        found_strong = False
        for t, info in THEME_POOL.items():
            name, category = info
            res = get_realtime_status(t, 5)
            if res and res[2] >= 0:
                found_strong = True
                msg += f"   {name}: {res[0]:.2f} (領先 {res[2]:.2f})\n"
        
        if not found_strong:
            msg += "   今日題材股動能較弱 (跌破5MA)。"

    send_line_push(token, user_id, msg)

def send_line_push(token, user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    requests.post(url, json=payload, headers=headers)

if __name__ == "__main__":
    main()
