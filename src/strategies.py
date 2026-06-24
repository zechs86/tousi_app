# strategies.py
# 【売買戦略の部品集】
# それぞれの戦略は「その日、株を持つべきか(1) / 持たないべきか(0)」を
# 全期間ぶん返す関数です(pandasのSeries)。
# これをバックテストに渡すと、戦略どうしを公平に比較できます。
#
# ねらい: 今の素朴な戦略(buy&holdに負けた)を、改良して勝てるようにすること。
# キモは「下降トレンド中は買わない」フィルター。暴落に巻き込まれないのが勝ち筋。

import pandas as pd


def buy_and_hold(dfi):
    """比較の基準。ずっと持ちっぱなし。"""
    return pd.Series(1, index=dfi.index)


def sma_cross_fast(dfi):
    """【今までの戦略に近い】短期線(SMA5)が中期線(SMA25)より上なら持つ。
    反応は速いが、ダマシ(往復ビンタ)が多くなりがち。"""
    return (dfi["SMA5"] > dfi["SMA25"]).astype(int)


def trend_filter(dfi):
    """【改良案①トレンド追従】中期線(SMA25)が長期線(SMA75)より上=上昇トレンドの間だけ持つ。
    下降トレンドに入ったら降りるので、大きな暴落を避けやすい。"""
    return (dfi["SMA25"] > dfi["SMA75"]).astype(int)


def rsi_mean_reversion(dfi, low=30, high=55):
    """【改良案②逆張り】RSIが low(30)以下の“売られすぎ”で買い、high(55)に戻ったら売る。
    安く買って戻りで売る、まさに本来やりたい形。ただし下落トレンドでは早すぎる買いに注意。"""
    pos, holding = [], 0
    for r in dfi["RSI"].fillna(50):
        if holding == 0 and r <= low:
            holding = 1
        elif holding == 1 and r >= high:
            holding = 0
        pos.append(holding)
    return pd.Series(pos, index=dfi.index)


def dip_in_uptrend(dfi, rsi_buy=40):
    """【改良案③合わせ技】上昇トレンド(SMA25>SMA75)の中で、
    一時的に押した(RSIがrsi_buy以下)ところを買い、トレンドが崩れたら降りる。
    『上昇基調の押し目だけ拾う』= 落ちるナイフを避けつつ安く買う狙い。"""
    uptrend = dfi["SMA25"] > dfi["SMA75"]
    pos, holding = [], 0
    rsi = dfi["RSI"].fillna(50)
    for i in range(len(dfi)):
        up = bool(uptrend.iloc[i])
        r = rsi.iloc[i]
        if holding == 0 and up and r <= rsi_buy:
            holding = 1            # 上昇トレンド中の押し目で買い
        elif holding == 1 and not up:
            holding = 0            # トレンドが崩れたら撤退
        pos.append(holding)
    return pd.Series(pos, index=dfi.index)


# バックテストで比較する戦略の一覧(名前: 関数)
ALL_STRATEGIES = {
    "buy&hold(基準)": buy_and_hold,
    "SMA5×25クロス(従来)": sma_cross_fast,
    "トレンド追従(改良①)": trend_filter,
    "RSI逆張り(改良②)": rsi_mean_reversion,
    "上昇中の押し目買い(改良③)": dip_in_uptrend,
}
