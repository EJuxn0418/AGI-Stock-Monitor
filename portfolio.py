import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# AGI 投資戰情室 v8.8.1 - 核心資產損益回報 (portfolio.py)
# ---------------------------------------------------
# 【長線/主動型核心權益持倉】(固定抱緊的大底倉)
LONG_PORTFOLIO = {
    '00941.TW': ['00941 中信上游半導體', 2, 16.74],
    '00981A.TW': ['00981A 統一台灣優選股A', 4, 29.7625]
}

# 🌟【短線戰術右側個股持倉】(預留空間！未來有進場直接在這裡加一行即可)
# 格式範例：'代碼.TW': ['股票名稱', 5MA, 10MA, 張數, 買入均價]
SHORT_PORTFOLIO = {
    # 目前空手保留最高現金主動權，有新單直接在此掛載
}

def get_stock_price(ticker):
    try:
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not live.empty:
            return float(live['Close'].values[-1])
        hist = yf.download(ticker, period="5d", interval="1d", progress=False)
        return float(hist['Close'].values[-1])
    except:
        return None

def send_portfolio_embed(webhook_url, fields):
    if not webhook_url or not fields: return
    payload = {
        "embeds": [{
            "title": "📊 戰情室午盤：核心資產權益彙整總表",
            "description": "系統已對長線底倉、主動型資產與短線個股進行盤中損益精算：",
            "color": 0x34495e,
            "fields": fields,
            "footer": {"text": "AGI 資產風控中心"},
            "timestamp": datetime.utcfromtimestamp(datetime.now(timezone(timedelta(hours=8))).timestamp()).isoformat() + "Z"
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    # 讀取對應你 Discord #總表 頻道的隱私門牌
    wh_summary = os.environ.get('WH_PORTFOLIO_SUMMARY')
    
    now = datetime.now(timezone(timedelta(hours=8)))
    is_noon = 12 <= now.hour < 15
    is_test_mode = now.hour >= 20
    
    if is_noon or is_test_mode:
        fields = []
        total_cost = 0
        total_market_value = 0
        
        # 1. 計算長線與主動型核心資產
        for t, info in LONG_PORTFOLIO.items():
            curr_price = get_stock_price(t)
            if not curr_price: continue
            
            name, qty, cost = info[0], info[1], info[2]
            sub_cost = cost * qty * 1000
            sub_value = curr_price * qty * 1000
            sub_profit = sub_value - sub_cost
            roi = (sub_profit / sub_cost) * 100
            
            total_cost += sub_cost
            total_market_value += sub_value
            
            roi_sign = "🟢 +" if roi >= 0 else "🔴 "
            fields.append({
                "name": f"🏛️ {name} ({qty}張)",
                "value": f"成本均價: `{cost:.4f}`\n盤中現價: `{curr_price:.2f}`\n即時損益: `{roi_sign}{roi:.2f}%` (`{sub_profit:+,2.0f} 元`)",
                "inline": True
            })
            
        # 2. 自動偵測並計算短線戰術部位 (如果 SHORT_PORTFOLIO 裡有股票的話)
        short_status_str = "短線個股空手，保留最高現金主動權。"
        if SHORT_PORTFOLIO:
            short_status_str = "短線右側個股部隊出擊中，嚴守均線防守線。"
            for t, info in SHORT_PORTFOLIO.items():
                curr_price = get_stock_price(t)
                if not curr_price: continue
                
                name, qty, cost = info[0], info[3], info[4]
                sub_cost = cost * qty * 1000
                sub_value = curr_price * qty * 1000
                sub_profit = sub_value - sub_cost
                roi = (sub_profit / sub_cost) * 100
                
                total_cost += sub_cost
                total_market_value += sub_value
                
                roi_sign = "🟢 +" if roi >= 0 else "🔴 "
                fields.append({
                    "name": f"⚔️ 短線戰術 | {name} ({qty}張)",
                    "value": f"進場成本: `{cost:.2f}`\n盤中現價: `{curr_price:.2f}`\n戰術損益: `{roi_sign}{roi:.2f}%` (`{sub_profit:+,2.0f} 元`)",
                    "inline": True
                })
                
        # 3. 全帳戶權益大結算
        if total_cost > 0:
            total_profit = total_market_value - total_cost
            total_roi = (total_profit / total_cost) * 100
            total_sign = "🟢 +" if total_profit >= 0 else "🔴 "
            
            fields.insert(0, {
                "name": "💳 全帳戶權益加總 (Equity Summary)",
                "value": f"總投資本金: `{total_cost:,.0f} 元`\n總估算市值: `{total_market_value:,.0f} 元`\n整體回報率: **`{total_sign}{total_roi:.2f}%`** (**`{total_profit:+,2.0f} 元`**)\n當前狀態: `✅ {short_status_str}`",
                "inline": False
            })
            
        send_portfolio_embed(wh_summary, fields)

if __name__ == "__main__":
    main()
