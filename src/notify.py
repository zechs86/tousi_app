# notify.py
# 【スマホ通知の部品】ntfy.sh 経由でスマホにプッシュ通知を送ります。
# 他のプログラムから  from notify import send_push  で使います。
#
# 単体テスト:  .\.venv\Scripts\python.exe src\notify.py "好きなメッセージ"

import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)
import requests
from config import NTFY_TOPIC


def send_push(message, title="Tousi App", tags=None, priority=None, topic=None, click=None):
    """ntfyでスマホに通知を送る。成功でTrue。
    message : 本文(日本語OK)
    title   : 見出し(英数字推奨。日本語は化けることがある)
    tags    : 絵文字名(例 'moneybag','chart_with_upwards_trend','warning')
    priority: 'max','high','default','low','min'
    click   : 通知タップで開くURL
    """
    topic = topic or NTFY_TOPIC
    if not topic:
        print("NTFY_TOPIC が未設定です(config.py)")
        return False
    url = f"https://ntfy.sh/{topic}"
    headers = {"Title": title}
    if tags:
        headers["Tags"] = tags
    if priority:
        headers["Priority"] = priority
    if click:
        headers["Click"] = click
    try:
        r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=20)
        return r.status_code == 200
    except Exception as e:
        print("通知エラー:", e)
        return False


if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "notify.py からのテスト通知です。届けば成功！"
    ok = send_push(msg, title="Tousi Test", tags="white_check_mark")
    print("送信成功" if ok else "送信失敗")
