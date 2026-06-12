import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, timedelta, timezone

LONG_PORTFOLIO = {
    '00941.TW': ['00941 中信上游半導體', 2, 16.74],
    '00981A.TW': ['00981A 統一台灣優選股A', 4, 29.7625]
}
SHORT_PORTFOLIO = {}

def get_stock_price(ticker):
    try:
        live = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not live.empty: return float(live['Close'].values[-1])
        hist = yf.download(ticker, period="5d", interval="1d", progress=False)
        return float(hist['Close'].values[-1])
    except: return None

def send_portfolio_embed(webhook_url, title_suffix, fields):
    if not webhook_url or not fields: return
    payload = {"embeds": [{"title": f"📊 戰情室結算：{title_suffix}", "description": "系統已對長線底倉、主動型資產與短線個股進行精準定點損益精算：", "color": 0x34495e, "fields": fields, "footer": {"text": "AGI 資產風控中心 DV.01.003"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    requests.post(webhook_url, json=payload)

def main():
    wh_summary = os.environ.get('WH_PORTFOLIO_SUMMARY')
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    h = now_tw.hour
    
    if h == 9:
        title_suffix = "🌅 09:30 早盤開盤權益觀測總表"
    elif h == 12:
        title_suffix = "☀️ 12:00 中盤資金分向總表"
    elif h == 13:
        title_suffix = "🌍 13:00 尾盤現貨定型總表"
    else:
        title_suffix = f"🧪 盤後手動強制資產結算 ({now_tw.strftime('%H:%M')})"

    fields = []
    total_cost = 0
    total_market_value = 0
    
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
        fields.append({"name": f"🏛️ {name} ({qty}張)", "value": f"成本均價: `{cost:.4f}`\n盤中現價: `{curr_price:.2f}`\n即時損益: `{roi_sign}{roi:.2f}%` (`{sub_profit:+,2.0f} 元`)", "inline": True})
        
    if total_cost > 0:
        total_profit = total_market_value - total_cost
        total_roi = (total_profit / total_cost) * 100
        total_sign = "🟢 +" if total_profit >= 0 else "🔴 "
        fields.insert(0, {"name": "💳 全帳戶權益加總 (Equity Summary)", "value": f"總投資本金: `{total_cost:,.0f} 元`\n總估算市值: `{total_market_value:,.0f} 元`\n整體回報率: **`{total_sign}{total_roi:.2f}%`** (**`{total_profit:+,2.0f} 元`**)\n當前狀態: `✅ 短線個股空手，保留最高現金主動權。`", "inline": False})
        
    send_portfolio_embed(wh_summary, title_suffix, fields)

if __name__ == "__main__":
    main()
