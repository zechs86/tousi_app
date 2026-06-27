# signals.py
# 計算した指標を見て「買い / 売り / 様子見」を判定する部品です。
# ここがあなたの“トレード戦略”そのもの。
#
# 【点数配分の根拠（2026-06 バックテストで実証）】
#   107銘柄×複数期間で「各指標が点灯した日の数営業日後リターン」を測った結果:
#     ・RSI売られすぎ(<30)だけが明確な予測力（10日先 +2.6%・勝率68%）。RSI<40でも+0.9%。
#     ・SMA5>25の順張り継続 と MACD は、むしろ先行リターンがマイナス〜ゼロ（予測力なし）。
#   そこで「RSI売られすぎ＝主役(+3)」「トレンドは確認用(±1)」「クロスは小(±1)」とし、
#   予測力の無いMACDは買いスコアから外しました。
#   → 「買い」は実質『上昇トレンド中の売られすぎ＝押し目』でだけ点灯し、
#      下降トレンド中のRSI<30(落ちるナイフ)は買いになりません(score=+2=様子見)。
#   ※それでも“必勝”ではありません。損切りは必ず守る前提です。

import pandas as pd


def judge(df: pd.DataFrame) -> dict:
    """最新日のデータを見て、買い/売りの総合判定とその理由を返す。"""
    last = df.iloc[-1]       # 一番新しい日(最新)
    prev = df.iloc[-2]       # その前日(クロス=交差 を見るのに使う)

    score = 0                # 点数。プラスで買い寄り、マイナスで売り寄り
    reasons = []             # 判断の理由(あなたが納得できるように残す)

    # --- 1) RSI: 売られすぎ(安い) ＝ 唯一はっきり効く“主役” ---
    rsi = last["RSI"]
    if rsi < 30:
        score += 3
        reasons.append(f"🟢 RSI={rsi:.0f} 売られすぎ(安い→押し目の本命)")
    elif rsi < 40:
        score += 1
        reasons.append(f"🟢 RSI={rsi:.0f} やや売られすぎ(押し目寄り)")
    elif rsi > 70:
        score -= 2
        reasons.append(f"🔴 RSI={rsi:.0f} 買われすぎ(高い→売りを検討)")
    else:
        reasons.append(f"・RSI={rsi:.0f}(中立)")

    # --- 2) トレンドの地合い(中期25 と 長期75): 確認用 ---
    # 上昇トレンド中の押し目だけを買い、下降トレンドの安値拾い(落ちるナイフ)を避ける。
    if last["SMA25"] > last["SMA75"]:
        score += 1
        reasons.append("・上昇トレンド地合い(SMA25>SMA75)")
    else:
        score -= 1
        reasons.append("・下降トレンド地合い(SMA25<SMA75=安値拾いは危険)")

    # --- 3) 短期のクロス(5日×25日): イベント時だけ小さく加点 ---
    if prev["SMA5"] <= prev["SMA25"] and last["SMA5"] > last["SMA25"]:
        score += 1
        reasons.append("📈 ゴールデンクロス(短期線が中期線を上抜け)")
    elif prev["SMA5"] >= prev["SMA25"] and last["SMA5"] < last["SMA25"]:
        score -= 1
        reasons.append("📉 デッドクロス(短期線が中期線を下抜け)")

    # ※MACDは「点灯日の先行リターンが負〜ゼロ＝予測力なし」のため買い点数から除外。
    #   参考情報としてだけ残す。
    if last["MACD_hist"] > 0:
        reasons.append("（参考）MACDは上向き")
    else:
        reasons.append("（参考）MACDは下向き")

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
