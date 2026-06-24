# deepdive.py
# 【1銘柄を深掘り分析するツール】
# テクニカル(チャートの形)だけでなく、
#   ・割安度: 今の株価は過去1年のレンジの中で「安い方」か「高い方」か
#   ・ファンダ: PER / PBR / 配当利回り など(取れる範囲で)
#   ・株主優待: 権利確定日や条件(銘柄ごとに登録)
# をまとめて表示します。「優待を一番安く仕込む」判断の材料にします。
#
# 実行方法(PowerShell):
#   .\.venv\Scripts\python.exe src\deepdive.py 8267.T
#   コードを省略するとイオン(8267)を分析します。

import sys
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)。yfinanceより先に。

import yfinance as yf
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from indicators import add_all_indicators
from signals import judge

console = Console()

# --- 株主優待カレンダー(必要な銘柄だけ手で登録していく) ---
# record_months: 権利確定する月(末日)。memo: 優待の内容メモ。
YUTAI = {
    "8267.T": {
        "name": "イオン",
        "record_months": [2, 8],   # 2月末・8月末が権利確定
        "min_shares": 100,
        "memo": "100株でオーナーズカード(買物1%キャッシュバック+感謝デー5%OFF)。"
                "権利付最終日(権利確定日の2営業日前)に100株保有が条件。",
    },
}


def position_in_range(price, low, high):
    """52週レンジの中で今の株価が何%の位置か。0%=年初来安値、100%=年初来高値。"""
    if high is None or low is None or high == low:
        return None
    return (price - low) / (high - low) * 100


def fmt(v, suffix="", pct=False):
    """値がNoneでも落ちないように整形する小道具。"""
    if v is None:
        return "—"
    if pct:
        return f"{v*100:.2f}%"
    if isinstance(v, float):
        return f"{v:,.2f}{suffix}"
    return f"{v:,}{suffix}"


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"

    t = yf.Ticker(code)
    try:
        info = t.info
    except Exception:
        info = {}

    df = yf.download(code, period="1y", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        console.print(f"[red]{code} のデータが取得できませんでした[/red]")
        return
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    df = add_all_indicators(df)
    sig = judge(df)

    name = info.get("shortName") or info.get("longName") or YUTAI.get(code, {}).get("name") or code
    price = sig["price"]

    # 52週(直近1年)の高値・安値。
    # ※必ず「分割調整済み」のdf(auto_adjust=True)から計算する。
    #   infoのfiftyTwoWeekHighは分割前の古い値が混ざることがあり、割安度を誤らせるため使わない。
    high_52 = float(df["Close"].max())
    low_52 = float(df["Close"].min())
    pos = position_in_range(price, low_52, high_52)

    # 配当利回りを安全に計算する。
    #   yfinameの dividendYield は「3.5(=%)」のことも「0.035(=小数)」のこともあり不安定。
    #   一番確実なのは 1株あたり配当(dividendRate) ÷ 株価 で自前計算すること。
    rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
    if rate:
        div_yield_pct = rate / price * 100
    else:
        dy = info.get("dividendYield")
        if dy is None:
            div_yield_pct = None
        elif dy > 1:          # すでに%表記(例 3.5)
            div_yield_pct = dy
        else:                 # 小数表記(例 0.035)
            div_yield_pct = dy * 100

    # ---- 見出し ----
    console.print()
    console.print(Panel.fit(f"[bold cyan]{name}（{code}）深掘り分析[/bold cyan]",
                            border_style="cyan"))

    # ---- 1) 今の株価と割安度 ----
    t1 = Table(title="① 株価と割安度（過去1年）", show_header=False, box=None)
    t1.add_row("現在値", f"[bold]{price:,.0f} 円[/bold]")
    t1.add_row("1年の安値〜高値", f"{low_52:,.0f} 〜 {high_52:,.0f} 円")
    if pos is not None:
        # 位置バー(■で視覚化)。左=安い、右=高い
        filled = int(round(pos / 5))
        bar = "[green]" + "■" * filled + "[/green]" + "[dim]" + "□" * (20 - filled) + "[/dim]"
        cheap = "安値圏(仕込み好機の可能性)" if pos <= 30 else ("高値圏(高づかみ注意)" if pos >= 70 else "中間")
        t1.add_row("レンジ内の位置", f"{bar} {pos:.0f}%（{cheap}）")
    console.print(t1)

    # ---- 2) ファンダメンタル ----
    t2 = Table(title="② ファンダメンタル（業績・割安の目安）", show_header=False, box=None)
    t2.add_row("PER（株価収益率/低いほど割安）", fmt(info.get("trailingPE"), "倍"))
    t2.add_row("PBR（株価純資産倍率/1倍が目安）", fmt(info.get("priceToBook"), "倍"))
    t2.add_row("配当利回り", f"{div_yield_pct:.2f}%" if div_yield_pct is not None else "—")
    mc = info.get("marketCap")
    t2.add_row("時価総額", fmt(mc/1e8, "億円") if mc else "—")
    console.print(t2)

    # ---- 3) テクニカル判定 ----
    t3 = Table(title="③ テクニカル（チャートの今の形）", show_header=False, box=None)
    color = {"買い": "bold green", "売り": "bold red", "様子見": "yellow"}[sig["verdict"]]
    t3.add_row("総合判定", f"[{color}]{sig['verdict']}[/{color}]（点数 {sig['score']:+d}）")
    t3.add_row("RSI", f"{sig['rsi']:.0f}")
    for r in sig["reasons"]:
        t3.add_row("", r)
    console.print(t3)

    # ---- 4) 株主優待(登録があれば) ----
    y = YUTAI.get(code)
    if y:
        months = "・".join(f"{m}月末" for m in y["record_months"])
        t4 = Table(title="④ 株主優待", show_header=False, box=None)
        t4.add_row("権利確定", months)
        t4.add_row("必要株数", f"{y['min_shares']}株以上")
        t4.add_row("内容", y["memo"])
        console.print(t4)

    console.print()


if __name__ == "__main__":
    main()
