import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# AGI 投資戰情室 版本號：DV.01.002 - 雙龍頭分流雷達
# ---------------------------------------------------
THEME_POOL = {
    # ⚡ [科技核心一級戰區]
    # 半導體與設備特戰隊 -> 投遞至 WH_RADAR_SEMICON
    '2330.TW': ['台積電', '半導體核心', 'SEMICON'], 
    '3131.TWO': ['弘塑', '先進封裝設備', 'SEMICON'],
    '3583.TW': ['辛耘', '先進封裝設備', 'SEMICON'],
    
    # 散熱規格升級雙雄 -> 投遞至 WH_RADAR_COOLING
    '3324.TW': ['雙鴻', '散熱動能', 'COOLING'], 
    '3017.TW': ['奇鋐', '散熱動能', 'COOLING'],    
    
    # 重電能源雙箭頭 (士電模式) -> 投遞至 WH_RADAR_POWER
    '1503.TW': ['士電', '重電能源', 'POWER'],    
    '1514.TW': ['亞力', '重電能源', 'POWER'],
    
    # 光通訊題材股 -> 投遞至 WH_RADAR_OPTICS
    '3450.TW': ['聯鈞', 'CPO矽光子', 'OPTICS'],    
    '3363.TW': ['上詮', 'CPO矽光子', 'OPTICS'],    
    '1815.TW': ['富喬', '高階玻纖布', 'OPTICS'],
    '3491.TWO': ['昇達科', '低軌衛星龍頭', 'OPTICS'],

    # 🌟 [非科技/傳統產業季度動能池] -> 統一投遞至新開的 WH_RADAR_OTHER
    '6806.TW': ['雲豹能源', '綠能環保龍頭', 'OTHER'],
    '2646.TW': ['星宇航空', '航空觀光動能', 'OTHER'],
    '1795.TW': ['美時', '生技癌症藥巨頭', 'OTHER'],
    '6472.TW': ['保瑞', '生技CDMO龍頭', 'OTHER'],
    '2548.TW': ['華固', '高段班營建資產', 'OTHER'],
    '1101.TW': ['台泥', '低基期儲能轉型', 'OTHER']
}

def check_strategy(data):
    if not data: return None
    ma_list = [data['m5'], data['m10'], data['m20']]
    comp_ratio = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_compressed = comp_ratio <= 0.03 # 3% 均線緊密壓縮
    is_breakout = data['price'] > data['m5'] and is_compressed
    return {"ratio": comp_ratio * 100, "is_compressed": is_compressed, "is_breakout": is_breakout}

def get_stock_data(ticker):
    try:
        hist = yf.download(ticker, period="60d", interval="1d", progress=False)
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        curr = float(live['Close'].values[-1]) if not live.empty else float(hist['Close'].values[-1])
        return {
            "price": curr, 
            "m5": float(hist['Close'].rolling(5).mean().values[-1]),
            "m10": float(hist['Close'].rolling(10).mean().values[-1]),
            "m20": float(hist['Close'].rolling(20).mean().values[-1])
        }
    except: return None

def send_embed(webhook_url, title, fields, color=0x3498db):
    if not webhook_url or not fields: return
    payload = {
        "embeds": [{
            "title": title, 
            "color": color, 
            "fields": fields, 
            "footer": {"text": "AGI 季度動能分流雷達 DV.01.002"}, 
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    # 讀取網址：包含全新加入的台股其他頻道門牌
    wh_map = {
        'SEMICON': os.environ.get('WH_RADAR_SEMICON'),
        'COOLING': os.environ.get('WH_RADAR_COOLING'),
        'POWER': os.environ.get('WH_RADAR_POWER'),
        'OPTICS': os.environ.get('WH_RADAR_OPTICS'),
        'OTHER': os.environ.get('WH_RADAR_OTHER') # 👈 全新掛載
    }
    
    now = datetime.now(timezone(timedelta(hours=8)))
    is_morning = 9 <= now.hour < 12
    is_afternoon = 15 <= now.hour < 20
    is_test_mode = now.hour >= 20  
    
    signals = {'SEMICON': [], 'COOLING': [], 'POWER': [], 'OPTICS': [], 'OTHER': []}

    for t, info in THEME_POOL.items():
        d = get_stock_data(t)
        strat = check_strategy(d)
        if not strat: continue
        
        category = info[2]
        
        # 🌅 早盤模式：抓「壓縮突破」的起漲點
        if (is_morning or is_test_mode) and strat['is_breakout']:
            signals[category].append({
                "name": f"🔥 壓縮突破 | {info[0]} ({info[1]})",
                "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`",
                "inline": True
            })
            
        # 🌍 盤後模式：抓「正在壓縮蓄勢」的潛伏標的
        elif (is_afternoon or is_test_mode) and strat['is_compressed']:
            signals[category].append({
                "name": f"🌐 籌碼蓄積 | {info[0]} ({info[1]})",
                "value": f"現價: `{d['price']:.2f}`\n壓縮率: `{strat['ratio']:.1f}%`",
                "inline": True
            })

    # 分流投遞
    for cat, fields in signals.items():
        if fields:
            title = "🌅 早盤策略雷達：帶量突破強擊點" if (is_morning and not is_test_mode) else "🌍 盤後宏觀掃描：均線高度壓縮池"
            if is_test_mode: title = f"🧪 [全局測試] - 產業分流測試 ({cat})"
            
            color = 0xe74c3c if (is_morning or is_test_mode) else 0x1abc9c
            send_embed(wh_map[cat], title, fields, color)

if __name__ == "__main__":
    main()
