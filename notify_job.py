# notify_job.py
# 【自動通知ジョブ】GitHub Actions が朝・夜に自動実行します(PC不要)。
#   全銘柄をスキャン → 「今ここ！」候補の上位を ntfy でスマホに1通にまとめて通知。
#
# 手元テスト:  .\.venv\Scripts\python.exe notify_job.py
# 朝/夜の文言を変えたい時は、環境変数 RUN_LABEL に "朝" や "夜" を入れて実行。

import os
import sys
import warnings

warnings.simplefilter("ignore")

# src/ の中のモジュール(scanner, notify など)を import できるようにする
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import config
from scanner import scan
from notify import send_push
from risk import detect_risks
import ai_analysis


def build_message(hits):
    """買いサインを、スマホで読みやすくまとめる。"""
    top = hits[: config.SCAN_TOP_N]
    lines = []
    for h in top:
        cur = "" if h["is_jp"] else "$"
        mark = "🟢" if h["type"] == "押し目" else "🚀"
        afford = "✅" if h["affordable"] else "⚠️"
        lines.append(
            f"{mark}{h['name']} {h['type']}(強{h['strength']:.0f})\n"
            f"　{cur}{h['price']:,.0f}／損切{cur}{h['stop']:,.0f}・利確{cur}{h['target']:,.0f} {afford}"
        )
    return "\n".join(lines)


def build_risk_message(risks):
    """急変・下落で要注意の銘柄をまとめる。"""
    lines = []
    for r in risks[: config.SCAN_TOP_N]:
        cur = "" if r["is_jp"] else "$"
        lines.append(f"🔻{r['name']} {r['reason']}（{cur}{r['price']:,.0f}）")
    return "\n".join(lines)


def main():
    label = os.environ.get("RUN_LABEL", "").strip()
    prefix = f"【{label}のチェック】" if label else "【自動チェック】"

    print("スキャン中...")
    hits = scan()
    print("リスク検知中...")
    try:
        risks = detect_risks()
    except Exception as e:
        print("リスク検知エラー:", e)
        risks = []

    parts = [prefix.rstrip("】") + "】"]

    if hits:
        n = min(len(hits), config.SCAN_TOP_N)
        parts.append(f"\n🟢 買い候補 {len(hits)}件中 上位{n}件\n{build_message(hits)}")
        tags = "chart_with_upwards_trend"
    else:
        parts.append("\n🟢 買いサイン点灯なし（様子見）")
        tags = "coffee"

    if risks:
        parts.append(f"\n⚠️ 急変・下落で要注意 {len(risks)}件\n{build_risk_message(risks)}")
        tags = "warning"

    # AIによる一言総括(APIキーがある時だけ)
    ai = ai_analysis.comment_on_scan(hits, risks)
    if ai:
        parts.append(f"\n🤖 {ai}")

    parts.append("\n※サイン/警告=必勝ではありません。最終判断はご自身で。")
    msg = "\n".join(parts)
    # ntfyの本文上限(約4096バイト)対策。日本語は1文字3バイトなので余裕をみて1100文字で打ち切る。
    if len(msg) > 1100:
        msg = msg[:1100] + "…(省略)"
    title = f"Tousi: buy{len(hits)} / risk{len(risks)}"  # ntfyのTitleは英数字のみ

    # トピックは環境変数(GitHub Secrets)で上書き可。無ければ config.py の値を使う。
    # Secretに改行や空白が混じってもURLが壊れないよう strip する。
    topic = (os.environ.get("NTFY_TOPIC") or "").strip() or None
    ok = send_push(msg, title=title, tags=tags, priority="default", topic=topic)
    print("通知 送信成功" if ok else "通知 送信失敗")
    # GitHub Actions上で失敗を検知できるよう、失敗時は異常終了
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
