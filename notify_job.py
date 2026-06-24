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


def build_message(hits):
    """スキャン結果を、スマホで読みやすい1通の本文にまとめる。"""
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


def main():
    label = os.environ.get("RUN_LABEL", "").strip()
    prefix = f"【{label}のチェック】" if label else "【自動チェック】"

    print("スキャン中...")
    hits = scan()

    if not hits:
        msg = f"{prefix}今日はサイン点灯銘柄なし。様子見の相場です。"
        title = "Tousi: no signal"
        tags = "coffee"
    else:
        body = build_message(hits)
        n = min(len(hits), config.SCAN_TOP_N)
        msg = f"{prefix}買い候補 {len(hits)}件中 上位{n}件\n\n{body}\n\n※サイン=必勝ではありません。"
        title = f"Tousi: {len(hits)} signals"
        tags = "chart_with_upwards_trend"

    # トピックは環境変数(GitHub Secrets)で上書き可。無ければ config.py の値を使う。
    topic = os.environ.get("NTFY_TOPIC") or None
    ok = send_push(msg, title=title, tags=tags, priority="default", topic=topic)
    print("通知 送信成功" if ok else "通知 送信失敗")
    # GitHub Actions上で失敗を検知できるよう、失敗時は異常終了
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
