# _net.py
# 【日本語フォルダ対策】
# このプロジェクトは「デスクトップ」という日本語を含むフォルダにあります。
# 通信ライブラリ(curl)は、日本語を含むパスのSSL証明書ファイルをうまく開けず、
# 株価取得が SSLError で失敗します。
# そこで、証明書ファイルを「日本語を含まない安全な場所(Tempフォルダ)」へコピーし、
# そこを使うように設定します。これで通信が通るようになります。
#
# ※ main.py の一番上で、yfinance より先に import してください。

import os
import shutil
import tempfile
import certifi

def _setup_safe_ca():
    src = certifi.where()                      # certifiが持つ証明書の元の場所(日本語パス)
    dst = os.path.join(tempfile.gettempdir(), "tousi_cacert.pem")  # 日本語なしのコピー先
    try:
        # コピー先パス自体に非ASCII(日本語など)が含まれていたら諦める(その場合は別対策が必要)
        dst.encode("ascii")
        shutil.copyfile(src, dst)
        # 各種ライブラリが見る環境変数 と certifi.where を、安全なパスに差し替える
        certifi.where = lambda: dst
        os.environ["CURL_CA_BUNDLE"] = dst
        os.environ["SSL_CERT_FILE"] = dst
        os.environ["REQUESTS_CA_BUNDLE"] = dst
    except Exception:
        pass  # 失敗しても落とさない(元の挙動に戻るだけ)

_setup_safe_ca()
