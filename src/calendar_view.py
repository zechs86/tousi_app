# calendar_view.py 【優待・決算の「予定」をまとめる(共通部品)】
# 通知(notify_job)とダッシュボード(🗓️予定タブ)の両方から使う。
#   ・yutai_schedule() … 株主優待の権利付最終日カレンダー(残り日数＋現在値＋1年レンジ位置)
#   ・earnings_schedule(codes) … 指定銘柄の次回決算発表日(yfinance Ticker.calendar)
# ※日本株はyfinanceに決算日が無い/ズレることがある=取れた範囲で返す。

import datetime as dt

import config
import watch  # last_business_day / minus_business_days / RECORD_MONTHS を再利用


def months_map():
    """優待の権利確定月マップ。watch.RECORD_MONTHS と config.YUTAI_RECORD_MONTHS を合算。"""
    m = dict(getattr(watch, "RECORD_MONTHS", {}))
    m.update(getattr(config, "YUTAI_RECORD_MONTHS", {}) or {})
    return m


def _next_kenri(months, today):
    """その銘柄の、今日以降で最も近い (権利付最終日, 権利確定日) を返す。無ければ(None,None)。"""
    cands = []
    for y in (today.year, today.year + 1):
        for mo in months:
            record = watch.last_business_day(y, mo)       # 権利確定日(月末最終営業日)
            kenri = watch.minus_business_days(record, 2)  # 権利付最終日(2営業日前)
            if kenri >= today:
                cands.append((kenri, record))
    cands.sort()
    return cands[0] if cands else (None, None)


def price_range(code):
    """(現在値, 1年レンジ内%位置, 圏ラベル) を返す。失敗時は (None, None, None)。"""
    try:
        import pandas as pd
        import yfinance as yf
        df = yf.download(code, period="1y", interval="1d",
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        price = float(df["Close"].iloc[-1])
        lo, hi = float(df["Close"].min()), float(df["Close"].max())
        pos = (price - lo) / (hi - lo) * 100 if hi != lo else 50
        zone = "安値圏" if pos <= 30 else ("高値圏" if pos >= 70 else "中間")
        return price, pos, zone
    except Exception:
        return None, None, None


def yutai_schedule(today=None, with_price=True):
    """優待カレンダー。[{code,name,kenri,record,days,price,pos,zone}] を残り日数の近い順で返す。"""
    if today is None:
        today = dt.date.today()
    try:
        from universe import UNIVERSE
    except Exception:
        UNIVERSE = {}
    rows = []
    for code, months in months_map().items():
        kenri, record = _next_kenri(months, today)
        if not kenri:
            continue
        row = {"code": code, "name": UNIVERSE.get(code, code.replace(".T", "")),
               "kenri": kenri, "record": record, "days": (kenri - today).days,
               "price": None, "pos": None, "zone": None}
        if with_price:
            p, pos, zone = price_range(code)
            row.update(price=p, pos=pos, zone=zone)
        rows.append(row)
    rows.sort(key=lambda r: r["days"])
    return rows


def earnings_schedule(codes, today=None):
    """決算カレンダー。[{code,name,date,days}] を近い順で返す(取れた銘柄のみ)。"""
    if today is None:
        today = dt.date.today()
    try:
        from universe import UNIVERSE
    except Exception:
        UNIVERSE = {}
    import yfinance as yf
    rows = []
    for code in codes:
        try:
            cal = yf.Ticker(code).calendar
            ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if not ed:
                continue
            dates = ed if isinstance(ed, (list, tuple)) else [ed]
            norm = []
            for d in dates:
                if hasattr(d, "date"):
                    d = d.date()
                if isinstance(d, dt.date):
                    norm.append(d)
            future = sorted([d for d in norm if d >= today])
            if not future:
                continue
            nd = future[0]
            rows.append({"code": code, "name": UNIVERSE.get(code, code.replace(".T", "")),
                         "date": nd, "days": (nd - today).days})
        except Exception:
            continue
    rows.sort(key=lambda r: r["days"])
    return rows
