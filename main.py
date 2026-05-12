import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 核心數據配置 (v8.1 新增建準持倉)
# ---------------------------------------------------
# 長線底倉
LONG_PORTFOLIO = {
    '00941.TW': ['00941', 2, 16.74]
} 
# 短線右側部位：建準 149.0 進場 1 張，設定 5MA 為首要防守，10MA 為最後撤退線
SHORT_PORTFOLIO = {
    '2421.TW': ['建準', 5, 10, 1, 149.0]
} 

# Computex 戰備名單
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], 
    '2382.TW': ['廣達', 'AI伺服器'], 
    '3711.TW': ['日月光', '先進封裝'], 
    '3131.TWO': ['弘塑', '封測設備'],
    '3450.TW': ['聯鈞', 'CPO矽光子'],    
    '3363.TW': ['上詮', 'CPO矽光子'],    
    '2308.TW': ['台達電', 'AI電源/散熱'], 
    '3324.TW': ['雙鴻', '散熱(水冷)'], 
    '3017.TW': ['奇鋐', '散熱(3D VC)'],    
    '2421.TW': ['建準', '散熱(風扇)'],    
    '3491.TWO': ['昇達科', '低軌衛星'], 
    '6285.TW': ['啟碁', '低軌衛星'],
    '1815.TW': ['富喬', '高階玻纖布'], 
    '5340.TWO': ['建榮', '高階玻纖布']
}

WATCH_LIST = {
    '0050.TW': '元大台灣50', 
    '2317.TW': '鴻海', 
    '2454.TW': '聯發科',
    '2344.TW': '華邦電', 
    '2408.TW': '南亞科', 
    '2646.TW': '星宇', 
    '1528.TW':'恩德', 
    '3037.TW': '欣興', 
    '3481.TW':'群創', 
    
}

# --- 功能模組 ---
def check_strategy(data):
    if not data: return None
    ma_list = [data['m5'], data['m10'], data['m20']]
    comp_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_compressed = comp_ratio <= 0.03
    is_breakout = data['price'] > data['m5'] and is_compressed
    return {"ratio": comp_ratio * 100, "is_compressed": is_compressed, "is_breakout": is_breakout}

def get_stock_data(ticker, days=60):
    try:
        hist = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].values[-1]) if not live.empty else float(hist['Close'].values[-1])
        return {
            "price": curr, 
            "m5": float(hist['Close'].rolling(5).mean().values[-1]),
            "m10": float(hist['Close'].rolling(10).mean().values[-1]),
            "m20": float(hist['Close'].rolling(20).mean().values[-1]),
            "m60": float(hist['Close'].rolling(60).mean().values[-1])
        }
    except: return None

def get_spf_reports():
    url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
    headers = {'User-Agent': 'Mozilla/5.0'}
    fields = []
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('tr') or soup.select('li')
        now_tw = datetime.now(timezone(timedelta(hours=8)))
        d1, d2 = now_tw.strftime('%Y/%m/%d'), f"{now_tw.year}/{now_tw.month}/{now_tw.day}"
        for item in items:
            link = item.find('a')
            if link and (d1 in item.get_text() or d2 in item.get_text()):
                href = link.get('href')
                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                fields.append({"name": f"📰 {link.get('title') or link.get_text(strip=True)}", "value": f"[閱讀報告]({full_url})"})
        return fields
    except: return []

def send_embed(webhook_url, title, fields, color=0x2ecc71, desc=""):
    if not webhook_url or not fields: return
    payload = {"embeds": [{"title": title, "description": desc, "color": color, "fields": fields, "footer": {"text": "AGI 投資戰情室"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    requests.post(webhook_url, json=payload)

def main():
    wh = {k: os.environ.get(k) for k in ['WH_MORNING_REPORT', 'WH_AFTERNOON_REPORT', 'WH_PORTFOLIO_SUMMARY', 'WH_LONG_HOLDING', 'WH_SHORT_HOLDING', 'WH_MACRO_WATCH', 'WH_KEY_WATCH', 'WH_SYS_LOG', 'WH_TRADE_LOG', 'WH_SPF_REPORT']}
    now = datetime.now(timezone(timedelta(hours=8)))
    
    is_test_mode = now.hour >= 20  
    is_morning = 9 <= now.hour < 12
    is_noon = 12 <= now.hour < 15
    is_afternoon = 15 <= now.hour < 20

    action_record = []

    if is_morning or is_test_mode:
        m_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            strat = check_strategy(d)
            if strat and strat['is_breakout']:
                m_fields.append({"name": f"🔥 壓縮突破 | {info[0]} ({info[1]})", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`", "inline": True})
        send_embed(wh['WH_MORNING_REPORT'], "🌅 早盤策略雷達", m_fields if m_fields else [{"name":"狀態","value":"今日無符合標的"}], 0x3498db)
        action_record.append("發送早盤策略雷達")

    if is_noon or is_test_mode:
        l_fields = []
        for t, info in LONG_PORTFOLIO.items():
            d = get_stock_data(t, 120)
            if d:
                cost = info[2]
                roi_str = f" {'🟢' if d['price'] >= cost else '🔴'} {((d['price']-cost)/cost*100):.1f}%" if cost > 0 else ""
                l_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"價: `{d['price']:.2f}`{roi_str}", "inline": True})
        send_embed(wh['WH_LONG_HOLDING'], "🏢 長線部位狀態", l_fields, 0x27ae60)

        s_fields = []
        for t, info in SHORT_PORTFOLIO.items():
            d = get_stock_data(t)
            if d:
                cost = info[4]
                roi_str = f" {'🟢' if d['price'] >= cost else '🔴'} {((d['price']-cost)/cost*100):.1f}%" if cost > 0 else ""
                st = "✅ 站穩" if d['price'] >= d[f'm{info[1]}'] else "🚫 破線"
                s_fields.append({"name": f"⚔️ {info[0]} ({info[3]}張)", "value": f"價: `{d['price']:.2f}`{roi_str}\n均線: {info[1]}MA | 狀態: {st}", "inline": True})
        send_embed(wh['WH_SHORT_HOLDING'], "⚡ 短線部位狀態", s_fields, 0x2ecc71)

        send_embed(wh['WH_PORTFOLIO_SUMMARY'], "📊 當前持倉彙整總表", l_fields + s_fields, 0x34495e)
        
        k_fields = []
        for t, name in WATCH_LIST.items():
            d = get_stock_data(t)
            if d: k_fields.append({"name": f"🔸 {name}", "value": f"`{d['price']:.2f}`", "inline": True})
        send_embed(wh['WH_KEY_WATCH'], "👀 重點觀察池", k_fields, 0xe67e22)
        action_record.append("發送持倉狀態更新 (建準進場)")

    if is_afternoon or is_test_mode:
        mac_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            strat = check_strategy(d)
            if strat and strat['is_compressed']:
                mac_fields.append({"name": f"🌐 {info[1]} | {info[0]}", "value": f"現價: `{d['price']:.2f}`", "inline": True})
        send_embed(wh['WH_MACRO_WATCH'], "🌍 宏觀題材壓縮掃描", mac_fields if mac_fields else [{"name":"狀態","value":"目前無高度壓縮標的"}], 0x1abc9c)
        
        spf = get_spf_reports()
        if spf: send_embed(wh['WH_SPF_REPORT'], "📉 永豐期貨盤後", spf, 0x9b59b6)

    if action_record or is_test_mode:
        log_fields = [{"name": "交易紀錄", "value": "2421 建準 149.0 進場 1 張。"}]
        send_embed(wh['WH_TRADE_LOG'], "✍️ 系統操作留痕", log_fields, 0x7f8c8d)
        send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "執行時間", "value": f"{now.strftime('%H:%M:%S')}"}], 0x95a5a6)

if __name__ == "__main__":
    main()
