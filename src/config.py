# config.py
# 【アプリ全体の設定】ここを書き換えるだけで挙動を調整できます。

import os

# --- スマホ通知(ntfy) ---
# 合言葉(トピック)は公開リポジトリに載せないため、コードに直接書きません。
#   ① 環境変数 NTFY_TOPIC があればそれを使う(GitHub Actions の Secrets 用)
#   ② 無ければ src/secret_local.py(gitignore済み・手元だけ)から読む
#   ③ それも無ければ空(通知はスキップされるだけ)
def _load_ntfy_topic():
    v = os.environ.get("NTFY_TOPIC")
    if v and v.strip():
        return v.strip()
    try:
        from secret_local import NTFY_TOPIC as _t  # 手元だけのファイル(公開されない)
        return _t
    except Exception:
        return ""

NTFY_TOPIC = _load_ntfy_topic()

# --- スキャナー ---
SCAN_TOP_N = 8          # 「ここぞ」上位を何銘柄まで通知するか
MAX_PRICE_FOR_BUDGET = 1000   # 10万円で日本株100株が買える目安株価(円)。これ以下を「少額で買える」と印

# --- リスク管理(あなた=10万円スタート・大きく狙う 向け) ---
TAKE_PROFIT_PCT = 10.0   # +10%で利確を検討(攻め)
STOP_LOSS_PCT = 5.0      # -5%で損切り(これだけは必ず守る)
RISK_PER_TRADE_YEN = 5000  # 1トレードで失ってよい上限の目安(損切り幅から株数を逆算する用)
