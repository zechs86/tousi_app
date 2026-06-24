# ai_analysis.py 【Claude(AI)による個別成長株の分析】
# ニュース＋テクニカル＋ファンダ＋業績成長率＋機関投資家需給＋アナリスト目標を
# Claudeに渡し、成長株としての評価を構造化(JSON)で返してもらう。
# ダッシュボードの「🤖 AI分析」タブと、通知ジョブのAIコメントから使う。
#
# 手元テスト:  .\.venv\Scripts\python.exe src\ai_analysis.py 6920.T

import warnings
warnings.simplefilter("ignore")

import os
import re
import json

import config

SYSTEM = (
    "あなたは日本株を専門とする冷静なバイサイド・アナリストです。"
    "ユーザーは投資初心者で、個別の成長株を長期目線で見極めたいと考えています。"
    "渡された材料(株価・テクニカル・ファンダ・業績成長率・機関投資家需給・アナリスト目標・ニュース見出し)だけを根拠に、"
    "成長株としての魅力とリスクを率直に評価してください。"
    "重要な制約: ①これは投資助言ではなく判断材料であること。"
    "②材料に無いことを断定しない(不明なら『材料からは不明』と書く)。"
    "③ニュース見出しに別企業や無関係なものが混じっていたら無視する。"
    "④誇張や煽りをせず、弱点・リスクも必ず挙げる。"
    "⑤機関投資家・大口の保有や需給は重要な観点として必ず触れる"
    "(日本株は公開データが乏しいことが多いので、材料が無ければ『公開材料からは限定的』と正直に書く。憶測で機関名や金額を作らない)。"
    "⑥目標株価はアナリスト平均が材料にあればそれを基準に所感を述べ、無ければPERや成長率から妥当感を述べる(断定しない)。"
    "⑦『なぜ今か』(タイミング)は、押し目・ブレイク・待ち のどれかを根拠つきで簡潔に。"
    "出力は、指定したJSON以外を一切含めないこと(前置き・コードフェンス・解説は禁止)。"
)

# 期待するJSONの形(モデルに提示する)
SHAPE = """{
  "summary": "3行以内の要約(この銘柄の現状を一言で)",
  "growth_drivers": ["成長の原動力を箇条書きで2〜4個"],
  "strengths": ["競争上の強み・参入障壁(堀)を2〜4個"],
  "earnings_take": "直近の決算・業績トレンドの所感(増収増益か等。材料が乏しければ『材料からは不明』)",
  "positive_catalysts": ["直近の好材料・追い風(ニュース等から)"],
  "risks": ["主なリスク・弱点を2〜4個(必須)"],
  "institutional_take": "機関投資家・大口の保有/需給に関する所感(1〜2文)",
  "valuation_take": "PER/PBR/配当などから見た割高・割安の所感(1〜2文)",
  "target_take": "目標株価の所感(アナリスト平均があれば現値との比較、無ければ妥当感を1〜2文)",
  "timing": "『なぜ今か』タイミングの所感(押し目/ブレイク/待ち を根拠つきで1〜2文)",
  "stance": "強気 / 中立 / 弱気 のいずれか1語",
  "overall": "総合所感(初心者向けにやさしく2〜3文。最後に必ず『最終判断はご自身で』と添える)"
}"""


def _client():
    """APIキーが設定済みなら Anthropic クライアントを返す。無ければ None。"""
    key = config.ANTHROPIC_API_KEY
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


def has_key():
    return bool(config.ANTHROPIC_API_KEY)


def _fmt(v, suffix="", dash="不明"):
    return f"{v}{suffix}" if v not in (None, "") else dash


def gather_inputs(code, name, df, info):
    """株価df(Close等)とyfinanceのinfo辞書から、AIに渡すsnapshotとnewsを作る。
    df は当日NaNバー除外済みであること。戻り値: (snap, news_items)。"""
    from indicators import add_all_indicators
    from signals import judge

    dfi = add_all_indicators(df)
    sig = judge(dfi)
    last = dfi.iloc[-1]
    price = sig["price"]
    info = info or {}

    rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
    inst = info.get("heldPercentInstitutions")
    insider = info.get("heldPercentInsiders")
    rg = info.get("revenueGrowth")
    eg = info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")
    tmean = info.get("targetMeanPrice")
    thigh = info.get("targetHighPrice")
    tlow = info.get("targetLowPrice")
    nan = info.get("numberOfAnalystOpinions")
    reco = info.get("recommendationKey")
    vol_avg = float(dfi["Volume"].iloc[-21:-1].mean()) if len(dfi) >= 21 else 0.0
    lo = float(df["Close"].min())
    hi = float(df["Close"].max())
    pos = round((price - lo) / (hi - lo) * 100) if hi > lo else None
    cur = "" if str(code).endswith(".T") else "$"

    snap = {
        "cur": cur,
        "price": round(price),
        "chg_pct": round((price / dfi["Close"].iloc[-2] - 1) * 100, 2),
        "trend": "上昇" if last["SMA25"] > last["SMA75"] else "下降",
        "rsi": round(sig["rsi"]),
        "range_pos": f"{pos}%（0=安値,100=高値）" if pos is not None else None,
        "per": round(info["trailingPE"], 1) if info.get("trailingPE") else None,
        "pbr": round(info["priceToBook"], 2) if info.get("priceToBook") else None,
        "dividend_yield": round(rate / price * 100, 2) if rate else None,
        "rev_growth": round(rg * 100, 1) if rg is not None else None,
        "earn_growth": round(eg * 100, 1) if eg is not None else None,
        "inst_pct": round(inst * 100, 1) if inst else None,
        "insider_pct": round(insider * 100, 1) if insider else None,
        "vol_ratio": f"{float(last['Volume'])/vol_avg:.1f}倍" if vol_avg else None,
        "target_mean": round(tmean) if tmean else None,
        "target_high": round(thigh) if thigh else None,
        "target_low": round(tlow) if tlow else None,
        "num_analysts": nan,
        "reco": reco,
    }

    import news as news_mod
    items = news_mod.fetch_news(name, limit=12)
    return snap, items


def build_prompt(name, code, snap, news_items):
    cur = snap.get("cur", "")
    news_lines = "\n".join(
        f"- [{ {1:'好',-1:'悪',0:'中'}.get(it.get('sentiment',0),'中') }] {it['title']}（{it.get('source','')}）"
        for it in (news_items or [])[:12]
    ) or "（ニュースなし）"

    tgt = "不明"
    if snap.get("target_mean"):
        tgt = (f"平均 {cur}{snap['target_mean']:,}（高 {cur}{_fmt(snap.get('target_high'))} / "
               f"低 {cur}{_fmt(snap.get('target_low'))}、アナリスト{_fmt(snap.get('num_analysts'))}人、"
               f"レーティング {_fmt(snap.get('reco'))}）")

    return f"""# 分析対象
銘柄: {name}（{code}）

# 材料
## 株価・テクニカル
- 現在値: {cur}{_fmt(snap.get('price'))}
- 前日比: {_fmt(snap.get('chg_pct'), '%')}
- トレンド: {_fmt(snap.get('trend'))}（SMA25とSMA75の関係）
- RSI(14): {_fmt(snap.get('rsi'))}
- 52週レンジ内の位置: {_fmt(snap.get('range_pos'))}

## ファンダ・業績(成長率)
- PER: {_fmt(snap.get('per'), '倍')}
- PBR: {_fmt(snap.get('pbr'), '倍')}
- 配当利回り: {_fmt(snap.get('dividend_yield'), '%')}
- 売上成長率(前年比): {_fmt(snap.get('rev_growth'), '%')}
- 利益成長率(前年比): {_fmt(snap.get('earn_growth'), '%')}

## 保有・需給（機関投資家の動向）
- 機関投資家の保有比率: {_fmt(snap.get('inst_pct'), '%')}
- 内部者(役員等)の保有比率: {_fmt(snap.get('insider_pct'), '%')}
- 直近の出来高(20日平均比): {_fmt(snap.get('vol_ratio'))}

## アナリスト目標株価
- {tgt}

## 直近ニュース見出し（好=好材料/悪=悪材料/中=中立 の簡易判定つき）
{news_lines}

# 指示
上記の材料だけを根拠に、この銘柄を「個別成長株」として評価し、
次のJSON形式**のみ**で日本語で出力してください（他の文字は一切出力しない）:

{SHAPE}
"""


def _extract_json(text):
    """モデル出力からJSON部分を取り出してdict化。失敗時は例外。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def analyze_stock(name, code, snap, news_items, model=None):
    """1銘柄をAI分析。戻り値: (result_dict, error_str)。成功時 error=None。"""
    client = _client()
    if client is None:
        return None, "APIキーが未設定です。secret_local.py か Streamlitのsecretsに ANTHROPIC_API_KEY を入れてください。"

    model = model or config.AI_MODEL
    prompt = build_prompt(name, code, snap, news_items)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return None, f"AI呼び出しでエラー: {e}"

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    try:
        data = _extract_json(text)
    except Exception:
        return None, "AIの出力をJSONとして読めませんでした。もう一度お試しください。"

    try:
        data["_usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    except Exception:
        pass
    data["_model"] = model
    return data, None


def comment_on_scan(hits, risks=None, model=None):
    """通知用: 当日のスキャン結果(買い候補hits)とリスクrisksを、AIが1〜2行でやさしく総括。
    戻り値: コメント文字列(失敗時は空文字)。"""
    client = _client()
    if client is None:
        return ""
    buy = "、".join(f"{h['name']}({h['type']})" for h in (hits or [])[:6]) or "なし"
    rk = "、".join(f"{r['name']}({r['reason']})" for r in (risks or [])[:6]) or "なし"
    prompt = (
        "あなたは投資初心者向けの冷静なアドバイザーです。今日の日本株スクリーニング結果を、"
        "煽らず2行以内でやさしく総括してください(投資助言ではなく判断材料)。\n"
        f"買いサイン点灯: {buy}\n急変・下落で要注意: {rk}\n"
        "出力はコメント文のみ(前置き不要、絵文字は1つまで)。"
    )
    try:
        resp = client.messages.create(
            model=model or config.AI_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    except Exception:
        return ""


if __name__ == "__main__":
    import sys
    import _net  # noqa: F401
    import yfinance as yf
    from universe import UNIVERSE

    code = sys.argv[1] if len(sys.argv) > 1 else "6920.T"
    name = UNIVERSE.get(code, code)
    df = yf.download(code, period="1y", interval="1d", auto_adjust=True, progress=False)
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    info = {}
    try:
        info = yf.Ticker(code).info
    except Exception:
        pass
    snap, items = gather_inputs(code, name, df, info)
    result, err = analyze_stock(name, code, snap, items)
    if err:
        print("ERROR:", err)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
