import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

def get_spf_reports():
    url = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
    headers = {'User-Agent': 'Mozilla/5.0'}
    fields = []
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('tr') or soup.select('li') or soup.select('.list-item')
        now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        
        d1 = now_tw.strftime('%Y/%m/%d')
        d2 = f"{now_tw.year}/{now_tw.month}/{now_tw.day}"
        d3 = now_tw.strftime('%Y-%m-%d')
        
        for item in items:
            link = item.find('a')
            if not link: continue
            item_text = item.get_text()
            if d1 in item_text or d2 in item_text or d3 in item_text:
                href = link.get('href')
                full_url = f"https://www.spf.com.tw{href}" if href.startswith('/') else href
                title_text = link.get('title') or link.get_text(strip=True)
                if "期貨" in title_text or "日報" in title_text or "法人" in title_text:
                    fields.append({"name": f"📰 {title_text}", "value": f"[點擊閱讀完整 PDF 報告]({full_url})", "inline": False})
        return fields
    except Exception as e:
        print(f"爬蟲出錯: {e}")
        return []

def send_spf_embed(webhook_url, fields, is_test=False):
    if not webhook_url or not fields: return
    title = "🧪 [強制連線測試] 永豐期貨報告模組" if is_test else "📈 盤後情報：永豐期貨市場研究報告"
    color = 0x9b59b6 if is_test else 0x2980b9
    payload = {"embeds": [{"title": title, "description": "系統已自動抓取今日最新釋出的法人籌碼與期現貨策略報告：", "color": color, "fields": fields, "footer": {"text": "AGI 盤後數據中心 DV.01.005"}, "timestamp": datetime.now(timezone.utc).isoformat()}]}
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        print(f"永豐 Webhook 發送失敗: {e}")

def main():
    wh_spf = os.environ.get('WH_SPF_REPORT')
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    h = now_tw.hour
    
    # 嚴格鎖定 15:00 區間為實體爬蟲，其餘時段手動觸發皆為壓力測試
    is_afternoon = (h == 15 or h == 16)
    is_test = not is_afternoon
    
    report_fields = get_spf_reports() if is_afternoon else []
    
    if not report_fields:
        if is_test:
            report_fields = [{"name": "🧪 網路連線測試", "value": "這是強制觸發的測試報告，代表 Webhook 與爬蟲神經網路運作完全正常。"}]
        else:
            report_fields = [{"name": "通知", "value": "今日永豐期貨尚未更新報告，或今日為非交易日。"}]
            
    send_spf_embed(wh_spf, report_fields, is_test)

if __name__ == "__main__":
    main()
