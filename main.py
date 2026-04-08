import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 核心數據配置 (更新：買入群創 1 張 @ 25.95)
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2], '00941.TW': ['00941', 2]}

# 群創加入短線右側，預設開啟 5MA / 10MA 雙重防線
SHORT_PORTFOLIO = {
    '1528.TW': ['恩德', 5, 10, 1],
    '3481.TW': ['群創', 5, 10, 1]  
}

# 移出 3481 群創
WATCH_LIST = {
    '2344.TW': '華邦電', '2408.TW': '南亞科', 
    '2646.TW': '星宇航空', '3374.TWO': '精材', '3037.TW': '欣興'
}

THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '3491.TWO': ['昇達科', '低軌衛星'], '2313.TW': ['華通', '低軌衛星'],
    '2359.TW': ['所羅門', 'AI/機器人'], '1528.TW': ['恩德', 'AI/機器人']
}

# --- 工具模組 ---
def get_stock_data(ticker, days=60):
    try:
        hist = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].iloc[-1]) if not live.empty else float(hist['Close'].iloc[-1])
        return {
            "price": curr, "m5": float(hist['Close'].rolling(5).mean().iloc[-1]),
            "m10": float(hist['Close'].rolling(10).mean().iloc[-1]),
            "m20": float(hist['Close'].rolling(20).mean().iloc[-1]),
            "m60": float(hist['Close'].rolling(60).mean().iloc[-1])
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
    wh = {k: os.environ.get(k) for k in [
        'WH_MORNING_REPORT', 'WH_AFTERNOON_REPORT', 'WH_PORTFOLIO_SUMMARY', 
        'WH_LONG_HOLDING', 'WH_SHORT_HOLDING', 'WH_MACRO_WATCH', 
        'WH_KEY_WATCH', 'WH_SYS_LOG', 'WH_TRADE_LOG', 'WH_SPF_REPORT'
    ]}
    
    now = datetime.now(timezone(timedelta(hours=8)))
    is_test_mode = now.hour >= 20  
    
    # 1. 早盤區塊 (09:30 或 測試模式)
    if now.hour == 9 or is_test_mode:
        m_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            if d and d['price'] >= d['m5']: 
                m_fields.append({"name": f"🚀 {info[1]} | {info[0]}", "value": f"現價: `{d['price']:.2f}`", "inline": True})
        if not m_fields: m_fields.append({"name": "狀態", "value": "今日無標的站上 5MA"})
        send_embed(wh['WH_MORNING_REPORT'], "🌅 早盤強勢題材掃描", m_fields, 0x3498db)

    # 2. 午盤/持倉區塊 (13:00 或 測試模式)
    if (12 <= now.hour <= 14) or is_test_mode:
        l_fields = []
        for t, info in LONG_PORTFOLIO.items():
            d = get_stock_data(t, 120)
            if d: 
                adv = "🟢 安全" if d['price'] > d['m20'] else "🟡 月線防禦"
                l_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"價: `{d['price']:.2f}`\n月: {d['m20']:.2f} | 季: {d['m60']:.2f}\n{adv}", "inline": True})
        send_embed(wh['WH_LONG
