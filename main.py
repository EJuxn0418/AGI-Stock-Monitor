import yfinance as yf
import pandas as pd
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# 核心數據配置
# ---------------------------------------------------
LONG_PORTFOLIO = {'0050.TW': ['0050', 2, 70.25], '00941.TW': ['00941', 2, 16.74]}
SHORT_PORTFOLIO = {
    '1528.TW': ['恩德', 5, 10, 1, 26.90],
    '3481.TW': ['群創', 10, 20, 1, 25.95]
}

THEME_POOL = {
    '2330.TW': ['台積電', 'AI/半導體'], '2317.TW': ['鴻海', 'AI/半導體'],
    '1513.TW': ['華城', '重電/綠電'], '1503.TW': ['士電', '重電'],
    '3491.TWO': ['昇達科', '低軌衛星'], '2313.TW': ['華通', '低軌衛星'],
    '6285.TW': ['啟碁', '低軌衛星'], '9958.TW': ['世紀鋼', '綠電'],
    '2881.TW': ['富邦金', '金融'], '2882.TW': ['國泰金', '金融'],
    '1504.TW': ['東元', '電機機械'], '1528.TW': ['恩德', '電機機械'],
    '2382.TW': ['廣達', 'AI伺服器'], '3231.TW': ['緯創', 'AI伺服器']
}

WATCH_LIST = {'2344.TW': '華邦電', '2408.TW': '南亞科', '2646.TW': '星宇'}

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
    
    # 絕對時間閘門 (Strict Time-Gating)
    is_test_mode = now.hour >= 20  
    is_morning = 9 <= now.hour < 12      # 09:00 - 11:59
    is_noon = 12 <= now.hour < 15        # 12:00 - 14:59
    is_afternoon = 15 <= now.hour < 20   # 15:00 - 19:59

    action_record = []

    # ==========================================
    # 區塊 1: 早盤 (09:30 觸發)
    # ==========================================
    if is_morning or is_test_mode:
        m_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            strat = check_strategy(d)
            if strat and strat['is_breakout']:
                m_fields.append({"name": f"🔥 壓縮突破 | {info[0]} ({info[1]})", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`", "inline": True})
        desc = "系統偵測昨日均線高度糾結，今日開盤帶量站上 5MA 之強勢股："
        send_embed(wh['WH_MORNING_REPORT'], "🌅 早盤策略雷達：起漲點掃描", m_fields if m_fields else [{"name":"狀態","value":"今日尚無標的符合壓縮突破條件"}], 0x3498db, desc)
        action_record.append("發送早盤策略雷達")

    # ==========================================
    # 區塊 2: 午盤 (13:00 觸發)
    # ==========================================
    if is_noon or is_test_mode:
        # 長線持倉
        l_fields = []
        for t, info in LONG_PORTFOLIO.items():
            d = get_stock_data(t, 120)
            if d:
                cost = info[2]
                roi_str = f" {'🟢' if d['price'] >= cost else '🔴'} {((d['price']-cost)/cost*100):.1f}%" if cost > 0 else ""
                l_fields.append({"name": f"🏛️ {info[0]} ({info[1]}張)", "value": f"價: `{d['price']:.2f}`{roi_str}\n狀態: {'🟢 安全' if d['price']>d['m20'] else '🟡 月線防禦'}", "inline": True})
        send_embed(wh['WH_LONG_HOLDING'], "🏢 長線左側部位狀態", l_fields, 0x27ae60)

        # 短線持倉
        s_fields = []
        s_color = 0x2ecc71
        for t, info in SHORT_PORTFOLIO.items():
            d = get_stock_data(t)
            if d:
                cost = info[4]
                roi_str = f" {'🟢' if d['price'] >= cost else '🔴'} {((d['price']-cost)/cost*100):.1f}%" if cost > 0 else ""
                st = "✅ 站穩" if d['price'] >= d[f'm{info[1]}'] else "🚫 破線"
                if d['price'] < d[f'm{info[1]}']: s_color = 0xf1c40f
                if d['price'] < d[f'm{info[2]}']: s_color = 0xe74c3c
                s_fields.append({"name": f"⚔️ {info[0]} ({info[3]}張)", "value": f"價: `{d['price']:.2f}`{roi_str}\n均線: {info[1]}MA | 狀態: {st}", "inline": True})
        send_embed(wh['WH_SHORT_HOLDING'], "⚡ 短線右側部位狀態", s_fields, s_color)

        # 總表 與 午盤日報
        send_embed(wh['WH_PORTFOLIO_SUMMARY'], "📊 當前持倉彙整總表", l_fields + s_fields, 0x34495e)
        send_embed(wh['WH_AFTERNOON_REPORT'], "📋 午盤重點簡報", l_fields + s_fields, s_color)

        # 重點觀察池
        k_fields = []
        for t, name in WATCH_LIST.items():
            d = get_stock_data(t)
            if d: k_fields.append({"name": f"🔸 {name}", "value": f"`{d['price']:.2f}`", "inline": True})
        if k_fields: 
            send_embed(wh['WH_KEY_WATCH'], "👀 重點觀察池追蹤", k_fields, 0xe67e22)
            
        action_record.append("發送午盤總表與持倉狀態")

    # ==========================================
    # 區塊 3: 盤後結算 (15:00 觸發)
    # ==========================================
    if is_afternoon or is_test_mode:
        # 宏觀觀察池 (移至 15:00 區間)
        mac_fields = []
        for t, info in THEME_POOL.items():
            d = get_stock_data(t)
            strat = check_strategy(d)
            if strat and strat['is_compressed']:
                mac_fields.append({"name": f"🌐 {info[1]} | {info[0]}", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%` (糾結中)", "inline": True})
        send_embed(wh['WH_MACRO_WATCH'], "🌍 宏觀題材池：盤後壓縮掃描", mac_fields if mac_fields else [{"name":"狀態","value":"目前題材池標的均線尚無高度壓縮型態"}], 0x1abc9c, "三線糾結標的代表籌碼沉澱，隨時可能表態突破。")

        # 永豐期貨報告
        spf = get_spf_reports()
        if spf: send_embed(wh['WH_SPF_REPORT'], "📉 永豐期貨盤後報告", spf, 0x9b59b6)
        
        action_record.append("發送盤後宏觀壓縮與期貨報告")

    # ==========================================
    # 區塊 4: 每次執行必觸發 (日誌與留痕)
    # ==========================================
    if action_record or is_test_mode:
        mode_str = "全局測試模式" if is_test_mode else "排程觸發"
        log_fields = [
            {"name": "系統修復與優化", "value": "v7.3 導入嚴格時間閘門，解決午盤日報延遲誤發問題。"},
            {"name": "本次執行任務", "value": "\n".join(action_record) if action_record else "無具體任務"}
        ]
        send_embed(wh['WH_TRADE_LOG'], "✍️ 系統操作留痕", log_fields, 0x7f8c8d)
        
        sys_status = [{"name": "啟動時間", "value": f"{now.strftime('%Y/%m/%d %H:%M:%S')}"},
                      {"name": "運行模式", "value": mode_str}]
        send_embed(wh['WH_SYS_LOG'], "⚙️ 系統日誌", sys_status, 0x95a5a6)

if __name__ == "__main__":
    main()
