# analog.py 【過去の“似た局面”の統計】
# ※これは「予測」ではありません。今日と似たRSI・トレンドだった過去の日を集め、
#   その数営業日後に実際どう動いたか(勝率・平均・最大/最小)を集計するだけの“確率の参考”です。
#   未来を当てる道具ではなく、「似た時はこう動きがちだった」という傾向を見るためのものです。
#   損切りルールは必ず守る前提。

import statistics


def historical_analog(dfi, horizon=5, rsi_tol=7.0):
    """指標付きデータ(add_all_indicators済)から、今日と似た局面の horizon営業日後 変化率を集計。
    似た局面 = 同じトレンド(SMA25>SMA75の符号一致) かつ RSIが±rsi_tol 以内。
    戻り値: dict(samples, win_rate, avg, median, best, worst, horizon, today_rsi, today_up) or None。
    サンプルが少ない(10未満)時は None(=参考にできない)。"""
    try:
        import pandas as pd
    except Exception:
        return None
    if dfi is None or len(dfi) < horizon + 30:
        return None
    last = dfi.iloc[-1]
    if pd.isna(last.get("RSI")) or pd.isna(last.get("SMA75")):
        return None
    today_rsi = float(last["RSI"])
    today_up = bool(last["SMA25"] > last["SMA75"])

    closes = dfi["Close"].tolist()
    rsi = dfi["RSI"].tolist()
    sma25 = dfi["SMA25"].tolist()
    sma75 = dfi["SMA75"].tolist()
    n = len(dfi)
    rets = []
    for i in range(n - horizon):
        ri, s25, s75 = rsi[i], sma25[i], sma75[i]
        if ri != ri or s75 != s75 or s25 != s25:   # NaN除外
            continue
        if (s25 > s75) != today_up:
            continue
        if abs(ri - today_rsi) > rsi_tol:
            continue
        base = closes[i]
        if base:
            rets.append((closes[i + horizon] / base - 1) * 100)
    if len(rets) < 10:
        return None
    return {
        "samples": len(rets),
        "win_rate": sum(1 for r in rets if r > 0) / len(rets) * 100,
        "avg": statistics.mean(rets),
        "median": statistics.median(rets),
        "best": max(rets),
        "worst": min(rets),
        "horizon": horizon,
        "today_rsi": today_rsi,
        "today_up": today_up,
    }
