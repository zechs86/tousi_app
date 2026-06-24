# main.py
# 【Phase 1 のメインプログラム】
# やること: 監視リストの日本株を1つずつ
#   ① 株価データをネットから取得 (yfinance)
#   ② テクニカル指標を計算 (indicators.py)
#   ③ 買い/売り/様子見を判定 (signals.py)
#   ④ 結果を見やすい表で画面に表示 (rich)
#
# 実行方法(PowerShellで):
#   cd "C:\Users\k_nak\OneDrive\デスクトップ\tousi_app"
#   .\.venv\Scripts\python.exe src\main.py

import warnings
warnings.simplefilter("ignore")          # 細かい警告メッセージを非表示にして見やすく

import _net  # noqa: F401  ← 日本語フォルダ対策(SSL証明書)。yfinanceより先に読み込む

import yfinance as yf
from rich.console import Console
from rich.table import Table

from watchlist import WATCHLIST
from indicators import add_all_indicators
from signals import judge

console = Console()


def analyze_one(code: str):
    """1銘柄ぶんのデータを取得→指標計算→判定して結果を返す。"""
    # 過去6か月ぶんの日足(1日1本)データを取得
    df = yf.download(code, period="6mo", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty or len(df) < 80:
        return None  # データが取れない/少なすぎる銘柄はスキップ

    # yfinanceは列が階層になることがあるので平らにする
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    df = add_all_indicators(df)   # 指標を計算
    result = judge(df)            # 買い/売り判定
    return result


def main():
    console.print("\n[bold cyan]📊 日本株テクニカル分析 (Phase 1: サイン表示)[/bold cyan]")
    console.print("[dim]※これは投資助言ではなく、あなたの判断材料です。注文は楽天証券で手動で行ってください。[/dim]\n")

    table = Table(show_lines=True)
    table.add_column("コード", style="cyan", no_wrap=True)
    table.add_column("銘柄名")
    table.add_column("株価", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("点数", justify="right")
    table.add_column("判定", justify="center")
    table.add_column("理由")

    # 判定ごとの色分け
    color = {"買い": "bold green", "売り": "bold red", "様子見": "yellow"}

    buy_list, sell_list = [], []

    for code, name in WATCHLIST.items():
        console.print(f"[dim]取得中: {name} ({code}) ...[/dim]")
        try:
            r = analyze_one(code)
        except Exception as e:
            console.print(f"[red]  エラー: {e}[/red]")
            continue
        if r is None:
            console.print(f"[red]  データ不足のためスキップ[/red]")
            continue

        verdict = r["verdict"]
        v_colored = f"[{color[verdict]}]{verdict}[/{color[verdict]}]"
        reasons_text = "\n".join(r["reasons"])
        table.add_row(
            code, name,
            f"{r['price']:,.0f}円",
            f"{r['rsi']:.0f}",
            f"{r['score']:+d}",
            v_colored,
            reasons_text,
        )
        if verdict == "買い":
            buy_list.append(name)
        elif verdict == "売り":
            sell_list.append(name)

    console.print()
    console.print(table)

    # まとめ
    console.print("\n[bold]── 今日の注目 ──[/bold]")
    console.print(f"  🟢 買いサイン: {', '.join(buy_list) if buy_list else 'なし'}")
    console.print(f"  🔴 売りサイン: {', '.join(sell_list) if sell_list else 'なし'}")
    console.print()


if __name__ == "__main__":
    main()
