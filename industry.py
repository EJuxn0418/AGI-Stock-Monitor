"""官方產業分類：從證交所／櫃買中心 OpenAPI 抓公司基本資料（產業別、股數），同時順便確定上市或上櫃。"""
import re
import requests
import common
from common import fnum, warn

NAMES = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械", "06": "電器電纜",
    "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造業",
    "15": "航運業", "16": "觀光餐旅", "17": "金融保險業", "18": "貿易百貨業", "19": "綜合", "20": "其他業",
    "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業",
    "26": "光電業", "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技業", "34": "電子商務", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "80": "管理股票", "91": "存託憑證",
}
SKIP = {"管理股票", "存託憑證"}
_CACHE = None


def _get(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    r.raise_for_status()
    return r.json()


def official():
    """{代號: {name, industry, market, shares}}；抓不到時回傳空的，系統會退回原本的判斷方式。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    out = {}
    try:
        for r in _get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L"):
            code = str(r.get("公司代號", "")).strip()
            par = fnum(re.sub(r"[^\d.]", "", str(r.get("普通股每股面額", "")))) or 10
            cap = fnum(r.get("實收資本額"))
            out[code] = {"name": str(r.get("公司簡稱", "")).strip(), "market": "TW",
                         "industry": NAMES.get(str(r.get("產業別", "")).strip(), "其他業"),
                         "shares": cap / par if cap else None}
    except Exception as ex:
        warn(f"證交所公司基本資料讀取失敗：{ex}")
    try:
        for r in _get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"):
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            out[code] = {"name": str(r.get("CompanyAbbreviation", "")).strip(), "market": "TWO",
                         "industry": NAMES.get(str(r.get("SecuritiesIndustryCode", "")).strip(), "其他業"),
                         "shares": fnum(r.get("IssueShares"))}
    except Exception as ex:
        warn(f"櫃買中心公司基本資料讀取失敗：{ex}")
    for code, v in out.items():
        common._MARKET.setdefault(code, v["market"])
    _CACHE = out
    return out


def info(code):
    o = official().get(common.base_of(code))
    if o:
        return o
    if code.startswith("00"):
        return {"name": code, "industry": "ETF", "market": None, "shares": None}
    return {"name": code, "industry": "未分類", "market": None, "shares": None}


def day_closes():
    """全市場最近一個交易日的收盤價（每週龍頭排名用）。"""
    px = {}
    try:
        for r in _get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"):
            px[str(r.get("Code", "")).strip()] = fnum(r.get("ClosingPrice"))
    except Exception as ex:
        warn(f"證交所全市場收盤價讀取失敗：{ex}")
    try:
        for r in _get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"):
            px[str(r.get("SecuritiesCompanyCode", "")).strip()] = fnum(r.get("Close"))
    except Exception as ex:
        warn(f"櫃買中心全市場收盤價讀取失敗：{ex}")
    return {k: v for k, v in px.items() if v}
