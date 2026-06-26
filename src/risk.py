# risk.py 【暴落・急変リスク検知】
# 監視ユニバース全銘柄を見て、「急落」「短期での大きな下げ」「出来高急増を伴う下落」を検出。
# 通知ジョブ(朝夜)で“要注意”として知らせる＆ダッシュボードでも使える。
# 実行: .\.venv\Scripts\python.exe src\risk.py

import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401
import yfinance as yf

from universe import UNIVERSE

# しきい値(config化してもよいが、まずはここで分かりやすく)
DROP_1D = -5.0     # 1日で-5%以上の下落 = 急落
DROP_5D = -10.0    # 直近5日で-10%以上の下落 = 短期暴落
VOL_SPIKE = 1.8    # 出来高が20日平均の1.8倍以上 かつ 下落 = 売り圧力
GAP_DOWN = -3.0    # 寄り付きが前日終値より-3%以上低い = ギャップダウン(悪材料の可能性)


def _analyze(code, name, df):
    df = df.dropna()
    if df is None or df.empty or len(df) < 25:
        return None
    close = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    open_today = float(df["Open"].iloc[-1])
    chg_1d = (close / prev - 1) * 100
    base_5d = float(df["Close"].iloc[-6]) if len(df) >= 6 else prev
    chg_5d = (close / base_5d - 1) * 100
    vol_avg = float(df["Volume"].iloc[-21:-1].mean())
    vol_today = float(df["Volume"].iloc[-1])
    vol_ratio = (vol_today / vol_avg) if vol_avg else 0.0
    gap = (open_today / prev - 1) * 100 if prev else 0.0
    # 期間内(約3ヶ月)の最安値を更新したか
    period_low = float(df["Close"].min())
    new_low = close <= period_low * 1.001

    reason = None
    if chg_1d <= DROP_1D:
        reason = f"急落 {chg_1d:.1f}%"
    elif chg_5d <= DROP_5D:
        reason = f"5日で{chg_5d:.1f}%"
    elif new_low and chg_1d < 0:
        reason = "約3ヶ月の安値更新"
    elif gap <= GAP_DOWN:
        reason = f"寄りで{gap:.1f}%のギャップ下げ"
    elif vol_ratio >= VOL_SPIKE and chg_1d < 0:
        reason = f"出来高急増({vol_ratio:.1f}倍)で下落"
    if reason is None:
        return None

    is_jp = code.endswith(".T")
    # 並べ替え用の深刻度: 下げ幅・ギャップ・新安値(=10点)の最大
    severity = max(abs(min(chg_1d, chg_5d)), abs(min(gap, 0)), 10.0 if new_low else 0.0)
    return {
        "code": code, "name": name, "price": close,
        "chg_1d": round(chg_1d, 1), "chg_5d": round(chg_5d, 1),
        "reason": reason, "severity": severity, "is_jp": is_jp,
    }


def detect_risks(limit=None):
    """ユニバースを走査し、急変・下落で要注意の銘柄を深刻な順に返す。"""
    codes = list(UNIVERSE.keys())
    if limit:
        codes = codes[:limit]
    data = yf.download(codes, period="3mo", interval="1d", auto_adjust=True,
                       group_by="ticker", progress=False, threads=True)
    out = []
    for code in codes:
        try:
            sub = data[code] if len(codes) > 1 else data
            r = _analyze(code, UNIVERSE[code], sub)
        except Exception:
            continue
        if r:
            out.append(r)
    out.sort(key=lambda x: x["severity"], reverse=True)
    return out


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    risks = detect_risks(lim)
    if not risks:
        print("要注意の急変銘柄なし。")
    else:
        print(f"⚠️ 要注意 {len(risks)}件:")
        for r in risks:
            cur = "" if r["is_jp"] else "$"
            print(f"  {r['name']}: {r['reason']}（{cur}{r['price']:,.0f}）")
