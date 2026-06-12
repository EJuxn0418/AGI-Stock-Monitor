import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

WATCH_LIST = {
    '0050.TW': '元大台灣50 (歷史止盈)', '2317.TW': '鴻海 (組裝權值指標)', '2454.TW': '聯發科 (晶片權值指標)',
    '1528.TW': '恩德 (歷史短線倉)', '3481.TW': '群創 (歷史短線倉)', '2421.TW': '建準 (歷史短線倉)',
    '1513.TW': '中興電 (歷史短線倉)', '2489.TW': '瑞軒 (歷史短線倉)', '2344.TW': '華邦電 (歷史監控)',
    '2646.TW': '星宇航空 (歷史監控)', '3037.TW': '欣興 (歷史監控)'
}

def check_footprint_strategy(data):
    if not data: return None
    ma_list = [data['m5'], data['m10'], data['m20']]
    comp_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_compressed = comp_ratio <= 0.03
    is_breakout = data['price'] > data['m5'] and is_compressed
    return {"ratio": comp_ratio * 100, "is_compressed": is_compressed, "is_breakout": is_breakout}

def get_stock_data(ticker):
    try:
        hist = yf.download(ticker, period="60d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].values[-1]) if not live.empty else float(hist['Close'].values[-1])
        return {"price": curr, "m5": float(hist['Close'].rolling(5).mean().values[-1]), "m10": float(hist['Close'].rolling(10).mean().values[-1]), "m20": float(hist['Close'].rolling(20).mean().values[-1])}
    except: return None

def send_footprint_embed(webhook_url, fields):
    if not webhook_url or not fields: return
    payload = {"embeds": [{"title": "👀 盤後追蹤：歷史足跡與戰略觀察池報告", "description": "系統已針對你曾操作過的所有前任標的與指定指標進行均線型態掃描：", "color": 0xe67e22, "fields": fields, "footer": {"text": "AGI 歷史軌跡追蹤器 DV.01.003"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    requests.post(webhook_url, json=payload)

def main():
    wh_footprint = os.environ.get('WH_KEY_WATCH')
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    
    # 只要手動按下，一律強制高亮，方便現場抓鬼
    is_afternoon = True 
    fields = []
    
    for t, name in WATCH_LIST.items():
        d = get_stock_data(t)
        strat = check_footprint_strategy(d)
        if not strat: continue
        
        if strat['is_breakout']: status_icon = "🔥 [起漲突破訊號]"
        elif strat['is_compressed']: status_icon = "🌐 [籌碼蓄勢糾結中]"
        else: status_icon = "⚪ 波動發散盤整中"
            
        if strat['is_compressed'] or strat['is_breakout'] or is_afternoon:
            fields.append({"name": f"{name} ({t})", "value": f"當前現價: `{d['price']:.2f}`\n狀態型態: {status_icon}\n即時壓縮率: `{strat['ratio']:.1f}%`", "inline": True})
            
    send_footprint_embed(wh_footprint, fields)

if __name__ == "__main__":
    main()
