# ai_analysis.py 【Claude(AI)による個別成長株の分析】
# ニュース＋テクニカル＋ファンダの材料をClaudeに渡し、
# 「成長ドライバー / 強み(堀) / 好材料 / リスク / 割安度の所感 / 総合スタンス」を
# 構造化(JSON)で返してもらう。ダッシュボードの「🤖 AI分析」タブから呼ばれる。
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
    "渡された材料(株価・テクニカル・ファンダ・ニュース見出し)だけを根拠に、"
    "成長株としての魅力とリスクを率直に評価してください。"
    "重要な制約: ①これは投資助言ではなく判断材料であること。"
    "②材料に無いことを断定しない(不明なら『材料からは不明』と書く)。"
    "③ニュース見出しに別企業や無関係なものが混じっていたら無視する。"
    "④誇張や煽りをせず、弱点・リスクも必ず挙げる。"
    "⑤機関投資家・大口の保有や需給は重要な観点として必ず触れる"
    "(ただし日本株は公開データが乏しいことが多いので、材料が無ければ"
    "『公開材料からは限定的』と正直に書く。憶測で具体的な機関名や金額を作らない)。"
    "出力は、指定したJSON以外を一切含めないこと(前置き・コードフェンス・解説は禁止)。"
)

# 期待するJSONの形(モデルに提示する)
SHAPE = """{
  "summary": "3行以内の要約(この銘柄の現状を一言で)",
  "growth_drivers": ["成長の原動力を箇条書きで2〜4個"],
  "strengths": ["競争上の強み・参入障壁(堀)を2〜4個"],
  "positive_catalysts": ["直近の好材料・追い風(ニュース等から)"],
  "risks": ["主なリスク・弱点を2〜4個(必須)"],
  "institutional_take": "機関投資家・大口の保有/需給に関する所感(1〜2文。材料が乏しければ『公開材料からは限定的』と明記)",
  "valuation_take": "PER/PBR/配当などから見た割高・割安の所感(1〜2文)",
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


def _fmt(v, suffix="", dash="不明"):
    return f"{v}{suffix}" if v not in (None, "") else dash


def build_prompt(name, code, snap, news_items):
    cur = "" if str(code).endswith(".T") else "$"
    news_lines = "\n".join(
        f"- [{ {1:'好',-1:'悪',0:'中'}.get(it.get('sentiment',0),'中') }] {it['title']}（{it.get('source','')}）"
        for it in (news_items or [])[:12]
    ) or "（ニュースなし）"

    return f"""# 分析対象
銘柄: {name}（{code}）

# 材料
## 株価・テクニカル
- 現在値: {cur}{_fmt(snap.get('price'))}
- 前日比: {_fmt(snap.get('chg_pct'), '%')}
- トレンド: {_fmt(snap.get('trend'))}（SMA25とSMA75の関係）
- RSI(14): {_fmt(snap.get('rsi'))}
- 52週レンジ内の位置: {_fmt(snap.get('range_pos'))}

## ファンダメンタル
- PER: {_fmt(snap.get('per'), '倍')}
- PBR: {_fmt(snap.get('pbr'), '倍')}
- 配当利回り: {_fmt(snap.get('dividend_yield'), '%')}

## 保有・需給（機関投資家の動向）
- 機関投資家の保有比率: {_fmt(snap.get('inst_pct'), '%')}
- 内部者(役員等)の保有比率: {_fmt(snap.get('insider_pct'), '%')}
- 直近の出来高(20日平均比): {_fmt(snap.get('vol_ratio'))}

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
    # 念のためコードフェンスを除去
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)  # 最初の{...}を拾う
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

    # 使用トークン(費用の目安表示用)
    try:
        data["_usage"] = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
    except Exception:
        pass
    data["_model"] = model
    return data, None


if __name__ == "__main__":
    import sys
    import _net  # noqa: F401
    import yfinance as yf
    from universe import UNIVERSE
    from indicators import add_all_indicators
    from signals import judge
    import news as news_mod

    code = sys.argv[1] if len(sys.argv) > 1 else "6920.T"
    name = UNIVERSE.get(code, code)
    df = yf.download(code, period="1y", interval="1d", auto_adjust=True, progress=False)
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])  # 当日の未確定(NaN)バーを除外
    dfi = add_all_indicators(df)
    sig = judge(dfi)
    last = dfi.iloc[-1]
    info = {}
    try:
        info = yf.Ticker(code).info
    except Exception:
        pass
    rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
    inst = info.get("heldPercentInstitutions")
    insider = info.get("heldPercentInsiders")
    vol_avg = float(dfi["Volume"].iloc[-21:-1].mean())
    snap = {
        "price": round(sig["price"]),
        "chg_pct": round((sig["price"] / dfi["Close"].iloc[-2] - 1) * 100, 2),
        "trend": "上昇" if last["SMA25"] > last["SMA75"] else "下降",
        "rsi": round(sig["rsi"]),
        "per": round(info["trailingPE"], 1) if info.get("trailingPE") else None,
        "pbr": round(info["priceToBook"], 2) if info.get("priceToBook") else None,
        "dividend_yield": round(rate / sig["price"] * 100, 2) if rate else None,
        "inst_pct": round(inst * 100, 1) if inst else None,
        "insider_pct": round(insider * 100, 1) if insider else None,
        "vol_ratio": f"{float(last['Volume'])/vol_avg:.1f}倍" if vol_avg else None,
    }
    items = news_mod.fetch_news(name, limit=12)
    result, err = analyze_stock(name, code, snap, items)
    if err:
        print("ERROR:", err)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
