# history.py
# 【タイムライン・ビューア】
# DBに貯めた「ニュース」と「株価」を日付で結びつけて、
# 『この材料が出た後、株価はどう動いたか』を振り返るツールです。
#
# 表示するもの:
#   ニュースの日付 / 雰囲気(＋好・－悪) / 見出し / その後5営業日の値動き
#
# ※Googleニュースは最近の分しか取れないため、過去にさかのぼった収集は不可。
#   でも news.py や watch.py / 自動収集を回すほど、ここに履歴が貯まっていきます。
#
# 実行方法:
#   .\.venv\Scripts\python.exe src\history.py 8267.T

import sys
from email.utils import parsedate_to_datetime
import warnings
warnings.simplefilter("ignore")

from rich.console import Console
from rich.table import Table

from watchlist import WATCHLIST
import storage

console = Console()


def load_prices(code):
    """DBのpricesから {日付(YYYY-MM-DD): 終値} と、日付の並び を返す。"""
    conn = storage.connect()
    cur = conn.cursor()
    cur.execute("SELECT date, close FROM prices WHERE code=? ORDER BY date", (code,))
    rows = cur.fetchall()
    conn.close()
    closes = {d: c for d, c in rows}
    dates = [d for d, _ in rows]
    return closes, dates


def price_move_after(closes, dates, news_date, ndays=5):
    """ニュース日(以降で最初にある営業日)の終値と、そのn営業日後の終値の変化率(%)を返す。"""
    # news_date 以降で最初に存在する取引日を探す
    base_idx = None
    for i, d in enumerate(dates):
        if d >= news_date:
            base_idx = i
            break
    if base_idx is None or base_idx + ndays >= len(dates):
        return None, None
    p0 = closes[dates[base_idx]]
    p1 = closes[dates[base_idx + ndays]]
    if p0 == 0:
        return None, None
    return (p1 - p0) / p0 * 100, dates[base_idx]


def load_news(code):
    """DBのnewsから (日付, 見出し, 雰囲気) を新しい順に返す。"""
    conn = storage.connect()
    cur = conn.cursor()
    cur.execute("SELECT published, title, sentiment FROM news WHERE code=?", (code,))
    rows = cur.fetchall()
    conn.close()
    out = []
    for published, title, sentiment in rows:
        # RSSの日付文字列(例 'Tue, 10 Jun 2026 ...')をYYYY-MM-DDに変換
        date_str = None
        try:
            dt = parsedate_to_datetime(published)
            date_str = dt.strftime("%Y-%m-%d")
        except Exception:
            date_str = None
        out.append({"date": date_str, "title": title, "sentiment": sentiment})
    # 日付があるものを新しい順に
    out.sort(key=lambda x: x["date"] or "", reverse=True)
    return out


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"
    name = WATCHLIST.get(code, code.replace(".T", ""))

    console.print(f"\n[bold cyan]🕒 {name}（{code}） ニュース×株価 タイムライン[/bold cyan]")
    console.print("[dim]『この材料の後、株価はどう動いたか』を振り返ります（データが貯まるほど充実）。[/dim]\n")

    closes, dates = load_prices(code)
    news = load_news(code)

    if not news:
        console.print("[yellow]この銘柄のニュースはまだDBにありません。"
                      "先に  src\\news.py  を実行して貯めてください。[/yellow]\n")
        return

    table = Table(show_lines=False)
    table.add_column("日付", no_wrap=True)
    table.add_column("雰囲気", justify="center", no_wrap=True)
    table.add_column("見出し")
    table.add_column("5営業日後", justify="right", no_wrap=True)

    for n in news:
        d = n["date"] or "—"
        s = n["sentiment"]
        mark = "[green]＋好[/green]" if s > 0 else ("[red]－悪[/red]" if s < 0 else "[dim]・[/dim]")

        move_str = "—"
        if n["date"] and closes:
            move, base = price_move_after(closes, dates, n["date"])
            if move is not None:
                color = "green" if move >= 0 else "red"
                move_str = f"[{color}]{move:+.1f}%[/{color}]"
        table.add_row(d, mark, n["title"], move_str)

    console.print(table)
    console.print(f"\n[dim]※「5営業日後」が — の行は、まだその先の株価が無い(最近すぎる)等。"
                  f"毎日収集を続けると埋まっていきます。[/dim]\n")


if __name__ == "__main__":
    main()
