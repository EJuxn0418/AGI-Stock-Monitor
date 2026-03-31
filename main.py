import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1A. 長線左側部位 (Long-Term) - 金字塔建倉邏輯 
# ---------------------------------------------------
LONG_PORTFOLIO = {
    '0050.TW': ['0050', 2],      
    '00941.TW': ['00941', 2]     
}

# ---------------------------------------------------
# 1B. 短線右側部位 (Short-Term) - 嚴格均線停損
# ---------------------------------------------------
SHORT_PORTFOLIO = {
    '1528.TW': ['恩德', 5, 1]    
}

# ---------------------------------------------------
# 2. 重點觀察池 (Watch List) - 尋找右側突破點
# ---------------------------------------------------
WATCH_LIST = {
    '2344.TW': '華邦電',   
    '3481.TW': '群創',     
    '2408.TW': '南亞科',   
    '2646.TW': '星宇航空', 
    '4967.TW': '十銓',     
    '3374.TWO': '精材',    
    '2449.TW': '京元電子', 
    '2354.TW': '鴻準',
    '3037.TW': '欣興'      
}

# ---------------------------------------------------
# 3. 參考目標價 (Target Prices) - ⚠️ 已校準 2026 真實水位
# ---------------------------------------------------
TARGET_PRICES = {
    '0050.TW': 82.0,   # 基於近一年高點 81.8 校準
    '00941.TW': 23.0,  # 基於近一年高點 22.99 校準
    '2646.TW': 25.0, 
    '2344.TW': 136.0,  # 前波歷史高點
    '3481.TW': 32.0,  
    '2408.TW': 85.0,  
    '4967.TW': 150.0, 
    '3374.TWO': 250.0,
    '2449.TW': 130.0, 
    '2354.TW': 90.0,  
    '3037.TW': 220.0, 
    '1528.TW': 34.0    # 恩德波段歷史高點
}

# ---------------------------------------------------
# 4. 題材掃描池 (Themes) - 農場系統
# ---------------------------------------------------
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], 
    '2317.TW': ['鴻海', 'AI/半導體'],
    '2382.TW': ['廣達', 'AI/伺服器'],   
    '2454.TW': ['聯發科', 'AI/半導體'],
    '2376.TW': ['技嘉', 'AI/伺服器'],   
    '3017.TW': ['奇鋐', 'AI/散熱'],     
    '5234.TW': ['達興材料', '半導體材料'], 
    '3491.TWO': ['昇達科', '低軌衛星'],   
    '2313.TW': ['華通', '低軌衛星'],
    '1519.TW': ['華城', '儲能/重電'],    
    '1513.TW': ['中興電', '儲能/重電'], 
    '1503.TW': ['士電', '儲能/重電'],
    '6869.TW': ['雲豹能源', '儲能/綠能'], 
    '9958.TW': ['世紀鋼', '儲能/綠能'], 
    '2359.TW': ['所羅門', 'AI/機器人'],   
    '6188.TWO': ['廣明', 'AI/機器人'],    
    '1528.TW': ['恩德', 'AI/機器人'],      
    '2891.TW': ['中信金', '金融'],       
    '2881.TW': ['富邦金', '金融']
}

# --- 核心功能模組 ---
def get_realtime_status(ticker, ma_days):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        ma_value = float(hist_df['Close'].rolling(window=ma_days).mean().iloc[-1])
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(hist_df['Close'].iloc[-1])
        return curr, ma_value, curr - ma_value
    except: return None

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
        ma20, ma60, ma120 = float(close.rolling(20).mean().iloc[-1]), float(close.rolling(60).mean().iloc[-1]), float(close.rolling(120).mean().iloc[-1])
        return curr, ma20, ma60, ma120
    except: return None

def main():
    token, user_id = os.environ.get('LINE_ACCESS_TOKEN'), os.environ.get('LINE_USER_ID')
    now = datetime.now(timezone(timedelta(hours=8)))
    
    if now.hour < 12: 
        msg = f"\n🌅 宜駿的早盤題材推薦 ({now.strftime('%m/%d %H:%M')})\n🎯 標準：強勢站上 5MA\n━━━━━━━━━━━━━━━\n"
        categorized = {}
        for t, info in THEME_POOL.items():
            res = get_realtime_status(t, 5)
            if res and res[2] >= 0:
                if info[1] not in categorized: categorized[info[1]] = []
                categorized[info[1]].append(f"{info[0]} (+{res[2]:.2f})")
        if categorized:
            for cat, stocks in categorized.items(): msg += f"【{cat}】\n   🚀 {', '.join(stocks)}\n"
        else: msg += "目前題材池中尚無標的符合篩選標準。"
    else: 
        msg = f"\n📊 宜駿的 AGI 綜合報告 ({now.strftime('%H:%M')})\n━━━━━━━━━━━━━━━\n"
        msg += "🏛️ [長線左側：金字塔建倉區]\n"
        for t, info in LONG_PORTFOLIO.items():
            res = get_long_term_status(t)
            if res:
                curr, ma20, ma60, ma120 = res
                advice = "🟢 抱緊" if curr > ma20 else ("🟡 塔尖10%" if curr > ma60 else ("🟠 中段20%" if curr > ma120 else "🔴 底部40%"))
                msg += f"【{info[0]}】({info[1]}張) 現價: {curr:.2f}\n 💡 策略: {advice}\n 📉 距季線: {((curr-ma60)/ma60*100):.1f}%\n\n"
        msg += "⚔️ [短線右側：嚴格停損區]\n"
        if not SHORT_PORTFOLIO: msg += "   (空倉等待狙擊)\n\n"
        else:
            for t, info in SHORT_PORTFOLIO.items():
                res = get_realtime_status(t, info[1])
                if res:
                    curr, ma, diff = res
                    status = "✅ 站上" if diff >= 0 else "⚠️ 跌破請注意"
                    msg += f"【{info[0]}】({info[2]}張) 現價: {curr:.2f}\n"
                    if t in TARGET_PRICES: msg += f" 🎯 目標: {TARGET_PRICES[t]} (距 {((TARGET_PRICES[t]-curr)/curr*100):.1f}%)\n"
                    msg += f" 🔹 {info[1]}MA 防守: {ma:.2f}\n 🔹 狀態: {status} ({'+' if diff>=0 else ''}{diff:.2f})\n\n"
        if WATCH_LIST:
            msg += "👀 [重點觀察池追蹤]\n"
            for t, name in WATCH_LIST.items():
                res = get_full_ma_status(t)
                if res:
                    curr, m5, m10, m20 = res
                    msg += f"🔸 {name} ({curr:.2f})\n"
                    if t in TARGET_PRICES and curr > 0:
                        msg += f"   🎯 空間: {((TARGET_PRICES[t]-curr)/curr*100):.1f}%\n"
                    msg += f"   5MA: {m5:.2f}{'🔺'if curr>=m5 else'🔻'} | 10MA: {m10:.2f}{'🔺'if curr>=m10 else'🔻'} | 20MA: {m20:.2f}{'🔺'if curr>=m20 else'🔻'}\n"
            msg += "\n"
        msg += "🔥 [題材池三線交會掃描]\n"
        buy_obs, keep_obs, leave_obs = [], [], []
        for t, info in THEME_POOL.items():
            res = get_full_ma_status(t)
            if res:
                curr, m5, m10, m20 = res
                min_ma = min([m5, m10, m20])
                if min_ma > 0:
                    spread = (max([m5, m10, m20]) - min_ma) / min_ma * 100
                    if spread <= 3.0: buy_obs.append(info[0])
                    elif spread >= 6.0 and m5 < m20 and curr < m20: leave_obs.append(info[0])
                    else: keep_obs.append(info[0])
        msg += f"🎯 買入觀察期: {', '.join(buy_obs)}\n👀 持續觀察中: {', '.join(keep_obs)}\n🗑️ 離開視野中: {', '.join(leave_obs)}\n"

    try:
        requests.post("https://api.line.me/v2/bot/message/push", headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, json={"to": user_id, "messages": [{"type": "text", "text": msg}]})
    except:
        pass

if __name__ == "__main__":
    main()
