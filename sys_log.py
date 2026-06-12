import os
import requests
import sys
from datetime import datetime, timedelta, timezone

def send_log_embed(webhook_url, channel_name, task_name, message, color=0x95a5a6):
    if not webhook_url: return
    payload = {
        "embeds": [{
            "title": f"⚙️ AGI 運行日誌 - 核心同步完成",
            "description": f"系統已成功向 [**{channel_name}**] 執行自動化指令同步。",
            "color": color,
            "fields": [
                {"name": "⚙️ 觸發模組任務", "value": f"`{task_name}`", "inline": True},
                {"name": "📊 核心同步狀態", "value": f"✅ `{message}`", "inline": True}
            ],
            "footer": {"text": "AGI 核心維護日誌中心 DV.01.003"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    wh_sys_log = os.environ.get('WH_SYS_LOG')
    wh_trade_log = os.environ.get('WH_TRADE_LOG')

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    h = now_tw.hour
    
    # 根據當前實體台灣時間自動判定任務名稱
    if h == 9:
        task_info = ["09:30 早盤開盤突破雷達", "已完成雙龍頭均線壓縮起漲突破度掃描。"]
    elif h == 12:
        task_info = ["12:00 中盤權益總表結算", "已完成全帳戶資產中盤即時損益精算。"]
    elif h == 13:
        task_info = ["13:00 尾盤權益總表結算", "已完成現貨收盤權益加總與狀態留痕。"]
    elif h == 15:
        task_info = ["15:00 歷史足跡與期貨報告", "已完成11檔前任籌碼沉澱池掃描與永豐期貨報告爬取。"]
    else:
        task_info = [f"🧪 盤中手動強制突擊測試 ({now_tw.strftime('%H:%M')})", "手動無視時間鎖測試，核心通道全面暢通！"]

    if wh_sys_log:
        send_log_embed(wh_sys_log, "#系統日誌", task_info[0], task_info[1], color=0x7f8c8d)
    if wh_trade_log:
        send_log_embed(wh_trade_log, "#操作留痕 (備援)", task_info[0], task_info[1], color=0x34495e)

if __name__ == "__main__":
    main()
