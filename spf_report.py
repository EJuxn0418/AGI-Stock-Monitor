"""永豐期貨研究報告：盤後抓今天新出的報告連結。"""
import requests
from bs4 import BeautifulSoup
from common import send, today_tw, error
import ui

URL = "https://www.spf.com.tw/sinopacSPF/research/list.do?id=1709f20d3ff00000d8e2039e8984ed51"
KEYWORDS = ("期貨", "日報", "法人", "盤後", "籌碼")


def fetch():
    res = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    d = today_tw()
    stamps = (f"{d:%Y/%m/%d}", f"{d.year}/{d.month}/{d.day}", f"{d:%Y-%m-%d}", f"{d:%Y%m%d}")
    found, seen = [], set()
    for item in soup.select("tr, li"):
        link = item.find("a")
        if not link or not link.get("href"):
            continue
        text = item.get_text(" ", strip=True)
        if not any(s in text for s in stamps):
            continue
        title = link.get("title") or link.get_text(strip=True)
        if not any(k in title for k in KEYWORDS):
            continue
        href = link["href"]
        full = href if href.startswith("http") else "https://www.spf.com.tw" + ("" if href.startswith("/") else "/") + href
        if full in seen:
            continue
        seen.add(full)
        found.append(f"📰 [{title[:120]}]({full})")
    return found


def run():
    try:
        fields = fetch()
    except Exception as ex:
        error(f"永豐期貨網站抓取失敗：{ex}")
        return "抓取失敗"
    if not fields:
        send("WH_SPF_REPORT", [ui.embed("📈 永豐期貨盤後報告", f"今天還沒找到報告，可能尚未發布或網站改版\n[手動查看]({URL})", ui.GRAY)],
             label="永豐期貨")
        return "沒有找到今日報告"
    send("WH_SPF_REPORT", [ui.embed(f"📈 永豐期貨盤後報告｜{today_tw():%m/%d}", f"**{len(fields)} 份**\n{ui.RULE}\n" + "\n".join(fields), ui.GRAY)],
         label="永豐期貨")
    return f"{len(fields)} 份報告"
