# backtest.py
# 【バックテスト＝過去検証】
# 「買いサインで買い、売りサインで売る」を過去のデータで実際にやってみて、
# お金が増えたか/減ったかを検証します。
# これをやらずに自動売買を始めるのが一番危険。必ずここで戦略の実力を測ります。
#
# 比較相手は「buy&hold(最初に買ってずっと持つ)」。
# 戦略がbuy&holdに勝てないなら、わざわざ売買する意味は薄い、という判断材料になります。
#
# 実行方法:
#   .\.venv\Scripts\python.exe src\backtest.py 8267.T
#   コード省略でイオン。第2引数で期間(年)を指定できる: ... 8267.T 5
#
# ※注意: 手数料・税金・スリッページ(約定ズレ)は簡易化のため未考慮。
#         単元(100株単位)も無視し「全額投資」で戦略の素の実力を測ります。

import sys
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)
import yfinance as yf
from rich.console import Console
from rich.table import Table

from watchlist import WATCHLIST
from indicators import add_all_indicators
from signals import judge

console = Console()


def run_backtest(code, years=5, initial=1_000_000):
    df = yf.download(code, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty or len(df) < 120:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    dfi = add_all_indicators(df)

    cash = initial          # 現金
    shares = 0.0            # 保有株数
    entry_price = 0.0       # 買った時の値段(勝ち負け判定用)
    trades = []             # 1回ごとの売買結果(損益率)
    start = 80              # 指標が安定するまで待つ

    for i in range(start, len(dfi) - 1):
        sig = judge(dfi.iloc[:i + 1])           # その日までの情報だけで判定(未来は見ない)
        next_open = float(dfi.iloc[i + 1]["Open"])  # 売買は「翌日の寄り付き」で約定とする

        if sig["verdict"] == "買い" and shares == 0:
            shares = cash / next_open            # 全額で買う
            cash = 0.0
            entry_price = next_open
        elif sig["verdict"] == "売り" and shares > 0:
            cash = shares * next_open            # 全部売る
            ret = (next_open - entry_price) / entry_price
            trades.append(ret)
            shares = 0.0

    # 最終日に持っていたら時価で清算
    final_price = float(dfi.iloc[-1]["Close"])
    equity = cash + shares * final_price
    if shares > 0:
        trades.append((final_price - entry_price) / entry_price)

    # buy&hold(最初に全額買ってずっと持つ)
    first_price = float(dfi.iloc[start]["Open"])
    bh_equity = initial / first_price * final_price

    wins = [t for t in trades if t > 0]
    result = {
        "code": code,
        "years": years,
        "n_trades": len(trades),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
        "strategy_return": (equity / initial - 1) * 100,
        "buyhold_return": (bh_equity / initial - 1) * 100,
        "equity": equity,
        "bh_equity": bh_equity,
        "avg_win": (sum(wins) / len(wins) * 100) if wins else 0.0,
        "losses": [t for t in trades if t <= 0],
    }
    return result


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    name = WATCHLIST.get(code, code.replace(".T", ""))

    console.print(f"\n[bold cyan]🧪 バックテスト: {name}（{code}） 過去{years}年[/bold cyan]")
    console.print("[dim]※手数料・税金は未考慮。戦略の素の実力を見る簡易版です。[/dim]\n")

    r = run_backtest(code, years)
    if r is None:
        console.print("[red]データ不足でテストできませんでした[/red]")
        return

    losses = r["losses"]
    avg_loss = (sum(losses) / len(losses) * 100) if losses else 0.0

    t = Table(show_header=False, box=None)
    t.add_row("売買した回数", f"{r['n_trades']} 回")
    t.add_row("勝率", f"{r['win_rate']:.1f}%")
    t.add_row("勝った時の平均", f"[green]+{r['avg_win']:.1f}%[/green]")
    t.add_row("負けた時の平均", f"[red]{avg_loss:.1f}%[/red]")
    t.add_row("", "")
    sc = "green" if r["strategy_return"] >= 0 else "red"
    bc = "green" if r["buyhold_return"] >= 0 else "red"
    t.add_row("[bold]この戦略の成績[/bold]", f"[{sc}]{r['strategy_return']:+.1f}%[/{sc}]  （{r['equity']:,.0f}円）")
    t.add_row("ずっと持ってた場合", f"[{bc}]{r['buyhold_return']:+.1f}%[/{bc}]  （{r['bh_equity']:,.0f}円）")
    console.print(t)

    # 総評
    diff = r["strategy_return"] - r["buyhold_return"]
    console.print()
    if r["n_trades"] < 3:
        console.print("[yellow]判定: 売買回数が少なすぎて評価不能。期間を延ばすか戦略を調整しましょう。[/yellow]")
    elif diff > 0:
        console.print(f"[green]判定: 戦略がbuy&holdに {diff:+.1f}% 勝っています。有望。[/green]")
    else:
        console.print(f"[yellow]判定: 戦略はbuy&holdに {diff:+.1f}% 負け。ルール改良の余地あり。[/yellow]")
    console.print("[dim]※1銘柄・1期間の結果は“たまたま”の可能性あり。複数銘柄・複数期間で確かめるのが大事。[/dim]\n")


if __name__ == "__main__":
    main()
