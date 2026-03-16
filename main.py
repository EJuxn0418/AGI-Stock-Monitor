import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1A. 長線左側部位 (Long-Term) - 金字塔建倉邏輯
# ---------------------------------------------------
LONG_PORTFOLIO = {
    '0050.TW': '0050',   
    '00941.TW': '00941'
}

# ---------------------------------------------------
# 1B. 短線右側部位 (Short-Term) - 嚴格均線停損
# ---------------------------------------------------
SHORT_PORTFOLIO = {
    '2344.TW': ['華邦電', 5]  # 維持 5MA 防守，跌破警示
}

# ---------------------------------------------------
# 2. 重點觀察池 (Watch List) - 尋找右側突破點
# ---------------------------------------------------
WATCH_LIST = {
    '3481.TW': '群創',     
    '2646.TW': '星宇航空', 
    '2408.TW': '南亞科',   
    '4967.TW': '十銓',     
    '3374.TWO': '精材',    
    '2449.TW': '京元電子', 
    '2354.TW': '鴻準'      
}

# ---------------------------------------------------
# 3. 參考目標價 (Target Prices)
# ---------------------------------------------------
TARGET_PRICES = {
    '0050.TW': 200.0, '00941.TW': 25.0, '2646.TW': 25.0, '2344.TW': 150.0,  
    '3481.TW': 32.0,  '2408.TW': 85.0,  '4967.TW': 150.0, '3374.TWO': 250.0,
    '2449.TW': 130.0, '2354.TW': 90.0
}

# ---------------------------------------------------
# 4. 題材掃描池 (Themes)
# ---------------------------------------------------
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '3231.TW': ['緯創', 'AI/半導體'],   '2454.TW': ['聯發科', 'AI/半導體'],
    '2376.TW': ['技嘉', 'AI/伺服器'],   '3017.TW': ['奇鋐', 'AI/散熱'],     
    '1513.TW': ['中興電', '儲能/重電'], '1503.TW': ['士電', '儲能/重電'],
    '9958.TW': ['世紀鋼', '永續/綠能'], '2891.TW': ['中信金', '金融'],       
    '2881.TW': ['富邦金', '金融'],     '2603.TW': ['長榮', '航運'],         
    '2618.TW': ['長榮航', '航運']       
}

# --- 核心功能：短線與即時狀態 ---
def get_realtime_status(ticker, ma_days):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        ma_value = float(hist_df['Close'].rolling(window=ma_days).mean().iloc[-1])
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(hist_df['Close'].iloc[-1])
        return curr, ma_value, curr - ma_value
    except:
        return None

def get_full_ma_status(ticker):
    try:
        hist_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        close = hist_df['Close']
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(close.iloc[-1])
        return curr, float(close.rolling(5).mean().iloc[-1]), float(close.rolling(10).mean().iloc[-1]), float(close.rolling(20).mean().iloc[-1])
    except:
        return None

# --- 新功能：長線金字塔狀態 (抓取1年資料計算季線/半年線) ---
def get_long_term_status(ticker):
    try:
        hist_df = yf.download(ticker, period="1y", interval="1d", progress=False)
        live_df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist_df.empty: return None
        close = hist_df['Close']
        curr = float(live_df['Close'].iloc[-1]) if not live_df.empty else float(close.iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1])
        ma120 = float(close.rolling(120).mean().iloc[-1])
        return curr, ma20, ma60, ma120
    except:
        return None

def main():
    token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('LINE_USER_ID')
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    
    # --- 早上 09:30：早盤動能快篩 ---
    if now.hour < 12: 
        msg = f"\n🌅 宜駿的早盤題材推薦 ({now.strftime('%m/%d %H:%M')})\n"
        msg += "🎯 標準：強勢站上 5MA (即時)\n━━━━━━━━━━━━━━━\n"
        categorized_results = {}
        for t, info in THEME_POOL.items():
            name, category = info
            res = get_realtime_status(t, 5)
            if res and res[2] >= 0:
                if category not in categorized_results: categorized_results[category] = []
                categorized_results[category].append(f"{name} (+{res[2]:.2f})")
        if categorized_results:
            for cat, stocks in categorized_results.items(): msg += f"【{cat}】\n   🚀 {', '.join(stocks)}\n"
        else:
            msg += "目前題材池中尚無標的符合篩選標準。"
    
    # --- 下午 13:00：全方位綜合報告 ---
    else: 
        msg = f"\n📊 宜駿的 AGI 綜合報告 ({now.strftime('%H:%M')})\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        # 1A. 長線金字塔部位
        msg += "🏛️ [長線左側：金字塔建倉區]\n"
        for t, name in LONG_PORTFOLIO.items():
            res = get_long_term_status(t)
            if res:
                curr, ma20, ma60, ma120 = res
                msg += f"【{name}】 現價: {curr:.2f}\n"
                
                # 金字塔策略建議邏輯
                if curr > ma20:
                    advice = "🟢 抱緊現有部位，不宜追高加碼"
                elif curr > ma60:
                    advice = "🟡 溫和回檔 (跌破月線)，可規劃【塔尖10%】試單"
                elif curr > ma120:
                    advice = "🟠 價值浮現 (跌破季線)，建議啟動【中段20%】承接"
                else:
                    advice = "🔴 長線超跌 (跌破半年線)，啟動【底部40%】大舉佈局"
                    
                msg += f" 💡 策略: {advice}\n"
                msg += f" 📉 距離季線({ma60:.2f}): {((curr-ma60)/ma60*100):.1f}%\n\n"

        # 1B. 短線動能部位
        msg += "⚔️ [短線右側：嚴格停損區]\n"
        for t, info in SHORT_PORTFOLIO.items():
            res = get_realtime_status(t, info[1])
            if res:
                curr, ma, diff = res
                status = "✅ 站上" if diff >= 0 else "⚠️ 跌破請注意"
                msg += f"【{info[0]}】 現價: {curr:.2f}\n"
                if t in TARGET_PRICES:
                    target = TARGET_PRICES[t]
                    msg += f" 🎯 目標: {target} (距 {((target-curr)/curr*100):.1f}%)\n"
                msg += f" 🔹 {info[1]}MA 防守線: {ma:.2f}\n"
                msg += f" 🔹 狀態: {status} ({'+' if diff>=0 else ''}{diff:.2f})\n\n"
        
        # 2. 重點觀察池
        if WATCH_LIST:
            msg += "👀 [重點觀察池追蹤 (右側突破準備)]\n"
            for t, name in WATCH_LIST.items():
                res = get_full_ma_status(t)
                if res:
                    curr, ma5, ma10, ma20 = res
                    msg += f"🔸 {name} ({curr:.2f})\n"
                    if t in TARGET_PRICES:
                        msg += f"   🎯 空間: {((TARGET_PRICES[t]-curr)/curr*100):.1f}%\n"
                    msg += f"   5MA: {ma5:.2f}{'🔺'if curr>=ma5 else'🔻'} | 10MA: {ma10:.2f}{'🔺'if curr>=ma10 else'🔻'} | 20MA: {ma20:.2f}{'🔺'if curr>=ma20 else'🔻'}\n"
            msg += "\n"

        # 3. 農場系統
        msg += "🔥 [題材池三線交會掃描]\n"
        buy_obs, keep_obs, leave_obs = [], [], []
        for t, info in THEME_POOL.items():
            res = get_full_ma_status(t)
            if res:
                curr, ma5, ma10, ma20 = res
                spread = (max([ma5, ma10, ma20]) - min([ma5, ma10, ma20])) / min([ma5, ma10, ma20]) * 100
                if spread <= 3.0: buy_obs.append(info[0])
                elif spread >= 6.0 and ma5 < ma20 and curr < ma20: leave_obs.append(info[0])
                else: keep_obs.append(info[0])
        
        msg += f"🎯 買入觀察期: {', '.join(buy_obs) if buy_obs else '無'}\n"
        msg += f"👀 持續觀察中: {', '.join(keep_obs) if keep_obs else '無'}\n"
        msg += f"🗑️ 離開視野中: {', '.join(leave_obs) if leave_obs else '無'}\n"

    send_line_push(token, user_id, msg)

def send_line_push(token, user_id, text):
    requests.post("https://api.line.me/v2/bot/message/push", 
                  headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, 
                  json={"to": user_id, "messages": [{"type": "text", "text": text}]})

if __name__ == "__main__":
    main()
