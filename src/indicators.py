# indicators.py
# 株価データから「テクニカル指標」を計算する部品をまとめたファイルです。
# テクニカル指標 = 過去の株価の動きから、買いどき・売りどきのヒントを数値化したもの。
#
# このファイルで計算するのは、王道の3つ:
#   1. 移動平均線 (SMA) … 株価の平均的な流れ。短期線が長期線を上抜く=上昇サイン
#   2. RSI            … 買われすぎ/売られすぎを 0〜100 で表す。30以下=安い、70以上=高い
#   3. MACD           … トレンドの勢いと転換点をとらえる

import pandas as pd


def add_sma(df: pd.DataFrame, periods=(5, 25, 75)) -> pd.DataFrame:
    """移動平均線(SMA)を追加する。
    例: SMA5 = 直近5日間の終値の平均。短期=5日, 中期=25日, 長期=75日 が日本株の定番。"""
    for p in periods:
        df[f"SMA{p}"] = df["Close"].rolling(window=p).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI(相対力指数)を追加する。一般に 70以上=買われすぎ(売りを検討) / 30以下=売られすぎ(買いを検討)。"""
    delta = df["Close"].diff()                 # 前日比(上がった/下がった幅)
    gain = delta.clip(lower=0)                 # 上がった分だけ取り出す
    loss = -delta.clip(upper=0)                # 下がった分だけ取り出す(プラスの値にする)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACDを追加する。
    MACD線がシグナル線を下から上抜く=買いサイン、上から下抜く=売りサイン。"""
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]   # 0より上=勢いが上向き
    return df


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """上の3つをまとめて計算する。"""
    df = add_sma(df)
    df = add_rsi(df)
    df = add_macd(df)
    return df
