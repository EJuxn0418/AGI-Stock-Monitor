"""AGI 戰情室共用工具：時間、Discord 發送、報價、日K、試算表讀取。"""
import os
import io
import csv
import re
import time
from datetime import datetime, timedelta, timezone, date

import requests
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # 本機測試用
    yf = None

VERSION = "DV.03.000"
TW = timezone(timedelta(hours=8))
BT = "\u0060"  # Discord 行內程式碼符號

ERRORS = []    # 嚴重錯誤（會讓系統日誌變紅）
WARNINGS = []  # 一般提醒（系統日誌變黃）


def now_tw():
    return datetime.now(TW)


def today_tw():
    return now_tw().date()


def mono(x):
    return f"{BT}{x}{BT}"


def warn(msg):
    if str(msg) in WARNINGS:
        return
    print("[WARN]", msg)
    WARNINGS.append(str(msg))


def error(msg):
    print("[ERROR]", msg)
    ERRORS.append(str(msg))


def env(name):
    return (os.environ.get(name) or "").strip()


def fnum(x, default=None):
    try:
        v = float(str(x).replace(",", "").strip())
        return v
    except Exception:
        return default


# ---------------------------------------------------------------- Discord
def make_embeds(title, fields, color, description=None, footer=None):
    """把欄位切成多張卡片（每張最多 24 欄、約 4500 字），避免超過 Discord 上限。"""
    chunks, cur, size = [], [], 0
    for f in fields:
        fs = len(f["name"]) + len(f["value"])
        if cur and (len(cur) >= 24 or size + fs > 4500):
            chunks.append(cur)
            cur, size = [], 0
        cur.append(f)
        size += fs
    if cur or not chunks:
        chunks.append(cur)
    embeds = []
    for i, ch in enumerate(chunks):
        e = {
            "title": title if i == 0 else f"{title}（續 {i + 1}）",
            "color": color,
            "fields": ch,
            "footer": {"text": footer or f"AGI 戰情室 {VERSION}"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if description and i == 0:
            e["description"] = description
        embeds.append(e)
    return embeds


def _esize(e):
    n = len(e.get("title", "")) + len(e.get("description", "") or "") + len(e.get("footer", {}).get("text", ""))
    return n + sum(len(f["name"]) + len(f["value"]) for f in e.get("fields", []))


def send(webhook_env, embeds, label=""):
    """把多張卡片打包成訊息發送（每則最多 10 張、5500 字）；遇到限流會等待重試。失敗會記錄成錯誤，不會默默吞掉。"""
    url = env(webhook_env)
    if not url:
        warn(f"{label}：GitHub Secrets 沒有設定 {webhook_env}，略過發送")
        return False
    batches, cur, size = [], [], 0
    for e in embeds:
        es = _esize(e)
        if cur and (len(cur) >= 10 or size + es > 5500):
            batches.append(cur)
            cur, size = [], 0
        cur.append(e)
        size += es
    if cur:
        batches.append(cur)
    ok = True
    for batch in batches:
        for attempt in range(3):
            try:
                r = requests.post(url, json={"embeds": batch}, timeout=15)
                if r.status_code == 429:
                    wait = 2.0
                    try:
                        wait = float(r.json().get("retry_after", 2))
                    except Exception:
                        pass
                    time.sleep(wait + 0.5)
                    continue
                if r.status_code >= 300:
                    error(f"{label}：Discord 回應 {r.status_code} {r.text[:150]}")
                    ok = False
                break
            except Exception as ex:
                if attempt == 2:
                    error(f"{label}：發送失敗 {ex}")
                    ok = False
                time.sleep(2)
    return ok


# ---------------------------------------------------------------- 代號處理
def norm_code(raw):
    """'50' -> '0050'、'2330.0' -> '2330'、'3131.two' -> '3131.TWO'"""
    s = str(raw or "").strip().upper()
    if not s or s in ("NAN", "NONE"):
        return ""
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    if "." in s:
        base, suf = s.split(".", 1)
    else:
        base, suf = s, ""
    if base.isdigit() and len(base) < 4:
        base = base.zfill(4)
    return f"{base}.{suf}" if suf else base


_MARKET = {}  # '3131' -> 'TWO'


def base_of(code):
    return code.split(".")[0]


# ---------------------------------------------------------------- 證交所即時行情
_SESSION = None


def _mis(ex_ch):
    global _SESSION
    try:
        if _SESSION is None:
            _SESSION = requests.Session()
            _SESSION.headers.update({
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://mis.twse.com.tw/stock/index.jsp",
            })
            _SESSION.get("https://mis.twse.com.tw/stock/index.jsp", timeout=10)
        r = _SESSION.get(
            "https://mis.twse.com.tw/stock/api/getStockInfo.jsp",
            params={"ex_ch": ex_ch, "json": "1", "delay": "0", "_": int(time.time() * 1000)},
            timeout=10,
        )
        return r.json().get("msgArray", []) or []
    except Exception as ex:
        warn(f"證交所即時行情連線失敗：{ex}")
        return []


def _first(x):
    return fnum((x or "").split("_")[0])


def _parse_mis(m):
    price = fnum(m.get("z"))
    if not price or price <= 0:
        b, a = _first(m.get("b")), _first(m.get("a"))
        if b and a and b > 0 and a > 0:
            price = (a + b) / 2
        else:
            price = (a if a and a > 0 else None) or (b if b and b > 0 else None)
    d = m.get("d") or ""
    try:
        dd = datetime.strptime(d, "%Y%m%d").date()
    except Exception:
        dd = None
    return {"price": price, "date": dd, "time": m.get("t", ""), "name": m.get("n", ""),
            "prev_close": fnum(m.get("y")), "open": fnum(m.get("o")), "volume": fnum(m.get("v")), "src": "TWSE"}


def resolve(codes):
    """代號 -> Yahoo 代號（自動判斷上市 .TW / 上櫃 .TWO）。"""
    codes = [c for c in dict.fromkeys(codes) if c]
    unknown = [c for c in codes if "." not in c and c not in _MARKET]
    for i in range(0, len(unknown), 10):
        part = unknown[i:i + 10]
        q = "|".join(f"tse_{b}.tw|otc_{b}.tw" for b in part)
        for m in _mis(q):
            c = (m.get("c") or "").upper()
            if c in part and m.get("n"):
                _MARKET[c] = "TW" if m.get("ex") == "tse" else "TWO"
    for b in unknown:
        if b in _MARKET or yf is None:
            continue
        for suf in ("TW", "TWO"):
            try:
                h = yf.Ticker(f"{b}.{suf}").history(period="5d")
                if not h.empty:
                    _MARKET[b] = suf
                    break
            except Exception:
                pass
    out = {}
    for c in codes:
        if "." in c:
            out[c] = c
        elif c in _MARKET:
            out[c] = f"{c}.{_MARKET[c]}"
        else:
            warn(f"{c} 判斷不出上市或上櫃，先當上市（.TW）處理")
            out[c] = f"{c}.TW"
    return out


def live_quotes(tickers):
    """Yahoo 代號清單 -> {ticker: {price, date, time, name, src}}；證交所優先，失敗才用 Yahoo。"""
    tickers = list(dict.fromkeys(tickers))
    out = {}
    pairs = []
    for t in tickers:
        base, suf = t.split(".", 1)
        pairs.append((t, f"{'otc' if suf == 'TWO' else 'tse'}_{base}.tw", base))
    for i in range(0, len(pairs), 20):
        part = pairs[i:i + 20]
        msgs = {(m.get("c") or "").upper(): m for m in _mis("|".join(p[1] for p in part))}
        for t, _, base in part:
            m = msgs.get(base.upper())
            if m:
                q = _parse_mis(m)
                if q["price"]:
                    out[t] = q
    for t in tickers:
        if t in out or yf is None:
            continue
        try:
            h = yf.Ticker(t).history(period="1d", interval="1m")
            if not h.empty:
                out[t] = {"price": float(h["Close"].iloc[-1]), "date": h.index[-1].date(),
                          "time": h.index[-1].strftime("%H:%M:%S"), "name": "", "src": "Yahoo"}
        except Exception:
            pass
        if t not in out:
            warn(f"{t} 抓不到即時價")
    return out


def is_trading_day():
    """用台積電今天有沒有成交資料判斷是否開市。回傳 True/False/None（無法判斷）。"""
    q = live_quotes(["2330.TW"]).get("2330.TW")
    if q and q.get("date"):
        return q["date"] == today_tw()
    return None


# ---------------------------------------------------------------- 日K
def daily_history(tickers, period="150d"):
    """一次批次下載日K，回傳 {ticker: DataFrame(Open, Close, Volume)}，索引為日期。"""
    tickers = list(dict.fromkeys(tickers))
    out = {}
    if not tickers or yf is None:
        return out
    try:
        df = yf.download(tickers, period=period, interval="1d", group_by="ticker",
                         auto_adjust=False, progress=False, threads=True)
    except Exception as ex:
        error(f"Yahoo 日K下載失敗：{ex}")
        return out
    for t in tickers:
        try:
            sub = None
            if isinstance(df.columns, pd.MultiIndex):
                for lvl in (0, 1):
                    if t in df.columns.get_level_values(lvl):
                        sub = df.xs(t, axis=1, level=lvl)
                        break
            elif len(tickers) == 1:
                sub = df
            if sub is None or "Close" not in sub:
                warn(f"{t} 抓不到日K")
                continue
            sub = sub[["Open", "Close", "Volume"]].dropna(subset=["Close"])
            if sub.empty:
                warn(f"{t} 抓不到日K")
                continue
            sub.index = pd.to_datetime(sub.index).date
            out[t] = sub
        except Exception as ex:
            warn(f"{t} 日K解析失敗：{ex}")
    return out


def ma_snapshot(hist, live_price=None, today=None, threshold=0.03):
    """計算均線與壓縮率。有即時價時，用即時價當作今天的收盤（盤中即時均線）。"""
    if hist is None:
        return None
    s = hist["Close"].astype(float).copy()
    today = today or today_tw()
    if live_price:
        if len(s) and s.index[-1] == today:
            s.iloc[-1] = live_price
        else:
            s = pd.concat([s, pd.Series([float(live_price)], index=[today])])
    if len(s) < 20:
        return None
    price = float(s.iloc[-1])
    m = {n: float(s.iloc[-n:].mean()) for n in (5, 10, 20, 60) if len(s) >= n}
    lo, hi = min(m[5], m[10], m[20]), max(m[5], m[10], m[20])
    if lo <= 0:
        return None
    ratio = (hi - lo) / lo
    return {
        "price": price, "m5": m[5], "m10": m[10], "m20": m[20], "m60": m.get(60),
        "ratio": ratio * 100, "compressed": ratio <= threshold,
        "breakout": ratio <= threshold and price > m[5],
    }


# ---------------------------------------------------------------- 試算表
def read_tab(name, required=()):
    """讀 Google 試算表的某個分頁（需開啟「知道連結的人可檢視」）。沒設定或讀取失敗回傳 None。"""
    sid = env("SHEET_ID")
    if not sid:
        return None
    try:
        r = requests.get(f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq",
                         params={"tqx": "out:csv", "sheet": name, "headers": "1"}, timeout=20)
        r.raise_for_status()
        txt = r.content.decode("utf-8-sig")
        if txt.lstrip().startswith("<"):
            error(f"試算表「{name}」讀不到，請確認共用設定是「知道連結的任何人：檢視者」")
            return None
        rows = []
        for row in csv.DictReader(io.StringIO(txt)):
            clean = {str(k).strip(): str(v or "").strip() for k, v in row.items() if k}
            if any(clean.values()):
                rows.append(clean)
        if rows and required:
            missing = [c for c in required if c not in rows[0]]
            if missing:
                error(f"試算表「{name}」缺少欄位 {missing}（分頁名稱打錯時 Google 會回傳第一個分頁）")
                return None
        return rows
    except Exception as ex:
        error(f"試算表「{name}」讀取失敗：{ex}")
        return None


def enabled(v):
    return str(v or "").strip().upper() not in {"否", "N", "NO", "FALSE", "0", "X", "❌", "停用", "關"}


def parse_date(s):
    s = str(s or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    m = re.match(r"Date\((\d+),(\d+),(\d+)", s)  # Google 偶爾回傳 Date(2026,5,12)
    if m:
        return date(int(m.group(1)), int(m.group(2)) + 1, int(m.group(3)))
    return None
