# checks.py
# 【買う前の安全チェック集】
# 「買う瞬間の事故」を防ぐための判定をまとめたモジュール。
#   ・決算発表日の接近(またぎは±10%飛ぶことも)     → next_earnings()
#   ・流動性=売買代金(少ないと売りたい時に売れない)  → liquidity_20d()
#   ・高値からの下落率(押し目か崩壊かの物差し)       → drawdown()
#   ・ベータ/ボラ(市場よりどれだけ激しく動くか)      → volatility()
#   ・セクター集中(保有が同業種に偏っていないか)     → portfolio_sectors()
#   ・買う前チェックリスト(上を全部まとめて警告)     → precheck()
#
# 手元テスト:  .\.venv\Scripts\python.exe src\checks.py 6920.T

import warnings
warnings.simplefilter("ignore")

import datetime

# 流動性のしきい値: 1日平均売買代金がこの額を下回ると「⚠️流動性低め」
LIQUIDITY_WARN_YEN = 100_000_000        # 1億円/日
# 決算接近の警告日数
EARNINGS_WARN_DAYS = 7
# セクター集中の警告しきい値(評価額ベース)
SECTOR_WARN_RATIO = 0.5                 # 50%超で警告


def next_earnings(info, ticker=None):
    """次回の決算発表日を返す。(date, 残り日数) / 不明なら (None, None)。
    infoのearningsTimestampStartが過去日のことがあるので、未来の日付だけ採用。"""
    today = datetime.date.today()
    cands = []
    for k in ("earningsTimestampStart", "earningsTimestamp"):
        v = (info or {}).get(k)
        if v:
            try:
                cands.append(datetime.datetime.fromtimestamp(v).date())
            except Exception:
                pass
    if ticker is not None:
        try:
            cal = ticker.calendar
            for d in (cal.get("Earnings Date") or []) if isinstance(cal, dict) else []:
                if isinstance(d, datetime.datetime):
                    d = d.date()
                if isinstance(d, datetime.date):
                    cands.append(d)
        except Exception:
            pass
    future = sorted(d for d in cands if d >= today)
    if not future:
        return None, None
    d = future[0]
    return d, (d - today).days


def liquidity_20d(df):
    """直近20営業日の平均売買代金(円)。dfはClose/Volume必須。データ不足ならNone。"""
    if df is None or len(df) < 5 or "Volume" not in df:
        return None
    tail = df.tail(20)
    try:
        v = float((tail["Close"] * tail["Volume"]).mean())
        return v if v > 0 else None
    except Exception:
        return None


def drawdown(df, window=252):
    """直近{window}営業日(≒52週)の高値からの下落率(小数: 0.15=高値から15%下)。"""
    if df is None or len(df) < 5:
        return None
    tail = df.tail(window)
    try:
        hi = float(tail["Close"].max())
        cur = float(tail["Close"].iloc[-1])
        return (hi - cur) / hi if hi > 0 else None
    except Exception:
        return None


def volatility(df, window=60):
    """直近{window}日の日次リターンの標準偏差を年率換算(小数: 0.4=年率40%)。"""
    if df is None or len(df) < window // 2:
        return None
    try:
        r = df["Close"].tail(window).pct_change().dropna()
        return float(r.std()) * (252 ** 0.5)
    except Exception:
        return None


def sector_of(info):
    """セクター名(英語)。無ければ None。"""
    return (info or {}).get("sector") or None


def fmt_liq(v):
    """売買代金を読みやすく。"""
    if v is None:
        return "—"
    if v >= 1e12:
        return f"{v/1e12:.1f}兆円/日"
    if v >= 1e8:
        return f"{v/1e8:,.0f}億円/日"
    return f"{v/1e4:,.0f}万円/日"


def precheck(df, info, stop_set=None, budget_ratio=None):
    """買う前チェック。戻り値: warningsのリスト [{level:'warn'/'info', msg:str}, ...]。
    stop_set: 損切りラインを設定済みか(None=不明なら項目を出さない)。
    budget_ratio: この買いが総資産に占める割合(小数)。None=不明なら出さない。"""
    out = []

    ed, days = next_earnings(info)
    if days is not None and days <= EARNINGS_WARN_DAYS:
        out.append({"level": "warn",
                    "msg": f"⚠️ {days}日後({ed:%m/%d})に決算発表。またぎは株価が大きく動くことがあります"})
    elif ed is not None:
        out.append({"level": "info", "msg": f"🗓️ 次回決算: {ed:%m/%d}（{days}日後）"})

    liq = liquidity_20d(df)
    if liq is not None and liq < LIQUIDITY_WARN_YEN:
        out.append({"level": "warn",
                    "msg": f"⚠️ 流動性低め（売買代金 {fmt_liq(liq)}）。売りたい時に値が飛ぶことがあります"})

    dd = drawdown(df)
    if dd is not None and dd >= 0.3:
        out.append({"level": "warn",
                    "msg": f"⚠️ 52週高値から{dd*100:.0f}%下落中。押し目ではなく下落トレンドの可能性も"})

    beta = (info or {}).get("beta")
    if beta is not None and beta >= 1.5:
        out.append({"level": "info",
                    "msg": f"📉 ベータ{beta:.1f}＝市場平均の約{beta:.1f}倍動きやすい銘柄です（急落も大きい）"})

    if stop_set is False:
        out.append({"level": "warn", "msg": "⚠️ 損切りラインが未設定です。買う前に「いくらで諦めるか」を決めましょう"})

    if budget_ratio is not None and budget_ratio >= 0.3:
        out.append({"level": "warn",
                    "msg": f"⚠️ この買いだけで総資産の{budget_ratio*100:.0f}%。1銘柄への集中はリスクが高くなります"})

    return out


def portfolio_sectors(positions, info_getter, prices=None):
    """保有のセクター構成を返す。positions: {code: {name, shares, avg_cost}}。
    info_getter(code)->info辞書(キャッシュ推奨)。prices: {code: 現値}(無ければavg_costで概算)。
    戻り値: (構成list[{sector, value, ratio}], 警告str or None)。"""
    if not positions:
        return [], None
    vals = {}
    for code, pos in positions.items():
        try:
            info = info_getter(code) or {}
        except Exception:
            info = {}
        sec = info.get("sector") or "不明"
        px = (prices or {}).get(code) or pos.get("avg_cost", 0)
        vals[sec] = vals.get(sec, 0) + float(px) * int(pos.get("shares", 0))
    total = sum(vals.values())
    if total <= 0:
        return [], None
    out = sorted(({"sector": s, "value": v, "ratio": v / total} for s, v in vals.items()),
                 key=lambda x: -x["ratio"])
    warn = None
    top = out[0]
    if len(positions) >= 2 and top["ratio"] >= SECTOR_WARN_RATIO and top["sector"] != "不明":
        warn = (f"⚠️ 保有の{top['ratio']*100:.0f}%が「{top['sector']}」に集中しています。"
                "同業種は同時に下がりやすいので分散を意識しましょう")
    return out, warn


# セクター名の日本語補足(表示用)
SECTOR_JP = {
    "Technology": "テクノロジー", "Industrials": "資本財(機械等)",
    "Consumer Cyclical": "一般消費財", "Consumer Defensive": "生活必需品",
    "Healthcare": "ヘルスケア", "Financial Services": "金融",
    "Communication Services": "通信サービス", "Basic Materials": "素材",
    "Energy": "エネルギー", "Real Estate": "不動産", "Utilities": "公益",
}


def sector_jp(sec):
    if not sec:
        return "—"
    jp = SECTOR_JP.get(sec)
    return f"{jp}" if jp else sec


if __name__ == "__main__":
    import sys
    import _net  # noqa: F401
    import yfinance as yf

    code = sys.argv[1] if len(sys.argv) > 1 else "6920.T"
    t = yf.Ticker(code)
    info = t.info
    df = yf.download(code, period="1y", interval="1d", auto_adjust=True, progress=False)
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])

    ed, days = next_earnings(info, t)
    print(f"次回決算: {ed} ({days}日後)")
    print(f"売買代金20日平均: {fmt_liq(liquidity_20d(df))}")
    dd = drawdown(df)
    print(f"52週高値からの下落: {dd*100:.1f}%" if dd is not None else "DD: —")
    vol = volatility(df)
    print(f"ボラ(年率): {vol*100:.0f}%" if vol else "ボラ: —")
    print(f"ベータ: {info.get('beta')}")
    print(f"セクター: {sector_of(info)} ({sector_jp(sector_of(info))})")
    print("--- precheck ---")
    for w in precheck(df, info, stop_set=False, budget_ratio=0.4):
        print(" ", w["level"], w["msg"])
