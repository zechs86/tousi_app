# backtest_multi.py
# 【複数銘柄でまとめて検証】
# 1銘柄で勝てても「たまたま」かもしれない。
# 監視リストの全銘柄で各戦略を回し、平均で勝てるか=本物かを確かめます。
#
# 表の各セルは「その銘柄でのトータルリターン%」。一番下に平均と勝率を出します。
#
# 実行方法:
#   .\.venv\Scripts\python.exe src\backtest_multi.py 5     (過去5年)
#
# ※手数料・税金は未考慮。

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
from backtest_compare import evaluate

console = Console()


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    strat_names = list(ALL_STRATEGIES.keys())

    console.print(f"\n[bold cyan]🧪 複数銘柄バックテスト（過去{years}年・{len(WATCHLIST)}銘柄）[/bold cyan]")
    console.print("[dim]各セル=その銘柄のリターン%。下段に平均と『buy&holdに勝った率』。[/dim]\n")

    # results[strategy_name] = [各銘柄のリターン...]
    results = {name: [] for name in strat_names}
    bh_returns = []   # 銘柄ごとのbuy&holdリターン(勝率判定の基準)

    table = Table(show_lines=False)
    table.add_column("銘柄", no_wrap=True)
    for name in strat_names:
        # 表示用に名前を短縮
        short = name.replace("(基準)", "").replace("(従来)", "").replace("(改良①)", "①") \
                    .replace("(改良②)", "②").replace("(改良③)", "③")
        table.add_column(short, justify="right")

    for code, jname in WATCHLIST.items():
        df = yf.download(code, period=f"{years}y", interval="1d",
                         auto_adjust=True, progress=False)
        if df is None or df.empty or len(df) < 120:
            continue
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        dfi = add_all_indicators(df).dropna()
        if len(dfi) < 60:
            continue

        row = [jname]
        bh_ret = evaluate(dfi, ALL_STRATEGIES["buy&hold(基準)"](dfi))["return"]
        bh_returns.append(bh_ret)

        for name in strat_names:
            r = evaluate(dfi, ALL_STRATEGIES[name](dfi))["return"]
            results[name].append(r)
            color = "green" if r >= 0 else "red"
            row.append(f"[{color}]{r:+.0f}%[/{color}]")
        table.add_row(*row)

    # 平均行
    avg_row = ["[bold]平均[/bold]"]
    for name in strat_names:
        vals = results[name]
        avg = sum(vals) / len(vals) if vals else 0
        color = "green" if avg >= 0 else "red"
        avg_row.append(f"[bold {color}]{avg:+.0f}%[/bold {color}]")
    table.add_row(*avg_row)

    # 「buy&holdに勝った率」行
    win_row = ["[bold]勝率(対基準)[/bold]"]
    for name in strat_names:
        vals = results[name]
        wins = sum(1 for r, bh in zip(vals, bh_returns) if r > bh)
        rate = wins / len(vals) * 100 if vals else 0
        win_row.append(f"{rate:.0f}%")
    table.add_row(*win_row)

    console.print(table)
    console.print("\n[dim]①トレンド追従 ②RSI逆張り ③上昇中の押し目買い。"
                  "平均リターンが高く、勝率が高い戦略が本物。[/dim]\n")


if __name__ == "__main__":
    main()
