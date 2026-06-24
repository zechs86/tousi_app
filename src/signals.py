# signals.py
# 計算した指標を見て「買い / 売り / 様子見」を判定する部品です。
# ここがあなたの“トレード戦略”そのもの。あとでルールを足したり強さを変えたりできます。
#
# 考え方: 1つの指標だけで決めると だまし(ハズレ)が多い。
#         そこで複数の指標の点数を足し算して、総合点で判断します。
#         プラスが大きい=買い、マイナスが大きい=売り。

import pandas as pd


def judge(df: pd.DataFrame) -> dict:
    """最新日のデータを見て、買い/売りの総合判定とその理由を返す。"""
    last = df.iloc[-1]       # 一番新しい日(最新)
    prev = df.iloc[-2]       # その前日(クロス=交差 を見るのに使う)

    score = 0                # 点数。プラスで買い寄り、マイナスで売り寄り
    reasons = []             # 判断の理由(あなたが納得できるように残す)

    # --- 1) 移動平均: ゴールデンクロス/デッドクロス (短期5日 と 中期25日) ---
    if prev["SMA5"] <= prev["SMA25"] and last["SMA5"] > last["SMA25"]:
        score += 2
        reasons.append("📈 ゴールデンクロス(短期線が中期線を上抜け=上昇の合図)")
    elif prev["SMA5"] >= prev["SMA25"] and last["SMA5"] < last["SMA25"]:
        score -= 2
        reasons.append("📉 デッドクロス(短期線が中期線を下抜け=下落の合図)")
    elif last["SMA5"] > last["SMA25"]:
        score += 1
        reasons.append("・短期線が中期線の上(上昇トレンド継続中)")
    else:
        score -= 1
        reasons.append("・短期線が中期線の下(下落トレンド継続中)")

    # --- 2) RSI: 売られすぎ(安い)/買われすぎ(高い) ---
    rsi = last["RSI"]
    if rsi < 30:
        score += 2
        reasons.append(f"🟢 RSI={rsi:.0f} 売られすぎ(安い→買いを検討)")
    elif rsi > 70:
        score -= 2
        reasons.append(f"🔴 RSI={rsi:.0f} 買われすぎ(高い→売りを検討)")
    else:
        reasons.append(f"・RSI={rsi:.0f}(中立)")

    # --- 3) MACD: 勢いの転換 ---
    if prev["MACD"] <= prev["MACD_signal"] and last["MACD"] > last["MACD_signal"]:
        score += 2
        reasons.append("📈 MACDが上抜け(上昇の勢いが出始めた)")
    elif prev["MACD"] >= prev["MACD_signal"] and last["MACD"] < last["MACD_signal"]:
        score -= 2
        reasons.append("📉 MACDが下抜け(下落の勢いが出始めた)")
    elif last["MACD_hist"] > 0:
        score += 1
        reasons.append("・MACDは上向き(勢いは買い寄り)")
    else:
        score -= 1
        reasons.append("・MACDは下向き(勢いは売り寄り)")

    # --- 総合判定 ---
    if score >= 3:
        verdict = "買い"
    elif score <= -3:
        verdict = "売り"
    else:
        verdict = "様子見"

    return {
        "verdict": verdict,
        "score": score,
        "price": float(last["Close"]),
        "rsi": float(rsi),
        "reasons": reasons,
    }
