# favorites.py 【お気に入り銘柄】
# 気になる銘柄に⭐を付けて、ページ上部からワンタップで呼び出せるようにする。
# 保存: data/favorites.json(手元・gitignore)。
# クラウドはアプリが眠るとファイルが消えるが、その時は config.FAVORITES から自動で復元する
# （= config.FAVORITES が“消えない基本のお気に入り”。永続させたい銘柄はそこに入れる）。

import os
import json

import config
from universe import UNIVERSE

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_PATH = os.path.join(_DIR, "favorites.json")


def _read_file():
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None  # ファイルなし


def _save_file(lst):
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


def load():
    """お気に入りコードのリスト。ファイルが無ければ config.FAVORITES から作る。"""
    f = _read_file()
    if f is None:
        f = [c for c in getattr(config, "FAVORITES", []) if c in UNIVERSE]
        _save_file(f)
    # ユニバースに存在するものだけ・重複排除・順序維持
    seen, out = set(), []
    for c in f:
        if c in UNIVERSE and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def is_fav(code):
    return code in load()


def toggle(code):
    """⭐の付け外し。戻り値: 更新後リスト。"""
    f = load()
    if code in f:
        f.remove(code)
    elif code in UNIVERSE:
        f.append(code)
    _save_file(f)
    return f


if __name__ == "__main__":
    print(load())
