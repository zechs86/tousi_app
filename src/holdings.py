# holdings.py 【実保有の見張りリスト】
# 実際に証券会社で買った銘柄の「利確🎯/損切り🛑ライン」を登録しておき、
# 株価が到達したら通知で知らせるための置き場。
#   ・かぶミニ(単元未満株)は逆指値での自動損切りができないため、その代わりに
#     「到達したらスマホ通知 → 自分で成行売り」という“アラート型の損切り/利確”に使う。
#   ・ペーパー(仮想売買)とは別物。こちらは「実際の保有の見張り」専用。
# 保存: store の `hold:<user>`。形式 { code: {"name":.., "target":float, "stop":float} }
# 到達済みかどうかの記録(再通知防止)は notify_job 側が `holdsent:<user>` で持つ。

import re

import store

try:
    from universe import UNIVERSE
except Exception:
    UNIVERSE = {}


def _safe_user(user):
    u = re.sub(r"[^0-9A-Za-z_\-ぁ-んァ-ヶー一-龠]", "_", (user or "").strip())
    return u or "guest"


def _key(user):
    return f"hold:{_safe_user(user)}"


def load(user="guest"):
    """見張り中の銘柄 dict を返す。{ code: {name,target,stop} }。"""
    d = store.get_json(_key(user))
    return d if isinstance(d, dict) else {}


def save(d, user="guest"):
    store.set_json(_key(user), d)


def set_line(user, code, name, target, stop, trail=None):
    """銘柄の利確/損切りラインを登録/更新。target/stop/trail は 0以下で「なし」。
    trail = トレーリングストップの下げ幅(%)。高値(peak)から trail% 下げたら通知。
    trail=None（未指定）なら既存の trail/peak を維持（target/stopだけ上書きする用途）。
    3つとも0なら銘柄ごと見張りから削除。戻り値: 更新後 dict。"""
    d = load(user)
    prev = d.get(code, {})
    target = float(target or 0)
    stop = float(stop or 0)
    if trail is None:                      # 未指定 → 既存のトレーリング設定を維持
        trail = float(prev.get("trail", 0) or 0)
        peak = prev.get("peak", 0)
    else:
        trail = float(trail or 0)
        peak = prev.get("peak", 0) if trail > 0 else 0   # trailを切ったら高値リセット
    if target <= 0 and stop <= 0 and trail <= 0:
        d.pop(code, None)
    else:
        d[code] = {"name": name or UNIVERSE.get(code, code),
                   "target": target if target > 0 else 0,
                   "stop": stop if stop > 0 else 0,
                   "trail": trail if trail > 0 else 0,
                   "peak": peak if trail > 0 else 0}
    save(d, user)
    return d


def remove(user, code):
    d = load(user)
    d.pop(code, None)
    save(d, user)
    return d
