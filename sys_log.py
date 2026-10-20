"""系統日誌：正常時只發一行；有提醒或錯誤才展開完整卡片，並讓 GitHub 亮紅燈。"""
from common import make_embeds, send, now_tw, ERRORS, WARNINGS, env
import ui


def report(task_label, results, seconds, quiet=False):
    """results: [(模組名稱, 結果文字)]；quiet=True 時只有出錯才發（盤中警報用，避免洗版）。"""
    if quiet and not ERRORS:
        return
    run_url = env("RUN_URL")
    link = f"　[紀錄]({run_url})" if run_url else ""
    if not ERRORS and not WARNINGS:
        brief = "　·　".join(f"{name} {str(res)[:60]}" for name, res in results)
        send("WH_SYS_LOG", [ui.embed(f"✅ {task_label}　{seconds:.0f} 秒", brief + link, ui.GREEN)], label="系統日誌")
        return
    color = ui.RED if ERRORS else ui.GOLD
    status = "❌ 有錯誤，請截圖給 Claude" if ERRORS else "⚠️ 完成，但有提醒"
    fields = [{"name": name, "value": str(res)[:1000] or "-", "inline": False} for name, res in results]
    if ERRORS:
        fields.append({"name": "❌ 錯誤", "value": "\n".join(ERRORS[:10])[:1000], "inline": False})
    if WARNINGS:
        fields.append({"name": "⚠️ 提醒", "value": "\n".join(WARNINGS[:10])[:1000], "inline": False})
    send("WH_SYS_LOG", [ui.embed(f"{'❌' if ERRORS else '⚠️'} {task_label}　{seconds:.0f} 秒", status + link, color, fields[:25])],
         label="系統日誌")


def legend():
    """發一則符號說明到產業雷達，給使用者釘選。"""
    desc = "\n".join([
        "**色條**　🟥 偏多　🟩 偏空　🟨 特別注意（⭐共振／午盤爆量）　⬜ 系統資訊",
        "**漲跌**　🔴 上漲　🟢 下跌　⚪ 平盤（台股紅漲綠跌）",
        ui.RULE,
        "✅ **剛站上**　今天收在均線上、昨天還在下方，例：✅5·20MA",
        "⏳ **快站上**　在均線下方 1% 內且均線走平或上彎，例：⏳20MA-0.3%",
        "🔥 **大量紅K**／🧊 **大量黑K**　成交量 ≥ 20 日均量 2 倍，例：🔥2.6x",
        "⚡ **午盤量能**　12:00 累計量已達均量 80%",
        "⭐ **共振**　產業龍頭 ＋ 你經手過的股票，同時出現訊號",
        "💼 **持有中**　▰▰▱▱▱ 損益條，每格 2%",
        ui.RULE,
        "門檻可在試算表「說明」分頁調整",
    ])
    target = "WH_RADAR" if env("WH_RADAR") else "WH_RADAR_SEMICON"
    ok = send(target, [ui.embed("📖 戰情室符號說明（建議釘選）", desc, ui.GRAY)], label="符號說明")
    return "已發送，請到 #產業雷達 釘選" if ok else "發送失敗"


def channel_test():
    """手動測試：每個頻道各送一張測試卡，確認 webhook 都通。"""
    names = ["WH_PORTFOLIO_SUMMARY", "WH_KEY_WATCH", "WH_TRADE_LOG", "WH_RADAR" if env("WH_RADAR") else "WH_RADAR_SEMICON",
             "WH_SPF_REPORT", "WH_ALERT", "WH_WEEKLY"]
    ok, bad = [], []
    for n in names:
        card = [ui.embed("🧪 連線測試", f"`{n}` 這個頻道的 webhook 正常", ui.GRAY)]
        (ok if send(n, card, label=n) else bad).append(n)
    return f"成功 {len(ok)}，失敗/未設定 {len(bad)}" + (f"：{'、'.join(bad)}" if bad else "")
