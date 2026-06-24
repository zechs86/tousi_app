# ai_chat.py 【AI投資相談チャット(ツールを使うエージェント)】
# ユーザーの自由な質問に対し、Claudeが必要なツール(銘柄データ取得/全体スキャン/リスク検知)を
# 自分で呼び出して材料を集め、初心者にやさしく答える。
# 中島聡さんのclaude-code-mainの「ツール使用ループ」設計を参考に、Python向けに簡素化。
#
# ダッシュボードの「💬 AIに相談」タブから respond() を呼ぶ。

import warnings
warnings.simplefilter("ignore")

import json

import config
from universe import UNIVERSE

# Claudeに渡すツール定義(Anthropic形式)
TOOLS = [
    {
        "name": "get_stock",
        "description": (
            "指定した銘柄の最新データを取得する。"
            "株価・前日比・トレンド・RSI・52週レンジ位置・PER・PBR・配当利回り・"
            "売上/利益成長率・機関投資家保有比率・アナリスト目標株価・直近ニュース見出し を返す。"
            "個別銘柄について答える前に必ずこれで実データを取得すること。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "銘柄コード。日本株は末尾.T(例 7203.T)、米国株はそのまま(例 AAPL)"}
            },
            "required": ["code"],
        },
    },
    {
        "name": "scan_market",
        "description": "監視ユニバース全体をスキャンし、買いサイン(押し目/急騰ブレイク)が点灯した銘柄を強い順に返す。「今の買い候補は?」等で使う。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "market_risks",
        "description": "監視ユニバースで急落・急変(暴落)している要注意銘柄を返す。「危ない銘柄は?」「暴落してるのは?」等で使う。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_my_portfolio",
        "description": "ユーザーのペーパートレード(練習)の保有銘柄・含み損益・現金・目標株価を返す。「私の保有は?」「含み損が大きいのは?」「私のポートフォリオへの助言は?」等、ユーザー自身の持ち株に関する相談で使う。",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_LABEL = {"get_stock": "📊 銘柄データ取得", "scan_market": "🔎 全体スキャン",
              "market_risks": "⚠️ リスク検知", "get_my_portfolio": "💰 保有ポートフォリオ"}


def _client():
    key = config.ANTHROPIC_API_KEY
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


def has_key():
    return bool(config.ANTHROPIC_API_KEY)


def _universe_hint():
    # Claudeが銘柄コードを選べるよう、監視ユニバースを一覧で渡す
    return "、".join(f"{c}={n}" for c, n in UNIVERSE.items())


SYSTEM = (
    "あなたは日本株・米国株に詳しい、初心者にやさしい投資アドバイザーです。"
    "ユーザーは投資初心者で、特に『個別成長株投資』と『機関投資家の動向』に関心があります。"
    "必ずツールで実データを取得してから具体的な数字を述べてください(数字を記憶や憶測で作らない)。"
    "回答は日本語で、専門用語にはやさしい補足を付け、要点→根拠の順で簡潔に。"
    "強み・好材料だけでなくリスク・弱点も必ず示すこと。"
    "これは投資助言ではなく判断材料です。断定や『必ず儲かる』表現は避け、最後に『最終判断はご自身で』と添えてください。"
    "比較を聞かれたら各銘柄を get_stock で取得して並べて比べること。"
    "扱える主な銘柄(コード=名前): " + _universe_hint()
)


def _resolve_code(q):
    """ユーザー/モデルが渡した文字列を、ユニバースの正式コードに寄せる。"""
    q = (q or "").strip()
    if q in UNIVERSE:
        return q
    up = q.upper()
    if up in UNIVERSE:
        return up
    if up + ".T" in UNIVERSE:
        return up + ".T"
    for c, n in UNIVERSE.items():
        if q and (q in n or n in q):
            return c
    return q  # 見つからなければそのまま(yfinanceに任せる)


def _tool_get_stock(inp):
    import _net  # noqa: F401
    import yfinance as yf
    import ai_analysis

    code = _resolve_code(inp.get("code", ""))
    name = UNIVERSE.get(code, code)
    df = yf.download(code, period="1y", interval="1d", auto_adjust=True, progress=False)
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    if df.empty:
        return json.dumps({"error": f"{code} のデータが取得できませんでした"}, ensure_ascii=False)
    info = {}
    try:
        info = yf.Ticker(code).info
    except Exception:
        pass
    snap, items = ai_analysis.gather_inputs(code, name, df, info)
    snap["name"] = name
    snap["code"] = code
    snap["news_titles"] = [it["title"] for it in (items or [])[:8]]
    return json.dumps(snap, ensure_ascii=False)


def _tool_scan(inp):
    from scanner import scan
    hits = scan()
    out = [{"name": h["name"], "code": h["code"], "type": h["type"], "strength": h["strength"],
            "price": h["price"], "rsi": h["rsi"]} for h in hits[: config.SCAN_TOP_N]]
    return json.dumps({"count": len(hits), "top": out}, ensure_ascii=False)


def _tool_risks(inp):
    from risk import detect_risks
    rs = detect_risks()
    out = [{"name": r["name"], "code": r["code"], "reason": r["reason"],
            "price": r["price"], "chg_1d": r["chg_1d"], "chg_5d": r["chg_5d"]}
           for r in rs[: config.SCAN_TOP_N]]
    return json.dumps({"count": len(rs), "risks": out}, ensure_ascii=False)


def run_tool(name, inp):
    try:
        if name == "get_stock":
            return _tool_get_stock(inp)
        if name == "scan_market":
            return _tool_scan(inp)
        if name == "market_risks":
            return _tool_risks(inp)
        return json.dumps({"error": f"unknown tool {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def respond(history, model=None, max_iters=6, on_tool=None):
    """history: [{'role':'user'/'assistant','content': ...}] を受け、ツール使用ループを回して
    最終回答テキストを返す。戻り値: (final_text, updated_history, error)。
    on_tool(label, input_dict) があればツール呼び出し毎に通知(UIの進捗表示用)。"""
    client = _client()
    if client is None:
        return None, history, "APIキーが未設定です。"

    msgs = list(history)
    for _ in range(max_iters):
        try:
            resp = client.messages.create(
                model=model or config.AI_MODEL,
                max_tokens=2000,
                system=SYSTEM,
                tools=TOOLS,
                messages=msgs,
            )
        except Exception as e:
            return None, history, f"AI呼び出しでエラー: {e}"

        msgs.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "tool_use":
            results = []
            for b in resp.content:
                if getattr(b, "type", "") == "tool_use":
                    if on_tool:
                        on_tool(TOOL_LABEL.get(b.name, b.name), b.input)
                    out = run_tool(b.name, b.input)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
            msgs.append({"role": "user", "content": results})
            continue

        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return text, msgs, None

    return "(ツール呼び出しが多くなりすぎました。質問を分けてお試しください)", msgs, None


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "イオン(8267.T)は成長株として買い時か、機関投資家の動向も含めて教えて"
    text, _, err = respond([{"role": "user", "content": q}],
                           on_tool=lambda l, i: print(f"[tool] {l} {i}"))
    print("\n=== 回答 ===\n", err or text)
