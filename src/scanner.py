# scanner.py 【全銘柄スキャナー = 「今ここ！」を探す中核】
# universe.py の全銘柄を毎日チェックし、買いサインが点灯した銘柄を強い順に並べます。
#   ① 押し目      … 上昇トレンド中の一時的な下げ(RSIが低い)。安く仕込む狙い。
#   ② 急騰ブレイク … 上昇トレンド中に20日高値を出来高を伴って突破。勢いに乗る狙い。
# 実行: .\.venv\Scripts\python.exe src\scanner.py   (末尾に数字で先頭N銘柄に限定テスト)

import sys
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401
import yfinance as yf
from rich.console import Console
from rich.table import Table

from universe import UNIVERSE
from indicators import add_all_indicators
import config

console = Console()


def analyze_one(code, name, df):
    if df is None or df.empty or len(df) < 80:
        return None
    df = add_all_indicators(df)
    if df[["SMA25", "SMA75", "RSI"]].iloc[-1].isna().any():
        return None

    last = df.iloc[-1]
    close = float(last["Close"])
    rsi = float(last["RSI"])
    uptrend = bool(last["SMA25"] > last["SMA75"])

    recent_high = float(df["Close"].iloc[-21:-1].max())
    vol_avg = float(df["Volume"].iloc[-21:-1].mean())
    vol_today = float(last["Volume"])
    ret_20 = (close / float(df["Close"].iloc[-21]) - 1) * 100 if len(df) >= 21 else 0.0

    sig_type = None
    strength = 0.0
    if uptrend and rsi <= 42 and close > float(last["SMA75"]):
        s = 50 + (42 - rsi) * 1.5
        if s > strength:
            strength, sig_type = s, "押し目"
    if uptrend and close >= recent_high and vol_today >= vol_avg * 1.3:
        s = 50 + min(ret_20, 40)
        if s > strength:
            strength, sig_type = s, "急騰ブレイク"
    if sig_type is None:
        return None

    stop = close * (1 - config.STOP_LOSS_PCT / 100)
    target = close * (1 + config.TAKE_PROFIT_PCT / 100)
    is_jp = code.endswith(".T")
    affordable = (close * 100) <= 100_000 if is_jp else True

    return {"code": code, "name": name, "price": close, "rsi": rsi,
            "type": sig_type, "strength": round(strength, 1), "ret_20": round(ret_20, 1),
            "stop": stop, "target": target, "affordable": affordable, "is_jp": is_jp}


def scan(limit=None):
    codes = list(UNIVERSE.keys())
    if limit:
        codes = codes[:limit]
    data = yf.download(codes, period="1y", interval="1d", auto_adjust=True,
                       group_by="ticker", progress=False, threads=True)
    hits = []
    for code in codes:
        try:
            sub = (data[code] if len(codes) > 1 else data).dropna()
            r = analyze_one(code, UNIVERSE[code], sub)
        except Exception:
            continue
        if r:
            hits.append(r)
    hits.sort(key=lambda x: x["strength"], reverse=True)
    return hits


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    console.print("\n[bold cyan]🔎 全銘柄スキャナー 「今ここ！」候補[/bold cyan]")
    console.print(f"[dim]{limit or len(UNIVERSE)}銘柄をスキャン中...[/dim]\n")

    hits = scan(limit)
    if not hits:
        console.print("[yellow]今日はサイン点灯銘柄なし(様子見の相場)。[/yellow]\n")
        return

    table = Table(show_lines=False)
    for col, j in [("強さ", "right"), ("モード", "left"), ("銘柄", "left"),
                   ("株価", "right"), ("RSI", "right"), ("損切り", "right"),
                   ("利確", "right"), ("10万可", "center")]:
        table.add_column(col, justify=j, no_wrap=(col != "銘柄"))

    for h in hits[:config.SCAN_TOP_N]:
        mc = "green" if h["type"] == "押し目" else "magenta"
        cur = "" if h["is_jp"] else "$"
        table.add_row(f"{h['strength']:.0f}", f"[{mc}]{h['type']}[/{mc}]", h["name"],
                      f"{cur}{h['price']:,.0f}", f"{h['rsi']:.0f}",
                      f"{cur}{h['stop']:,.0f}", f"{cur}{h['target']:,.0f}",
                      "[green]○[/green]" if h["affordable"] else "[dim]×[/dim]")
    console.print(table)
    console.print(f"\n[dim]点灯{len(hits)}件中 上位{min(len(hits), config.SCAN_TOP_N)}件。"
                  f"○=10万円で買える目安。損切り{config.STOP_LOSS_PCT:.0f}%/利確{config.TAKE_PROFIT_PCT:.0f}%。"
                  f"※サイン=必勝ではない。[/dim]\n")


if __name__ == "__main__":
    main()
