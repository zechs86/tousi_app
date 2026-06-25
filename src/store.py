# store.py 【保存先の抽象化】
# ペーパー/お気に入りなどの小さなJSONを、キーで読み書きする共通の置き場。
#   ・Upstash Redis(無料・REST)が設定されていればクラウドDBに保存=アプリが眠っても消えない
#   ・未設定なら data/kv/ にファイル保存(手元では永続/クラウドは一時的=従来どおり)
# 認証情報は環境変数 or Streamlit secrets から読む(コードには書かない):
#   UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN

import os
import json

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kv")


def _secret(name):
    v = os.environ.get(name)
    if v:
        return v
    try:
        import streamlit as st
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    try:
        import secret_local  # 手元のファイル(gitignore)。UPSTASH_... を入れておける
        v = getattr(secret_local, name, "")
        if v:
            return str(v)
    except Exception:
        pass
    return ""


def _upstash():
    url = (_secret("UPSTASH_REDIS_REST_URL") or "").strip().rstrip("/")
    tok = (_secret("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    return (url, tok) if url and tok else (None, None)


def using_db():
    return _upstash()[0] is not None


def _safe(key):
    # ファイル名用。: はWindowsで使えないので _ に。Redisキーは raw のまま(別途)。
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in key)


def kv_get(key):
    """キーの値(文字列)を返す。無ければ None。"""
    url, tok = _upstash()
    if url:
        try:
            import requests
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                              json=["GET", key], timeout=15)
            if r.status_code == 200:
                return r.json().get("result")
        except Exception:
            pass  # 失敗時はファイルにフォールバック
    # ファイル保存
    try:
        with open(os.path.join(_DIR, _safe(key) + ".json"), "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def kv_set(key, value):
    """キーに文字列を保存。"""
    url, tok = _upstash()
    if url:
        try:
            import requests
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                              json=["SET", key, value], timeout=15)
            if r.status_code == 200:
                return True
        except Exception:
            pass
    os.makedirs(_DIR, exist_ok=True)
    with open(os.path.join(_DIR, _safe(key) + ".json"), "w", encoding="utf-8") as f:
        f.write(value)
    return True


def list_keys(pattern="*"):
    """パターンに一致するキー一覧を返す(例 'paper:*')。
    Upstashなら KEYS、ファイル保存ならファイル名から復元(best-effort)。"""
    url, tok = _upstash()
    if url:
        try:
            import requests
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                              json=["KEYS", pattern], timeout=15)
            if r.status_code == 200:
                return r.json().get("result") or []
        except Exception:
            pass
    # ファイル保存のフォールバック: data/kv/*.json のファイル名(=_safe済みキー)を返す。
    # 注: ':' は '_' に変換済みのため raw キーと完全一致しないことがある。
    try:
        return [fn[:-5] for fn in os.listdir(_DIR) if fn.endswith(".json")]
    except Exception:
        return []


def get_json(key, default=None):
    raw = kv_get(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_json(key, obj):
    kv_set(key, json.dumps(obj, ensure_ascii=False))
