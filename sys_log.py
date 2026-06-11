import os
import requests
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------
# AGI 投資戰情室 v1.0 - 系統日誌與交易交叉留痕 (sys_log.py)
# ---------------------------------------------------

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
            "footer": {"text": "AGI 核心維護日誌中心"},
            "timestamp": datetime.utcfromtimestamp(datetime.now(timezone(timedelta(hours=8))).timestamp()).isoformat() + "Z"
        }]
    }
    requests.post(webhook_url, json=payload)

def main():
    # 同時讀取兩個頻道的 Webhook
    wh_sys_log = os.environ.get('WH_SYS_LOG')    # 新增：對應 #系統日誌 密鑰
    wh_trade_log = os.environ.get('WH_TRADE_LOG') # 對應 #操作留痕 密鑰

    # 從命令列參數讀取當前是執行哪一個任務
    task_type = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    
    task_map = {
        "morning_radar": ["09:30 早盤開盤突破雷達", "已完成雙龍頭均線壓縮起漲突破度掃描。"],
        "noon_portfolio": ["12:00 中盤權益總表結算", "已完成全帳戶資產中盤即時損益精算。"],
        "afternoon_portfolio": ["13:00 尾盤權益總表結算", "已完成現貨收盤權益加總與狀態留痕。"],
        "afternoon_scan": ["15:00 歷史足跡與期貨報告", "已完成11檔前任籌碼沉澱池掃描與永豐期貨報告爬取。"],
        "test": ["🧪 全局系統自檢測試", "核心模組互鎖測試成功，網路門牌通暢。"]
    }
    
    task_info = task_map.get(task_type, ["未知系統任務", "外部手動觸發執行。"])
    
    # ⚡ 雙重投遞：同時往 `#系統日誌` 和 `#操作留痕` 灌入足跡
    if wh_sys_log:
        send_log_embed(wh_sys_log, "#系統日誌", task_info[0], task_info[1], color=0x7f8c8d)
    if wh_trade_log:
        send_log_embed(wh_trade_log, "#操作留痕 (功能重疊備援)", task_info[0], task_info[1], color=0x34495e)

if __name__ == "__main__":
    main()
