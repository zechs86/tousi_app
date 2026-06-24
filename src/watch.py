# watch.py
# 【毎日の判断ブリーフィング】
# 「情報を常に集めて、買いどころを教えてくれる」— あなたが最初に望んだ機能の実用版。
# 対象銘柄(既定:イオン)について、毎朝これ1つ見れば判断できるよう情報を集約します。
#   ・株価と割安度(1年レンジ内の位置)
#   ・トレンド(上昇/下降)と 改良③の判断(押し目買いゾーンか/待ちか)
#   ・ニュースの雰囲気
#   ・株主優待の権利付最終日までの残り日数
#   ・総合した「今日のアクション案」
#
# 実行方法:
#   watch.bat をダブルクリック   または
#   .\.venv\Scripts\python.exe src\watch.py 8267.T
#
# ※投資助言ではなく判断材料です。最終判断はご自身で。

import sys
import datetime as dt
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401
import yfinance as yf
from rich.console import Console
from rich.panel import Panel

from watchlist import WATCHLIST
from indicators import add_all_indicators
import news as news_mod

console = Console()

# 優待の権利確定月(末)。deepdive.pyのYUTAIと合わせる。
RECORD_MONTHS = {"8267.T": [2, 8]}


def last_business_day(year, month):
    """その月の最終営業日(土日を除く)を返す。※祝日は未考慮。"""
    if month == 12:
        d = dt.date(year, 12, 31)
    else:
        d = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    while d.weekday() >= 5:        # 5=土,6=日
        d -= dt.timedelta(days=1)
    return d


def minus_business_days(d, n):
    """営業日でn日前を返す。※祝日は未考慮。"""
    while n > 0:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def next_kenri_date(code, today):
    """次の『権利付最終日』(=権利確定日の2営業日前)を返す。優待登録がなければ(None,None)。"""
    months = RECORD_MONTHS.get(code)
    if not months:
        return None, None
    candidates = []
    for y in (today.year, today.year + 1):
        for m in months:
            record = last_business_day(y, m)            # 権利確定日(最終営業日)
            kenri = minus_business_days(record, 2)      # 権利付最終日
            if kenri >= today:
                candidates.append((kenri, record))
    candidates.sort()
    return candidates[0] if candidates else (None, None)


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"
    name = WATCHLIST.get(code, code.replace(".T", ""))
    today = dt.date.today()

    df = yf.download(code, period="1y", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        console.print("[red]データ取得失敗[/red]")
        return
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    dfi = add_all_indicators(df)
    last = dfi.iloc[-1]

    price = float(last["Close"])
    low_52, high_52 = float(df["Close"].min()), float(df["Close"].max())
    pos = (price - low_52) / (high_52 - low_52) * 100 if high_52 != low_52 else 50

    # トレンド判定(改良③のベース): SMA25 > SMA75 なら上昇トレンド
    uptrend = bool(last["SMA25"] > last["SMA75"])
    rsi = float(last["RSI"])

    # 改良③のシグナル: 上昇トレンド中にRSI<=40の押し目 = 買いゾーン
    if uptrend and rsi <= 40:
        action_signal = ("buy", "[bold green]★ 押し目買いゾーン[/bold green]（上昇トレンド中の一時的な下げ）")
    elif uptrend:
        action_signal = ("hold", "[green]上昇トレンド継続[/green]（押し目=RSI40以下を待つか、分割で打診買い）")
    else:
        action_signal = ("wait", "[yellow]下降トレンド → まだ待ち[/yellow]（落ちるナイフ。上昇転換を待つのが規律）")

    # ニュースの雰囲気
    try:
        items = news_mod.fetch_news(name, limit=8)
        news_score = sum(it["sentiment"] for it in items)
    except Exception:
        items, news_score = [], 0
    news_mood = ("[green]やや好材料[/green]" if news_score > 0
                 else "[red]やや悪材料[/red]" if news_score < 0
                 else "[yellow]中立[/yellow]")

    # 優待の残り日数
    kenri, record = next_kenri_date(code, today)

    # ---- 表示 ----
    console.print()
    console.print(Panel.fit(f"[bold cyan]📋 {name}（{code}） 今日のブリーフィング  {today}[/bold cyan]",
                            border_style="cyan"))

    bar_n = int(round(pos / 5))
    bar = "[green]" + "■" * bar_n + "[/green]" + "[dim]" + "□" * (20 - bar_n) + "[/dim]"
    cheap = "安値圏" if pos <= 30 else ("高値圏" if pos >= 70 else "中間")

    lines = []
    lines.append(f"現在値        : [bold]{price:,.0f} 円[/bold]")
    lines.append(f"1年レンジ位置 : {bar} {pos:.0f}%（{cheap}）  安値{low_52:,.0f}〜高値{high_52:,.0f}")
    lines.append(f"トレンド      : {'[green]上昇[/green]' if uptrend else '[red]下降[/red]'}（SMA25{'>' if uptrend else '<'}SMA75） / RSI {rsi:.0f}")
    lines.append(f"ニュース雰囲気: {news_mood}（スコア {news_score:+d}）")
    if kenri:
        days_left = (kenri - today).days
        lines.append(f"優待権利       : 権利付最終日 [bold]{kenri}[/bold]（あと[bold]{days_left}日[/bold]）/ 確定 {record}")
    console.print("\n".join(lines))

    console.print()
    console.print(Panel.fit(action_signal[1], title="今日のアクション案", border_style="magenta"))

    # 優待向けの一言
    if kenri:
        days_left = (kenri - today).days
        if action_signal[0] == "wait":
            console.print(f"[dim]→ 優待狙い: 権利付最終日まで{days_left}日。まだ余裕。下げ止まり→上昇転換を待ち、"
                          f"転換後に分割買いで100株を目標。[/dim]")
        else:
            console.print(f"[dim]→ 優待狙い: 押し目/上昇基調。100株を数回に分けて仕込む好機。"
                          f"権利付最終日({kenri})までに揃える。[/dim]")

    # 主要ニュース3本
    if items:
        console.print("\n[bold]最近のニュース[/bold]")
        for it in items[:3]:
            console.print(f"  ・{it['title']}")
    console.print()


if __name__ == "__main__":
    main()
