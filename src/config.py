# config.py
# 【アプリ全体の設定】ここを書き換えるだけで挙動を調整できます。

import os

# --- お気に入り銘柄(消えない基本リスト) ---
# クラウドが眠ってもここの銘柄は復活する。永続させたい銘柄コードを並べる。
# アプリ内で⭐を付け外しもできる(手元では永続/クラウドは一時的)。
FAVORITES = ["8267.T"]   # 例: イオン。増やしたい時はここに "7203.T" などを追加。

# --- アプリ(ダッシュボード)のURL ---
# 通知の一番下に表示し、タップでダッシュボードが開くようにする。
# Streamlit Cloud のアプリURL(https://〇〇〇.streamlit.app)をここに入れる。
APP_URL = "https://tousiapp-halx5hjmpkl8fkzcyq2gqn.streamlit.app"

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

# --- 利確/損切り 到達アラート ---
# ライン到達の少し手前(この%以内)になったら「もうすぐ到達」と予告通知する。
# 例 2.0 なら、利確まであと2%以内/損切りまであと2%以内で予告。0以下で予告オフ(到達時のみ)。
NEAR_ALERT_PCT = 2.0

# --- 株主優待カウントダウン(無料・通知に表示) ---
# 権利付最終日までの残り日数がこの値以下になったら、朝夜通知に優待リマインドを表示する。
# 0 以下にすると優待リマインドを止める。
YUTAI_REMIND_DAYS = 75
# 優待銘柄と権利確定月。watch.py の RECORD_MONTHS とここを合算して判定する。
# 「コード: [確定月,...]」で追加できる。※月は各自で要確認(優待内容/月は変更・廃止あり)。
YUTAI_RECORD_MONTHS = {
    "8267.T": [2, 8],    # イオン(優待オーナーズカード)
    # 例) "9861.T": [2, 8],  # 吉野家  ← 使う時はコメントを外し、月をご確認ください
    # 例) "3197.T": [6, 12], # すかいらーく
}

# --- 決算カレンダー(無料・通知に表示) ---
# お気に入り＋ペーパー保有のうち、次の決算発表日がこの日数以内の銘柄を通知する。
# 0 以下でオフ。※日本株はyfinanceに決算日が無い/ズレることがある=出る範囲で表示。
EARNINGS_REMIND_DAYS = 14

# --- スキャナー ---
SCAN_TOP_N = 8          # 「ここぞ」上位を何銘柄まで通知するか
MAX_PRICE_FOR_BUDGET = 1000   # 10万円で日本株100株が買える目安株価(円)。これ以下を「少額で買える」と印

# --- リスク管理(あなた=10万円スタート・大きく狙う 向け) ---
TAKE_PROFIT_PCT = 10.0   # +10%で利確を検討(攻め)
STOP_LOSS_PCT = 5.0      # -5%で損切り(これだけは必ず守る)
RISK_PER_TRADE_YEN = 5000  # 1トレードで失ってよい上限の目安(損切り幅から株数を逆算する用)

# --- AI銘柄分析(Claude) ---
# 使うモデル。コスト重視なら sonnet、最高精度なら opus。
#   claude-sonnet-4-6 … バランス(推奨・安い)
#   claude-opus-4-8   … 最高精度(やや高い)
#   claude-haiku-4-5  … 最安・高速(軽い要約向け)
AI_MODEL = "claude-sonnet-4-6"

# AI機能のオン/オフ(Trueで有効=API課金が発生)。コスト節約のため既定オフ。
AI_CHAT_ENABLED = False      # 💬AI相談チャット(従量課金・1問¥5〜20)。Trueでタブ表示。
AI_NOTIFY_COMMENT = True     # 朝夜通知のAIコメント(1回約¥0.5・月¥20〜40)。Trueで付与。

# APIキーの読み込み: ①環境変数 ②Streamlitのsecrets ③手元のsecret_local.py の順。
def _load_anthropic_key():
    v = os.environ.get("ANTHROPIC_API_KEY")
    if v and v.strip():
        return v.strip()
    try:
        import streamlit as st  # クラウド公開時は Streamlit の Secrets に入れる
        if "ANTHROPIC_API_KEY" in st.secrets:
            return str(st.secrets["ANTHROPIC_API_KEY"]).strip()
    except Exception:
        pass
    try:
        from secret_local import ANTHROPIC_API_KEY as _k  # 手元だけ(公開されない)
        return _k
    except Exception:
        return ""

ANTHROPIC_API_KEY = _load_anthropic_key()
