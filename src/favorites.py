# favorites.py 【お気に入り銘柄】
# 気になる銘柄に⭐を付けて、ページ上部からワンタップで呼び出せるようにする。
# 保存: data/favorites.json(手元・gitignore)。
# クラウドはアプリが眠るとファイルが消えるが、その時は config.FAVORITES から自動で復元する
# （= config.FAVORITES が“消えない基本のお気に入り”。永続させたい銘柄はそこに入れる）。

import re

import config
import store
from universe import UNIVERSE


def _safe_user(user):
    u = re.sub(r"[^0-9A-Za-z_\-ぁ-んァ-ヶー一-龠]", "_", (user or "").strip())
    return u or "guest"


def _key(user):
    return f"fav:{_safe_user(user)}"


def _read_file(user):
    return store.get_json(_key(user))  # 無ければ None


def _save_file(lst, user):
    store.set_json(_key(user), lst)


def load(user="guest"):
    """お気に入りコードのリスト。無ければ config.FAVORITES から作る。"""
    f = _read_file(user)
    if not isinstance(f, list):
        f = [c for c in getattr(config, "FAVORITES", []) if c in UNIVERSE]
        _save_file(f, user)
    # ユニバースに存在するものだけ・重複排除・順序維持
    seen, out = set(), []
    for c in f:
        if c in UNIVERSE and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def is_fav(code, user="guest"):
    return code in load(user)


def toggle(code, user="guest"):
    """⭐の付け外し。戻り値: 更新後リスト。"""
    f = load(user)
    if code in f:
        f.remove(code)
    elif code in UNIVERSE:
        f.append(code)
    _save_file(f, user)
    return f


if __name__ == "__main__":
    print(load())
