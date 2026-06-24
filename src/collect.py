# collect.py
# 【データ収集の実行プログラム】
# 監視リストの全銘柄について:
#   ① 過去の株価をできるだけ長く取得(初回は数年ぶん)
#   ② pricesテーブルに保存(全履歴を蓄積)
#   ③ 指標・判定・ファンダを計算し、その日のsnapshotを保存
# を行います。これを毎日回すと、あなただけのデータがどんどん貯まります。
#
# 実行方法:
#   collect.bat をダブルクリック
#   または  .\.venv\Scripts\python.exe src\collect.py

import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)。yfinanceより先に。

import yfinance as yf
from rich.console import Console

from watchlist import WATCHLIST
from indicators import add_all_indicators
from signals import judge
import storage

console = Console()


def safe_div_yield(info, price):
    """配当利回り(%)を安全に計算する(deepdiveと同じ考え方)。"""
    rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
    if rate:
        return rate / price * 100
    dy = info.get("dividendYield")
    if dy is None:
        return None
    return dy if dy > 1 else dy * 100


def collect_one(code, name):
    """1銘柄ぶんを取得→保存し、その日のsnapshotを返す。"""
    # period="max" で取れるだけ過去をもらう(初回に一気に蓄積。2回目以降は重複上書き)
    df = yf.download(code, period="max", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty or len(df) < 80:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    saved = storage.save_prices(code, df)   # 全履歴をDBへ

    # 指標・判定
    dfi = add_all_indicators(df.copy())
    sig = judge(dfi)
    last_date = dfi.index[-1].strftime("%Y-%m-%d")

    # ファンダ(取れる範囲で)
    try:
        info = yf.Ticker(code).info
    except Exception:
        info = {}
    high_52 = float(df["Close"].tail(252).max())   # 直近約1年(252営業日)の高値
    low_52 = float(df["Close"].tail(252).min())
    pos = None if high_52 == low_52 else (sig["price"] - low_52) / (high_52 - low_52) * 100

    snap = {
        "code": code,
        "date": last_date,
        "name": name,
        "close": sig["price"],
        "rsi": sig["rsi"],
        "macd_hist": float(dfi.iloc[-1]["MACD_hist"]),
        "score": sig["score"],
        "verdict": sig["verdict"],
        "per": info.get("trailingPE"),
        "pbr": info.get("priceToBook"),
        "div_yield": safe_div_yield(info, sig["price"]),
        "pos_in_range": pos,
    }
    storage.save_snapshot(snap)
    return saved, snap


def main():
    storage.init_db()
    console.print("\n[bold cyan]🗄  データ収集を開始します[/bold cyan]\n")

    for code, name in WATCHLIST.items():
        try:
            result = collect_one(code, name)
        except Exception as e:
            console.print(f"[red]✗ {name}({code}) 失敗: {e}[/red]")
            continue
        if result is None:
            console.print(f"[yellow]- {name}({code}) データ不足でスキップ[/yellow]")
            continue
        saved, snap = result
        console.print(
            f"[green]✓[/green] {name}({code}) "
            f"履歴{saved}日分保存 / 最新 {snap['date']} "
            f"終値{snap['close']:,.0f}円 判定:{snap['verdict']}")

    # まとめ
    s = storage.db_summary()
    console.print("\n[bold]── データベースの現状 ──[/bold]")
    console.print(f"  株価データ: [bold]{s['price_rows']:,}[/bold] 行 "
                  f"（{s['price_codes']}銘柄 / {s['price_from']} 〜 {s['price_to']}）")
    console.print(f"  分析スナップショット: [bold]{s['snapshot_rows']:,}[/bold] 行")
    console.print(f"\n  保存先: [dim]{storage.DB_PATH}[/dim]\n")


if __name__ == "__main__":
    main()
