import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

THEME_POOL = {
    '2330.TW': ['台積電', '半導體核心', 'SEMICON'], 
    '3131.TWO': ['弘塑', '先進封裝設備', 'SEMICON'],
    '3583.TW': ['辛耘', '先進封裝設備', 'SEMICON'],
    '3324.TW': ['雙鴻', '散熱動能', 'COOLING'], 
    '3017.TW': ['奇鋐', '散熱動能', 'COOLING'],    
    '1503.TW': ['士電', '重電能源', 'POWER'],    
    '1514.TW': ['亞力', '重電能源', 'POWER'],
    '3450.TW': ['聯鈞', 'CPO矽光子', 'OPTICS'],    
    '3363.TW': ['上詮', 'CPO矽光子', 'OPTICS'],    
    '1815.TWO': ['富喬', '高階玻纖布', 'OPTICS'],
    '3491.TWO': ['昇達科', '低軌衛星龍頭', 'OPTICS'],
    '6806.TW': ['雲豹能源', '綠能環保龍頭', 'OTHER'],
    '2646.TW': ['星宇航空', '航空觀光動能', 'OTHER'],
    '1795.TW': ['美時', '生技癌症藥巨頭', 'OTHER'],
    '6472.TW': ['保瑞', '生技CDMO龍頭', 'OTHER'],
    '2548.TW': ['華固', '高段班營建資產', 'OTHER'],
    '1101.TW': ['台泥', '低基期儲能轉型', 'OTHER']
}

def check_strategy(data):
    if not data: return None
    try:
        ma_list = [data['m5'], data['m10'], data['m20']]
        min_ma = min(ma_list)
        if min_ma <= 0: return None
        comp_ratio = (max(ma_list) - min_ma) / min_ma
        is_compressed = comp_ratio <= 0.03
        is_breakout = data['price'] > data['m5'] and is_compressed
        return {"ratio": comp_ratio * 100, "is_compressed": is_compressed, "is_breakout": is_breakout}
    except: return None

def get_stock_data(ticker):
    try:
        hist = yf.download(ticker, period="60d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].values[-1]) if not live.empty else float(hist['Close'].values[-1])
        return {"price": curr, "m5": float(hist['Close'].rolling(5).mean().values[-1]), "m10": float(hist['Close'].rolling(10).mean().values[-1]), "m20": float(hist['Close'].rolling(20).mean().values[-1])}
    except: return None

def send_embed(webhook_url, title, fields, color=0x3498db):
    if not webhook_url or not fields: return
    payload = {"embeds": [{"title": title, "color": color, "fields": fields, "footer": {"text": "AGI 季度動能分流雷達 DV.01.005"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        print(f"雷達 Webhook 發送失敗: {e}")

def main():
    wh_map = {
        'SEMICON': os.environ.get('WH_RADAR_SEMICON'),
        'COOLING': os.environ.get('WH_RADAR_COOLING'),
        'POWER': os.environ.get('WH_RADAR_POWER'),
        'OPTICS': os.environ.get('WH_RADAR_OPTICS'),
        'OTHER': os.environ.get('WH_RADAR_OTHER')
    }
    
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    h = now_tw.hour
    is_morning = (h == 9)
    is_afternoon = (h == 15)
    is_manual_test = not is_morning and not is_afternoon # 👈 手動強制測試開關

    signals = {'SEMICON': [], 'COOLING': [], 'POWER': [], 'OPTICS': [], 'OTHER': []}

    for t, info in THEME_POOL.items():
        d = get_stock_data(t)
        strat = check_strategy(d)
        if not strat: continue
        category = info[2]
        
        if is_morning and strat['is_breakout']:
            signals[category].append({"name": f"🔥 壓縮突破 | {info[0]} ({info[1]})", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`", "inline": True})
        elif is_afternoon and strat['is_compressed']:
            signals[category].append({"name": f"🌐 籌碼蓄積 | {info[0]} ({info[1]})", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`", "inline": True})
        elif is_manual_test:
            # 👈 無視條件，強制寫入訊號以驗證門牌
            signals[category].append({"name": f"🧪 強制通訊驗證 | {info[0]}", "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`", "inline": True})

    for cat, fields in signals.items():
        if fields:
            if is_manual_test:
                title, color = f"🧪 [系統壓力測試] 頻道 {cat} 連線成功", 0x9b59b6
            else:
                title = "🌅 早盤策略雷達：帶量突破強擊點" if is_morning else "🌍 盤後宏觀掃描：均線高度壓縮池"
                color = 0xe74c3c if is_morning else 0x1abc9c
            send_embed(wh_map[cat], title, fields, color)

if __name__ == "__main__":
    main()
