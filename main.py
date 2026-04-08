import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 核心數據配置 (v6.7 新增：持有均價)
# 格式說明：
# 長線 = '代號': ['名稱', 張數, 買入均價]
# 短線 = '代號': ['名稱', 警告線MA, 撤退線MA, 張數, 買入均價]
# ---------------------------------------------------
LONG_PORTFOLIO = {
    '0050.TW': ['0050', 2, 70.25],    # ⚠️ 請將 0.0 改成你的 0050 均價
    '00941.TW': ['00941', 2, 16.74]   # ⚠️ 請將 0.0 改成你的 00941 均價
}

SHORT_PORTFOLIO = {
    '1528.TW': ['恩德', 5, 10, 1, 26.90],     # ⚠️ 請將 0.0 改成你的恩德均價
    '3481.TW': ['群創', 10, 10, 1, 25.95]   # 群創已更新為 25.95，防守線改為 10MA/20MA
}

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
    
    # 1. 早盤區塊
    if now.hour == 9 or is_test_mode:
        m_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            if d and d['price'] >= d['m5']: 
                m_fields.append({"name": f"🚀 {info[1]} | {info[0]}", "value": f"現價: `{d['price']:.2f}`", "inline": True})
        if not m_fields: m_fields.append({"name": "狀態", "value": "今日無標的站上 5MA"})
        send_embed(wh['WH_MORNING_REPORT'], "🌅 早盤強勢題材掃描", m_fields, 0x3498db)

    # 2. 午盤/持倉區塊
    if (12 <= now.hour <= 14) or is_test_mode:
        # 長線持倉 (含損益計算)
        l_fields = []
        for t, info in LONG_PORTFOLIO.items():
            d = get_stock_data(t, 120)
            if d: 
                cost = info[2]
                roi_str = ""
                if cost > 0:
                    roi = ((d['price'] - cost) / cost) * 100
                    roi_str = f" 🟢 +{roi:.1f}%" if roi >= 0 else f" 🔴 {roi:.1f}%"
                
                adv = "🟢 安全" if d['price'] > d['m20'] else "🟡 月線防禦"
                l_fields.append({
                    "name": f"🏛️ {info[0]} ({info[1]}張)", 
                    "value": f"現價: `{d['price']:.2f}`{roi_str}\n均價: `{cost}` | 月線: {d['m20']:.2f}\n狀態: {adv}", 
                    "inline": True
                })
        send_embed(wh['WH_LONG_HOLDING'], "🏢 長線左側部位狀態", l_fields, 0x27ae60)

        # 短線持倉 (含損益計算與動態均線防守)
        s_fields = []
        s_color = 0x2ecc71
        for t, info in SHORT_PORTFOLIO.items():
            d = get_stock_data(t)
            if d:
                m1_val, m2_val = d[f'm{info[1]}'], d[f'm{info[2]}']
                st = "✅ 站穩" if d['price'] >= m1_val else (f"⚠️ 破{info[1]}MA" if d['price'] >= m2_val else f"🚫 破{info[2]}MA")
                if d['price'] < m1_val: s_color = 0xf1c40f
                if d['price'] < m2_val: s_color = 0xe74c3c
                
                cost = info[4]
                roi_str = ""
                if cost > 0:
                    roi = ((d['price'] - cost) / cost) * 100
                    roi_str = f" 🟢 +{roi:.1f}%" if roi >= 0 else f" 🔴 {roi:.1f}%"

                s_fields.append({
                    "name": f"⚔️ {info[0]} ({info[3]}張)", 
                    "value": f"現價: `{d['price']:.2f}`{roi_str}\n均價: `{cost}` | 防守: {info[1]}MA\n狀態: **{st}**", 
                    "inline": True
                })
        send_embed(wh['WH_SHORT_HOLDING'], "⚡ 短線右側部位狀態", s_fields, s_color)

        send_embed(wh['WH_PORTFOLIO_SUMMARY'], "📊 當前持倉彙整總表", l_fields + s_fields, 0x34495e)
        send_embed(wh['WH_AFTERNOON_REPORT'], "📋 午盤重點簡報", l_fields + s_fields, s_color)

        # 觀察池
        k_fields = []
        for t, name in WATCH_LIST.items():
            d = get_stock_data(t)
            if d: k_fields.append({"name": f"🔸 {name}", "value": f"`{d['price']:.2f}` (5MA: {d['m5']:.2f})", "inline": True})
        send_embed(wh['WH_KEY_WATCH'], "👀 重點觀察池追蹤", k_fields, 0xe67e22)

        mac_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            if d: mac_fields.append({"name": f"🌐 {info[0]}", "value": f"`{d['price']:.2f}`", "inline": True})
        send_embed(wh['WH_MACRO_WATCH'], "🌍 宏觀題材池快訊", mac_fields, 0x1abc9c)

        # 留痕
        log_fields = [
            {"name": "系統升級", "value": "v6.7 導入持倉均價與即時損益 (ROI) 計算功能"},
            {"name": "建倉紀錄", "value": "3481 群創 今日以 25.95 買入 1 張，移入短線監控。"}
        ]
        send_embed(wh['WH_TRADE_LOG'], "✍️ 系統操作留痕", log_fields, 0x7f8c8d)

    # 3. 永豐期貨盤後
    if now.hour >= 15 or is_test_mode:
        spf = get_spf_reports()
        if spf:
            send_embed(wh['WH_SPF_REPORT'], "📉 永豐期貨盤後報告", spf, 0x9b59b6)

    send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", [{"name": "執行狀態", "value": f"完成時間: {now.strftime('%H:%M:%S')}"}], 0x95a5a6)

if __name__ == "__main__":
    main()
