"""系統日誌：每次任務結束回報執行結果；有錯誤一定會亮紅燈，不再默默吞掉。"""
from common import make_embeds, send, mono, now_tw, ERRORS, WARNINGS, env


def report(task_label, results, seconds, quiet=False):
    """results: [(模組名稱, 結果文字或例外)]；quiet=True 時只有出錯才發（盤中警報用，避免洗版）。"""
    if quiet and not ERRORS:
        return
    color = 0xE74C3C if ERRORS else 0xF1C40F if WARNINGS else 0x2ECC71
    status = "❌ 有錯誤" if ERRORS else "⚠️ 完成但有提醒" if WARNINGS else "✅ 正常"
    fields = [{"name": name, "value": str(res)[:1000] or "-", "inline": False} for name, res in results]
    if ERRORS:
        fields.append({"name": "❌ 錯誤", "value": "\n".join(ERRORS[:10])[:1000], "inline": False})
    if WARNINGS:
        fields.append({"name": "⚠️ 提醒", "value": "\n".join(WARNINGS[:10])[:1000], "inline": False})
    run_url = env("RUN_URL")
    desc = f"{status}｜耗時 {mono(f'{seconds:.0f} 秒')}" + (f"｜[執行紀錄]({run_url})" if run_url else "")
    send("WH_SYS_LOG", make_embeds(f"⚙️ 系統日誌｜{task_label}｜{now_tw():%m/%d %H:%M}", fields, color, description=desc),
         label="系統日誌")


def channel_test():
    """手動測試：每個頻道各送一張測試卡，確認 webhook 都通。"""
    names = ["WH_PORTFOLIO_SUMMARY", "WH_KEY_WATCH", "WH_TRADE_LOG", "WH_RADAR_SEMICON", "WH_RADAR_COOLING",
             "WH_RADAR_POWER", "WH_RADAR_OPTICS", "WH_RADAR_OTHER", "WH_SPF_REPORT", "WH_ALERT"]
    ok, bad = [], []
    for n in names:
        card = make_embeds("🧪 連線測試", [{"name": n, "value": f"這個頻道的 webhook 正常｜{now_tw():%H:%M:%S}", "inline": False}], 0x9B59B6)
        (ok if send(n, card, label=n) else bad).append(n)
    return f"成功 {len(ok)}，失敗/未設定 {len(bad)}" + (f"：{'、'.join(bad)}" if bad else "")
