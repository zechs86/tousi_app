# paper.py 【ペーパートレード(仮想資金で売買を記録)】
# 実弾の前に戦略を試すための“練習売買”。仮想資金で買い/売りを記録し、評価損益を見る。
# データは data/paper_trades.json に保存(手元・gitignore済)。
#
# 注意: Streamlit Cloud はファイルが一時的なので、アプリが眠ると記録が消えることがあります。
#       ずっと残したい場合は将来クラウドDBを足します。手元(PC)では永続します。

import os
import json
import datetime

START_CASH = 1_000_000  # 仮想の初期資金(円)。10万円スタートの練習なら下げてもOK。

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_PATH = os.path.join(_DIR, "paper_trades.json")


def _new_state():
    return {"cash": START_CASH, "start_cash": START_CASH, "positions": {},
            "history": [], "equity_curve": [], "targets": {}, "stops": {}}


def load():
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            s = json.load(f)
        # 後方互換: 欠けたキーを補完
        for k, v in _new_state().items():
            s.setdefault(k, v)
        return s
    except Exception:
        return _new_state()


def save(state):
    os.makedirs(_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def reset():
    s = _new_state()
    save(s)
    return s


def buy(state, code, name, shares, price):
    """仮想で買う。戻り値: (state, error)。"""
    shares = int(shares)
    if shares <= 0:
        return state, "株数は1以上にしてください。"
    cost = shares * price
    if cost > state["cash"]:
        return state, f"資金不足です（必要 ¥{cost:,.0f} / 残り ¥{state['cash']:,.0f}）。"
    pos = state["positions"].get(code)
    if pos:
        total_cost = pos["avg_cost"] * pos["shares"] + cost
        pos["shares"] += shares
        pos["avg_cost"] = total_cost / pos["shares"]
        pos["name"] = name
    else:
        state["positions"][code] = {"name": name, "shares": shares, "avg_cost": float(price)}
    state["cash"] -= cost
    state["history"].insert(0, {"time": _now(), "action": "買", "code": code, "name": name,
                                "shares": shares, "price": float(price)})
    save(state)
    return state, None


def sell(state, code, shares, price):
    """仮想で売る。戻り値: (state, error)。"""
    shares = int(shares)
    pos = state["positions"].get(code)
    if not pos or pos["shares"] <= 0:
        return state, "その銘柄は保有していません。"
    if shares <= 0 or shares > pos["shares"]:
        return state, f"売却株数が不正です（保有 {pos['shares']}株）。"
    proceeds = shares * price
    realized = (price - pos["avg_cost"]) * shares
    name = pos["name"]
    pos["shares"] -= shares
    if pos["shares"] == 0:
        del state["positions"][code]
    state["cash"] += proceeds
    state["history"].insert(0, {"time": _now(), "action": "売", "code": code, "name": name,
                                "shares": shares, "price": float(price),
                                "realized": round(realized)})
    save(state)
    return state, None


def summary(state, prices):
    """prices: {code: 現在値}。総資産・評価損益・リターンを計算して返す。"""
    holdings_value = 0.0
    rows = []
    for code, pos in state["positions"].items():
        cur = prices.get(code) or pos["avg_cost"]
        val = cur * pos["shares"]
        cost = pos["avg_cost"] * pos["shares"]
        pl = val - cost
        pl_pct = (cur / pos["avg_cost"] - 1) * 100 if pos["avg_cost"] else 0
        holdings_value += val
        rows.append({"code": code, "name": pos["name"], "shares": pos["shares"],
                     "avg_cost": pos["avg_cost"], "cur": cur, "value": val,
                     "pl": pl, "pl_pct": pl_pct})
    total = state["cash"] + holdings_value
    ret_pct = (total / state["start_cash"] - 1) * 100 if state["start_cash"] else 0
    return {"total": total, "cash": state["cash"], "holdings_value": holdings_value,
            "ret_pct": ret_pct, "rows": rows}


def record_equity(state, total):
    """今日の総資産を資産推移に記録(1日1点・同日は上書き)。"""
    today = datetime.date.today().isoformat()
    ec = state.setdefault("equity_curve", [])
    if ec and ec[-1].get("date") == today:
        ec[-1]["total"] = round(total)
    else:
        ec.append({"date": today, "total": round(total)})
        if len(ec) > 400:
            del ec[0]
    save(state)


def stats(state):
    """売買成績(勝率・実現損益・回数)を集計。"""
    realized = [h for h in state.get("history", []) if "realized" in h]
    wins = sum(1 for h in realized if h["realized"] > 0)
    n = len(realized)
    total_realized = sum(h["realized"] for h in realized)
    return {"trades": n, "wins": wins,
            "win_rate": (wins / n * 100) if n else 0.0,
            "total_realized": total_realized}


def set_target(state, code, price):
    """目標株価(利確)を設定/解除(price<=0で解除)。"""
    tg = state.setdefault("targets", {})
    if price and price > 0:
        tg[code] = float(price)
    elif code in tg:
        del tg[code]
    save(state)


def set_stop(state, code, price):
    """損切りライン(stop)を設定/解除(price<=0で解除)。"""
    sp = state.setdefault("stops", {})
    if price and price > 0:
        sp[code] = float(price)
    elif code in sp:
        del sp[code]
    save(state)


if __name__ == "__main__":
    s = load()
    print(json.dumps(s, ensure_ascii=False, indent=2))
