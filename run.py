"""AGI 戰情室總入口：python run.py <任務>
任務由外部排程（cron-job.org）指定，不再靠「現在幾點」判斷，所以排程延遲也不會跑錯任務。"""
import sys
import time
import traceback

import common
import sys_log

TASKS = {
    "morning":   ("09:30 早盤", [("早盤雷達", lambda: __import__("radar").run("morning")),
                                 ("資產總表", lambda: __import__("portfolio").run("09:30 早盤"))], True),
    "midday":    ("12:00 午盤", [("資產總表", lambda: __import__("portfolio").run("12:00 午盤")),
                                 ("午盤量能", lambda: __import__("radar").run("midday"))], True),
    "close":     ("13:00 尾盤", [("資產總表", lambda: __import__("portfolio").run("13:00 尾盤"))], True),
    "afternoon": ("15:00 盤後", [("盤後雷達", lambda: __import__("radar").run("afternoon")),
                                 ("歷史足跡", lambda: __import__("footprint").run()),
                                 ("操作留痕", lambda: __import__("footprint").trade_log()),
                                 ("訊號紀錄", lambda: __import__("signal_log").run())], True),
    "spf":       ("15:35 永豐期貨", [("永豐期貨", lambda: __import__("spf_report").run())], True),
    "intraday":  ("盤中警報", [("警報引擎", lambda: __import__("alerts").run())], True),
    "weekly":    ("每週龍頭建議", [("龍頭排名", lambda: __import__("weekly").run())], False),
    "test":      ("手動連線測試", [("各頻道 webhook", sys_log.channel_test)], False),
}


def in_session():
    n = common.now_tw()
    return (n.hour, n.minute) >= (9, 0) and (n.hour, n.minute) <= (13, 35)


def main():
    task = (sys.argv[1] if len(sys.argv) > 1 else "test").strip()
    if task not in TASKS:
        print(f"未知任務 {task}，可用：{', '.join(TASKS)}")
        sys.exit(2)
    label, steps, needs_market = TASKS[task]
    start = time.time()

    if task == "intraday" and not in_session():
        print("非盤中時段，略過")
        return
    if needs_market:
        open_ = common.is_trading_day()
        if open_ is False:
            print("今日休市，略過")
            if task != "intraday":
                sys_log.report(label, [("狀態", "今日休市，略過")], time.time() - start)
            return
        if open_ is None:
            common.warn("無法確認今天是否開市（證交所連不上），照常執行")

    results = []
    for name, fn in steps:
        try:
            results.append((name, fn()))
        except Exception as ex:
            tb = traceback.format_exc()
            print(tb)
            common.error(f"{name} 當機：{type(ex).__name__}: {ex}")
            results.append((name, "❌ 當機（詳見錯誤）"))

    sys_log.report(label, results, time.time() - start, quiet=(task == "intraday"))
    if common.ERRORS:
        sys.exit(1)  # 讓 GitHub 顯示紅燈，不再「出錯也綠燈」


if __name__ == "__main__":
    main()
