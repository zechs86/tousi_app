# fundamentals.py
# 【財務データのまとめ役】
# yfinance から「財務指標(ROE・利益率など)」と「バランスシート/損益計算書の5期推移」を
# 取り出して、ダッシュボード表示とAI分析の両方で使える素直な辞書にして返す。
#
# 方針:
#   ・extra_metrics(info)   … 既に取得済みの .info 辞書から計算/抽出(追加通信ゼロ)。
#   ・financial_summary(code)… balance_sheet / financials を別途取得(銘柄ごと1〜2秒)。
#   ・日本株は項目が欠けることが多いので、取れない値は None。呼び出し側で「—」表示。
#
# 手元テスト:  .\.venv\Scripts\python.exe src\fundamentals.py 7203.T

import warnings
warnings.simplefilter("ignore")


# ---- .info から取れる財務指標(追加通信なし) ----
def extra_metrics(info):
    """yfinanceの .info 辞書から、収益性・健全性の指標を取り出す。
    戻り値はすべて素の数値(比率は小数: 0.10=10%) または None。"""
    info = info or {}

    def g(*keys):
        for k in keys:
            v = info.get(k)
            if v not in (None, "", 0) or (v == 0 and k in info):
                if v is not None and v != "":
                    return v
        return None

    return {
        "roe": info.get("returnOnEquity"),            # 自己資本利益率(稼ぐ力/効率)
        "roa": info.get("returnOnAssets"),            # 総資産利益率
        "op_margin": info.get("operatingMargins"),    # 営業利益率
        "net_margin": info.get("profitMargins"),      # 純利益率
        "gross_margin": info.get("grossMargins"),     # 粗利率
        "payout": info.get("payoutRatio"),            # 配当性向(配当の無理のなさ)
        "debt_to_equity": info.get("debtToEquity"),   # D/E(%表記。負債/自己資本)
        "current_ratio": info.get("currentRatio"),    # 流動比率(短期の支払い余力)
        "quick_ratio": info.get("quickRatio"),        # 当座比率
        "op_cashflow": info.get("operatingCashflow"), # 営業キャッシュフロー
        "free_cashflow": info.get("freeCashflow"),    # フリーキャッシュフロー
        "total_cash": info.get("totalCash"),          # 手元現金
        "total_debt": info.get("totalDebt"),          # 有利子負債
        "bps": info.get("bookValue"),                 # 1株純資産(BPS)
        "forward_pe": info.get("forwardPE"),          # 予想PER
        "peg": info.get("pegRatio"),                  # PEG(成長を加味した割安度)
    }


# balance_sheet / financials の行ラベル候補(yfinanceの表記ゆれ対策)
_BS_ASSETS = ["Total Assets"]
_BS_LIAB = ["Total Liabilities Net Minority Interest", "Total Liabilities"]
_BS_EQUITY = ["Stockholders Equity", "Common Stock Equity",
              "Total Equity Gross Minority Interest"]
_FIN_REVENUE = ["Total Revenue", "Operating Revenue"]
_FIN_OP = ["Operating Income"]
_FIN_NET = ["Net Income", "Net Income Common Stockholders"]


def _row(frame, labels):
    """財務フレーム(index=項目名, columns=各期)から、候補ラベルの最初に当たる行を返す。
    無ければ None。戻り値は {期文字列: 値 or None} の dict。"""
    if frame is None or getattr(frame, "empty", True):
        return None
    for lbl in labels:
        if lbl in frame.index:
            s = frame.loc[lbl]
            out = {}
            for col, val in s.items():
                key = col.strftime("%Y/%m") if hasattr(col, "strftime") else str(col)
                try:
                    out[key] = None if val is None or (val != val) else float(val)
                except Exception:
                    out[key] = None
            return out
    return None


def financial_summary(code, years=5, ticker=None):
    """1銘柄のBS/PLを取得し、最大 years 期分のサマリを返す。
    戻り値 dict:
      periods: ['2026/03', ...]   新しい期が先頭
      assets/liabilities/equity/equity_ratio/revenue/op_income/net_income:
        それぞれ periods と同じ並びの list(値 or None)。equity_ratio は小数。
    取得失敗時は None。"""
    try:
        import yfinance as yf
        t = ticker or yf.Ticker(code)
        bs = t.balance_sheet
        fin = t.financials
    except Exception:
        return None

    assets = _row(bs, _BS_ASSETS)
    liab = _row(bs, _BS_LIAB)
    equity = _row(bs, _BS_EQUITY)
    revenue = _row(fin, _FIN_REVENUE)
    op_inc = _row(fin, _FIN_OP)
    net_inc = _row(fin, _FIN_NET)

    # 期(列)を新しい順に集める。BS優先、無ければPLから。
    period_keys = []
    for src in (assets, equity, liab, revenue):
        if src:
            period_keys = list(src.keys())
            break
    if not period_keys:
        return None
    period_keys = sorted(period_keys, reverse=True)[:years]

    def pick(d):
        return [d.get(p) if d else None for p in period_keys]

    a = pick(assets)
    eq = pick(equity)
    eqr = []
    for av, ev in zip(a, eq):
        eqr.append((ev / av) if (av and ev is not None and av != 0) else None)

    return {
        "periods": period_keys,
        "assets": a,
        "liabilities": pick(liab),
        "equity": eq,
        "equity_ratio": eqr,            # 自己資本比率(小数: 0.4=40%)
        "revenue": pick(revenue),
        "op_income": pick(op_inc),
        "net_income": pick(net_inc),
    }


# ---- 表示用の整形ヘルパー(呼び出し側で使う) ----
def fmt_money(v):
    """円の大きな金額を 兆/億 表記に。None や 0 は '—'。マイナスも対応。"""
    if v in (None, 0):
        return "—"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return f"{sign}{a/1e12:.2f}兆円"
    if a >= 1e8:
        return f"{sign}{a/1e8:,.0f}億円"
    if a >= 1e4:
        return f"{sign}{a/1e4:,.0f}万円"
    return f"{sign}{a:,.0f}円"


def fmt_pct(v, decimals=1):
    """小数の比率(0.10)を '10.0%' に。None は '—'。"""
    if v is None:
        return "—"
    return f"{v*100:.{decimals}f}%"


if __name__ == "__main__":
    import sys
    import _net  # noqa: F401  日本語フォルダ対策(SSL)。yfinanceより先に。
    import yfinance as yf

    code = sys.argv[1] if len(sys.argv) > 1 else "7203.T"
    info = {}
    try:
        info = yf.Ticker(code).info
    except Exception:
        pass
    print("=== extra_metrics ===")
    for k, v in extra_metrics(info).items():
        print(f"  {k:14} = {v}")
    print("=== financial_summary ===")
    fs = financial_summary(code)
    if not fs:
        print("  (取得できませんでした)")
    else:
        print("  期:", fs["periods"])
        for p, a, l, e, r in zip(fs["periods"], fs["assets"], fs["liabilities"],
                                 fs["equity"], fs["equity_ratio"]):
            print(f"  {p}  総資産 {fmt_money(a):>10}  総負債 {fmt_money(l):>10}  "
                  f"自己資本 {fmt_money(e):>10}  自己資本比率 {fmt_pct(r)}")
