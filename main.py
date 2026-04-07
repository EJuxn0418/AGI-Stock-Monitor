import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 核心數據配置
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2], '00941.TW': ['00941', 2]}
SHORT_PORTFOLIO = {'1528.TW': ['恩德', 5, 10, 1]}
WATCH_LIST = {'2344.TW': '華邦電', '3481.TW': '群創', '2408.TW': '南亞科'}
THEME_POOL = {'2313.TW': ['華通', '低軌衛星'], '1528.TW': ['恩德', 'AI/機器人']}

# --- 功能模組：永豐期貨爬蟲 (強化容錯版) ---
def get_spf_reports():
    url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
    headers = {'User-Agent': 'Mozilla/5.0'}
    fields = []
    try:
        print(f"[*] 開始巡邏永豐研究室: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('tr') or soup.select('li')
        
        # 取得今天日期（處理 04/07 與 4/7 兩種可能）
        now_tw = datetime.now(timezone(timedelta(hours=8)))
        d1 = now_tw.strftime('%Y/%m/%d')
        d2 = f"{now_tw.year}/{now_tw.month}/{now_tw.day}"
        
        for item in items:
            text = item.get_text(strip=True)
            link_tag = item.find('a')
            if link_tag and (d1 in text or d2 in text):
                title = link_tag.get('title') or link_tag.get_text(strip=True)
                href = link_tag.get('href')
                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                fields.append({"name": f"📰 {title}", "value": f"[點此閱讀報告]({full_url})", "inline": False})
        
        print(f"[+] 找到 {len(fields)} 則今日報告")
        return fields
    except Exception as e:
        print(f"[!] 爬蟲發生錯誤: {e}")
        return []

# --- 數據抓取與 Discord 發送 ---
def get_stock_data(ticker):
    try:
        hist = yf.download(ticker, period="60d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].iloc[-1]) if not live.empty else float(hist['Close'].iloc[-1])
        return {"price": curr, "m5": float(hist['Close'].rolling(5).mean().iloc[-1]), "m20": float(hist['Close'].rolling(20).mean().iloc[-1])}
    except: return None

def send_embed(webhook_url, title, fields, color=0x2ecc71, desc=""):
    if not webhook_url: 
        print(f"[!] 警告: Webhook URL 為空，無法發送 '{title}'")
        return
    payload = {"embeds": [{"title": title, "description": desc, "color": color, "fields": fields, "footer": {"text": "AGI 投資戰情室"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    res = requests.post(webhook_url, json=payload)
    print(f"[>] 發送 '{title}' 至 Discord, 狀態碼: {res.status_code}")

def main():
    # 讀取 Webhooks
    webhook_keys = ['WH_MORNING_REPORT', 'WH_AFTERNOON_REPORT', 'WH_PORTFOLIO_SUMMARY', 'WH_LONG_HOLDING', 'WH_SHORT_HOLDING', 'WH_MACRO_WATCH', 'WH_KEY_WATCH', 'WH_SYS_LOG', 'WH_TRADE_LOG', 'WH_SPF_REPORT']
    wh = {k: os.environ.get(k) for k in webhook_keys}
    
    now = datetime.now(timezone(timedelta(hours=8)))
    print(f"[*] AGI 管家啟動，目前台北時間: {now.strftime('%Y/%m/%d %H:%M:%S')}")

    # --- 邏輯分流 ---
    # 早盤 (09:30)
    if now.hour == 9:
        print("[*] 執行早盤邏輯...")
        # ... (省略重複的早盤代碼) ...
    
    # 午盤 (13:00)
    elif 12 <= now.hour <= 14:
        print("[*] 執行午盤邏輯...")
        # ... (省略重複的午盤代碼) ...

    # 盤後與測試 (15:00 以後，包含現在)
    else:
        print("[*] 執行盤後/測試邏輯...")
        spf_fields = get_spf_reports()
        if spf_fields:
            send_embed(wh['WH_SPF_REPORT'], "📉 永豐期貨盤後研究報告", spf_fields, 0x9b59b6)
        
        # 強制發送一個系統日誌，讓你知道程式有跑完
        test_fields = [{"name": "執行時間", "value": f"`{now.strftime('%H:%M:%S')}`", "inline": True}]
        send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌：手動測試成功", test_fields, 0x95a5a6)

if __name__ == "__main__":
    main()
