import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 1. 核心數據配置 (保持最新)
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2], '00941.TW': ['00941', 2]}
SHORT_PORTFOLIO = {'1528.TW': ['恩德', 5, 10, 1]}
WATCH_LIST = {
    '2344.TW': '華邦電', '3481.TW': '群創', '2408.TW': '南亞科', 
    '2646.TW': '星宇航空', '3374.TWO': '精材', '3037.TW': '欣興'
}
THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '3491.TWO': ['昇達科', '低軌衛星'], '2313.TW': ['華通', '低軌衛星'],
    '2359.TW': ['所羅門', 'AI/機器人'], '1528.TW': ['恩德', 'AI/機器人']
}

# --- 功能模組：永豐期貨爬蟲 ---
def get_spf_reports():
    url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
    headers = {'User-Agent': 'Mozilla/5.0'}
    fields = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        # 抓取列表項目（根據永豐網頁結構調整）
        items = soup.select('.news-list li') or soup.select('tr')
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime('%Y/%m/%d')
        
        count = 0
        for item in items:
            text = item.get_text(strip=True)
            link_tag = item.find('a')
            if link_tag and today_str in text:
                title = link_tag.get('title') or link_tag.get_text(strip=True)
                href = link_tag.get('href')
                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                fields.append({"name": f"📰 {title}", "value": f"[點此閱讀報告]({full_url})", "inline": False})
                count += 1
                if count >= 3: break # 僅取前三則最新
        return fields
    except: return []

# --- 數據抓取與 Discord 發送 (維持 v6.1 優化排版) ---
def get_stock_data(ticker, days=60):
    try:
        hist = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        if hist.empty: return None
        curr = float(live['Close'].iloc[-1]) if not live.empty else float(hist['Close'].iloc[-1])
        return {
            "price": curr, "m5": float(hist['Close'].rolling(5).mean().iloc[-1]),
            "m10": float(hist['Close'].rolling(10).mean().iloc[-1]),
            "m20": float(hist['Close'].rolling(20).mean().iloc[-1]),
            "m60": float(hist['Close'].rolling(60).mean().iloc[-1])
        }
    except: return None

def send_embed(webhook_url, title, fields, color=0x2ecc71, description=""):
    if not webhook_url: return
    payload = {"embeds": [{"title": title, "description": description, "color": color, "fields": fields, "footer": {"text": "AGI 投資戰情室"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    requests.post(webhook_url, json=payload)

def main():
    wh = {k: os.environ.get(k) for k in ['WH_MORNING_REPORT', 'WH_AFTERNOON_REPORT', 'WH_PORTFOLIO_SUMMARY', 'WH_LONG_HOLDING', 'WH_SHORT_HOLDING', 'WH_MACRO_WATCH', 'WH_KEY_WATCH', 'WH_SYS_LOG', 'WH_TRADE_LOG', 'WH_SPF_REPORT']}
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)

    # --- 早盤 (09:30) ---
    if now.hour == 9:
        morning_fields = []
        for t, info in THEME_POOL.items():
            data = get_stock_data(t)
            if data and data['price'] >= data['m5']:
                morning_fields.append({"name": f"🚀 {info[1]} | {info[0]}", "value": f"現價: `{data['price']:.2f}`", "inline": True})
        send_embed(wh['WH_MORNING_REPORT'], "🌅 今日強勢題材掃描", morning_fields, 0x3498db)

    # --- 午盤 (13:00) ---
    elif 12 <= now.hour <= 14:
        long_fields = []
        for t, info in LONG_PORTFOLIO.items():
            data = get_stock_data(t, 120)
            if data: long_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"現價: `{data['price']:.2f}`\n月線: {data['m20']:.2f} | 季線: {data['m60']:.2f}", "inline": True})
        send_embed(wh['WH_LONG_HOLDING'], "🏢 長線左側部位狀態", long_fields, 0x27ae60)

        short_fields = []
        status_color = 0x2ecc71
        for t, info in SHORT_PORTFOLIO.items():
            data = get_stock_data(t)
            if data:
                status = "✅ 站穩" if data['price'] >= data['m5'] else ("⚠️ 警訊(破5MA)" if data['price'] >= data['m10'] else "🚫 撤退(破10MA)")
                if data['price'] < data['m5']: status_color = 0xf1c40f
                if data['price'] < data['m10']: status_color = 0xe74c3c
                short_fields.append({"name": f"⚔️ {info[0]} ({info[3]}張)", "value": f"現價: `{data['price']:.2f}`\n5MA: {data['m5']:.2f} | 10MA: {data['m10']:.2f}\n狀態: **{status}**", "inline": True})
        send_embed(wh['WH_SHORT_HOLDING'], "⚡ 短線右側部位狀態", short_fields, status_color)
        send_embed(wh['WH_AFTERNOON_REPORT'], "📋 今日重點簡報", long_fields + short_fields, status_color)

        key_fields = []
        for t, name in WATCH_LIST.items():
            data = get_stock_data(t)
            if data: key_fields.append({"name": f"🔸 {name}", "value": f"現價: `{data['price']:.2f}`", "inline": True})
        send_embed(wh['WH_KEY_WATCH'], "👀 重點觀察池追蹤", key_fields, 0xe67e22)

    # --- 盤後報告 (15:00) ---
    elif now.hour >= 15:
        spf_fields = get_spf_reports()
        if spf_fields:
            send_embed(wh['WH_SPF_REPORT'], "📉 永豐期貨盤後研究報告", spf_fields, 0x9b59b6, "今日最新發佈之研究資訊：")
        else:
            send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "爬蟲狀態", "value": "今日尚未偵測到永豐新報告"}], 0x95a5a6)

    send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "時間", "value": f"{now.strftime('%H:%M')} 執行成功"}], 0x95a5a6)

if __name__ == "__main__":
    main()
