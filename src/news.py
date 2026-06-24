# news.py
# 【ニュース収集ツール】
# Googleニュースの「RSS」という無料の仕組みを使って、銘柄に関するニュースを集めます。
# APIキーもお金も不要です。
#
# やること:
#   ① 銘柄名で検索したニュースの見出しを取得
#   ② 「前向きワード(増益・最高益…)」「後ろ向きワード(減益・赤字…)」で簡易判定
#   ③ DB(newsテーブル)に貯める  ＋  画面に表示
#
# 実行方法:
#   .\.venv\Scripts\python.exe src\news.py 8267.T      (イオン)
#   コード省略でイオンを対象にします。
#
# ※簡易判定はあくまで目安。最終判断は見出し本文を読んで行ってください。

import sys
import urllib.parse
import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)
import feedparser
from rich.console import Console
from rich.table import Table

from watchlist import WATCHLIST
import storage

console = Console()

# 簡易センチメント(雰囲気)判定用のワード。あとから自由に増やせます。
POSITIVE = ["増益", "最高益", "上方修正", "増配", "好調", "黒字", "上昇", "急騰",
            "過去最高", "改善", "拡大", "提携", "受注", "値上げ", "自社株買い"]
NEGATIVE = ["減益", "下方修正", "減配", "赤字", "不振", "下落", "急落", "減少",
            "悪化", "リコール", "不正", "訴訟", "業績悪化", "延期", "撤退"]

# 銘柄ごとの「まぎらわしい別企業・除外したいワード」。検索からも結果からも除く。
# 例: イオン → 米国のイオンキュー(IONQ)が混ざるので除外。
NOISE = {
    "イオン": ["イオンキュー", "IONQ", "イオンモール", "イオンファンタジー"],
}


def score_title(title: str) -> int:
    """見出しに前向き/後ろ向きワードが何個あるかで点数化。+なら好材料寄り。"""
    s = 0
    for w in POSITIVE:
        if w in title:
            s += 1
    for w in NEGATIVE:
        if w in title:
            s -= 1
    return s


def fetch_news(name: str, limit: int = 12):
    """Googleニュースのrssから、その銘柄のニュースを取得する。
    まぎらわしい別企業(NOISE)は、検索クエリと結果フィルタの両方で除外して精度を上げる。"""
    excludes = NOISE.get(name, [])

    # 検索クエリ: 銘柄名は完全一致("...")で縛り、ノイズ語は -語 で除外する
    query = f'"{name}" 株'
    for w in excludes:
        query += f" -{w}"
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    feed = feedparser.parse(url)

    items = []
    for e in feed.entries:
        title = e.get("title", "")
        # 念のため結果側でもノイズ語を含む見出しを弾く(二重の保険)
        if any(w in title for w in excludes):
            continue
        # 銘柄名そのものを含まない見出しも除外(関連性を担保)
        if name not in title:
            continue
        source = ""
        if e.get("source") and hasattr(e.source, "title"):
            source = e.source.title
        items.append({
            "title": title,
            "published": e.get("published", ""),
            "source": source,
            "link": e.get("link", ""),
            "sentiment": score_title(title),
        })
        if len(items) >= limit:
            break
    return items


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "8267.T"
    name = WATCHLIST.get(code, code.replace(".T", ""))

    console.print(f"\n[bold cyan]📰 {name}（{code}）のニュース[/bold cyan]\n")

    items = fetch_news(name)
    if not items:
        console.print("[yellow]ニュースが取得できませんでした[/yellow]")
        return

    storage.init_db()
    rows = [(code, it["published"], it["title"], it["source"], it["link"], it["sentiment"])
            for it in items]
    storage.save_news(rows)

    table = Table(show_lines=False)
    table.add_column("雰囲気", justify="center", no_wrap=True)
    table.add_column("見出し")
    table.add_column("媒体", style="dim", no_wrap=True)

    total = 0
    for it in items:
        s = it["sentiment"]
        total += s
        if s > 0:
            mark = "[green]＋好[/green]"
        elif s < 0:
            mark = "[red]－悪[/red]"
        else:
            mark = "[dim]・[/dim]"
        table.add_row(mark, it["title"], it["source"])

    console.print(table)

    # 全体の雰囲気
    if total > 0:
        mood = "[green]やや好材料が多い[/green]"
    elif total < 0:
        mood = "[red]やや悪材料が多い[/red]"
    else:
        mood = "[yellow]中立(目立った材料は少なめ)[/yellow]"
    console.print(f"\n  ニュース全体の雰囲気: {mood}（合計スコア {total:+d}）")
    console.print(f"  [dim]※DBのnewsテーブルに{len(items)}件保存しました[/dim]\n")


if __name__ == "__main__":
    main()
