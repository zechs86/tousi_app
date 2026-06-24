# backtest_compare.py
# 【戦略の比較バックテスト】
# strategies.py の複数戦略を、同じ銘柄・同じ期間で一斉に過去検証し、表で比べます。
# 「どの戦略が buy&hold に勝てるのか?」を一目で分かるようにするのが目的。
#
# 評価する数字:
#   リターン   … 期間トータルで何%増えたか(大きいほど良い)
#   最大下落   … 途中で最大どれだけ含み損を抱えたか(0に近いほど精神的にラク=良い)
#   投資日数%  … 全期間のうち何%の日を株を持って過ごしたか
#   売買回数   … 何回エントリーしたか(多すぎると手数料負け)
#
# 実行方法:
#   .\.venv\Scripts\python.exe src\backtest_compare.py 8267.T 5
#   コード省略でイオン、年数省略で5年。
#
# ※手数料・税金・スリッページは未考慮(戦略の素の比較)。

import sys
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401
import yfinance as yf
from rich.console import Console
from rich.table import Table

from watchlist import WATCHLIST
from indicators import add_all_indicators
from strategies import ALL_STRATEGIES

console = Console()


def evaluate(dfi, position):
    """ポジション(0/1の系列)から成績を計算する。
    今日のポジションは『前日までの情報』で決め、当日のリターンを受け取る(未来を見ない)。"""
    daily_ret = dfi["Close"].pct_change().fillna(0)
    strat_ret = position.shift(1).fillna(0) * daily_ret      # 前日のポジションで当日の値動きを取る
    equity = (1 + strat_ret).cumprod()

    total_return = (equity.iloc[-1] - 1) * 100
    drawdown = (equity / equity.cummax() - 1).min() * 100    # 最大ドローダウン(マイナス)
    days_in = position.mean() * 100
    trades = int((position.diff() == 1).sum())               # 0→1の回数=買った回数
    return {
        "return": total_return,
        "drawdown": drawdown,
        "days_in": days_in,
        "trades": trades,
    }


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    name = WATCHLIST.get(code, code.replace(".T", ""))

    df = yf.download(code, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty or len(df) < 120:
        console.print("[red]データ不足[/red]")
        return
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    dfi = add_all_indicators(df).dropna()    # 指標が揃ってからの期間で比較

    console.print(f"\n[bold cyan]🧪 戦略比較バックテスト: {name}（{code}） 過去{years}年[/bold cyan]")
    console.print("[dim]※手数料・税金は未考慮。リターン大・最大下落小 が良い戦略。[/dim]\n")

    # buy&holdのリターンを基準として先に計算
    bh = evaluate(dfi, ALL_STRATEGIES["buy&hold(基準)"](dfi))
    bh_ret = bh["return"]

    table = Table(show_lines=False)
    table.add_column("戦略")
    table.add_column("リターン", justify="right")
    table.add_column("最大下落", justify="right")
    table.add_column("投資日数%", justify="right")
    table.add_column("売買回数", justify="right")
    table.add_column("基準比", justify="right")

    for label, func in ALL_STRATEGIES.items():
        res = evaluate(dfi, func(dfi))
        ret_color = "green" if res["return"] >= 0 else "red"
        diff = res["return"] - bh_ret
        if label.startswith("buy&hold"):
            diff_str = "[dim]—基準—[/dim]"
        else:
            dc = "green" if diff >= 0 else "red"
            diff_str = f"[{dc}]{diff:+.1f}%[/{dc}]"
        table.add_row(
            label,
            f"[{ret_color}]{res['return']:+.1f}%[/{ret_color}]",
            f"[red]{res['drawdown']:.1f}%[/red]",
            f"{res['days_in']:.0f}%",
            f"{res['trades']}回",
            diff_str,
        )
    console.print(table)
    console.print("\n[dim]「基準比」が緑(プラス)の戦略が buy&hold に勝った戦略です。[/dim]\n")


if __name__ == "__main__":
    main()
