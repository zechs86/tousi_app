# dashboard.py 【ブラウザで見る投資ダッシュボード(スマホ対応・ネオン調デザイン)】
# 起動: dashboard.bat をダブルクリック / または
#   .\.venv\Scripts\streamlit run src\dashboard.py
# ブラウザが開きます。同じWiFiのスマホからは http://(PCのIP):8501 で見られます。

import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

from universe import UNIVERSE
from indicators import add_all_indicators
from signals import judge
import config

st.set_page_config(page_title="投資ダッシュボード", page_icon="📈",
                   layout="centered", initial_sidebar_state="collapsed")

# ===== 配色（ネオン調） =====
UP = "#00E0A4"      # 上げ・好材料（ミントグリーン）
DOWN = "#FF5C7C"    # 下げ・悪材料（コーラルピンク）
NEUTRAL = "#FFC861" # 中立・様子見（アンバー）
INK = "#9AA6B2"     # うすい文字
CARD = "#151A23"    # カード背景

# ===== カスタムCSS（ここで一気にオシャレにする） =====
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Noto+Sans+JP:wght@400;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter','Noto Sans JP',sans-serif; }}

/* Streamlit標準の余白・ヘッダーを引き締める */
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 780px; }}

/* 背景にうっすらグラデーション */
.stApp {{
  background:
    radial-gradient(1100px 500px at 15% -10%, rgba(0,224,164,.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(108,99,255,.12), transparent 55%),
    #0B0E14;
}}

/* ヒーロー（タイトル帯） */
.hero {{
  border-radius: 22px;
  padding: 26px 24px;
  background: linear-gradient(135deg, rgba(0,224,164,.18), rgba(108,99,255,.18));
  border: 1px solid rgba(255,255,255,.08);
  box-shadow: 0 10px 40px rgba(0,0,0,.35);
  margin-bottom: 18px;
}}
.hero h1 {{ font-size: 1.9rem; font-weight: 800; margin: 0; letter-spacing:.5px;
  background: linear-gradient(90deg,#00E0A4,#7CE0FF 60%,#9D8BFF);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.hero p {{ color: {INK}; margin: 6px 0 0; font-size: .9rem; }}

/* タブを丸ピル風に */
.stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
.stTabs [data-baseweb="tab"] {{
  background: {CARD}; border-radius: 999px; padding: 8px 16px;
  border: 1px solid rgba(255,255,255,.06); font-weight: 600;
}}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(135deg, rgba(0,224,164,.25), rgba(108,99,255,.25));
  border-color: rgba(0,224,164,.5);
}}

/* 汎用カード */
.card {{
  background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,0)) , {CARD};
  border: 1px solid rgba(255,255,255,.07);
  border-radius: 18px; padding: 16px 18px; margin-bottom: 14px;
  box-shadow: 0 6px 24px rgba(0,0,0,.28);
}}
.signal-card {{ border-left: 5px solid {INK}; }}
.signal-card.up {{ border-left-color: {UP}; box-shadow: 0 0 0 1px rgba(0,224,164,.12), 0 8px 26px rgba(0,0,0,.3); }}
.signal-card.hot {{ border-left-color: {NEUTRAL}; box-shadow: 0 0 0 1px rgba(255,200,97,.12), 0 8px 26px rgba(0,0,0,.3); }}

.sc-top {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
.sc-name {{ font-size: 1.12rem; font-weight: 800; }}
.badge {{ font-size:.72rem; font-weight:700; padding:4px 10px; border-radius:999px;
  border:1px solid rgba(255,255,255,.12); white-space:nowrap; }}
.badge.up {{ color:{UP}; background: rgba(0,224,164,.12); }}
.badge.hot {{ color:{NEUTRAL}; background: rgba(255,200,97,.12); }}
.strength {{ font-size:.78rem; color:{INK}; }}

/* メトリクス行 */
.mrow {{ display:flex; gap:10px; margin-top:12px; }}
.metric {{ flex:1; background: rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.06);
  border-radius:12px; padding:10px 12px; text-align:center; }}
.m-label {{ font-size:.7rem; color:{INK}; letter-spacing:.3px; }}
.m-value {{ font-size:1.08rem; font-weight:800; margin-top:2px; }}
.m-value.up {{ color:{UP}; }} .m-value.down {{ color:{DOWN}; }}
.sc-foot {{ margin-top:10px; font-size:.78rem; color:{INK}; }}

/* 大きな判定バッジ */
.verdict {{ display:inline-block; font-weight:800; padding:8px 16px; border-radius:999px; font-size:1rem; }}
.verdict.buy {{ color:{UP}; background:rgba(0,224,164,.14); border:1px solid rgba(0,224,164,.4); }}
.verdict.sell {{ color:{DOWN}; background:rgba(255,92,124,.14); border:1px solid rgba(255,92,124,.4); }}
.verdict.hold {{ color:{NEUTRAL}; background:rgba(255,200,97,.14); border:1px solid rgba(255,200,97,.4); }}

/* ニュース行 */
.news-item {{ display:flex; gap:10px; padding:10px 0; border-bottom:1px solid rgba(255,255,255,.06); }}
.news-dot {{ font-size:1rem; }}
.news-src {{ color:{INK}; font-size:.72rem; }}

.foot-note {{ color:{INK}; font-size:.74rem; text-align:center; margin-top:24px; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def get_price(code, period="1y"):
    df = yf.download(code, period=period, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])  # 当日の未確定(NaN)バーを除外
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def run_scan_cached():
    from scanner import scan
    return scan()


@st.cache_data(ttl=1800, show_spinner=False)
def get_info(code):
    try:
        return yf.Ticker(code).info
    except Exception:
        return {}


def fmt(v, cur):
    return f"{cur}{v:,.0f}"


# ===== ヒーロー =====
st.markdown("""
<div class="hero">
  <h1>📈 投資ダッシュボード</h1>
  <p>テクニカル × ファンダ × ニュースで「今ここ！」を見える化。<br>※投資助言ではなく判断材料です。最終判断はご自身で。</p>
</div>
""", unsafe_allow_html=True)

tab_scan, tab_chart, tab_ai, tab_talk, tab_news = st.tabs(
    ["🔎 今ここ！", "📊 銘柄分析", "🤖 AI分析", "💬 AI相談", "📰 ニュース"])

# ============ タブ1: スキャナー ============
with tab_scan:
    cL, cR = st.columns([3, 1])
    cL.markdown("#### 全銘柄スキャン")
    if cR.button("🔄 更新", use_container_width=True):
        run_scan_cached.clear()
    st.caption("買いサインが点灯した銘柄を強い順に表示（約110銘柄を分析）。")

    with st.spinner("スキャン中…（初回は30秒ほど）"):
        hits = run_scan_cached()

    if not hits:
        st.markdown('<div class="card">😴 今日はサイン点灯銘柄なし。<br><span style="color:#9AA6B2">様子見の相場です。</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p style="color:#9AA6B2;font-size:.85rem">点灯 <b style="color:#EAF0F6">{len(hits)}</b> 件 ／ 上位 {min(len(hits), config.SCAN_TOP_N)} 件を表示</p>', unsafe_allow_html=True)
        for h in hits[:config.SCAN_TOP_N]:
            cur = "" if h["is_jp"] else "$"
            kind = "up" if h["type"] == "押し目" else "hot"
            emoji = "🟢" if h["type"] == "押し目" else "🚀"
            afford = "✅ 10万円で買える" if h["affordable"] else "⚠️ 10万円では足りない"
            st.markdown(f"""
<div class="card signal-card {kind}">
  <div class="sc-top">
    <span class="sc-name">{emoji} {h['name']}</span>
    <span class="badge {kind}">{h['type']}</span>
  </div>
  <div class="strength">強さスコア {h['strength']:.0f} ／ RSI {h['rsi']:.0f}</div>
  <div class="mrow">
    <div class="metric"><div class="m-label">株価</div><div class="m-value">{fmt(h['price'],cur)}</div></div>
    <div class="metric"><div class="m-label">損切り目安</div><div class="m-value down">{fmt(h['stop'],cur)}</div></div>
    <div class="metric"><div class="m-label">利確目安</div><div class="m-value up">{fmt(h['target'],cur)}</div></div>
  </div>
  <div class="sc-foot">{afford}</div>
</div>
""", unsafe_allow_html=True)

# ============ タブ2: 銘柄分析 ============
with tab_chart:
    codes = list(UNIVERSE.keys())
    default_idx = codes.index("8267.T") if "8267.T" in codes else 0
    code = st.selectbox("銘柄を選ぶ", options=codes, index=default_idx,
                        format_func=lambda c: f"{UNIVERSE[c]}（{c}）")
    df = get_price(code)
    if df is None:
        st.error("データが取得できませんでした。")
    else:
        dfi = add_all_indicators(df)
        sig = judge(dfi)
        last = dfi.iloc[-1]
        uptrend = bool(last["SMA25"] > last["SMA75"])
        cur = "" if code.endswith(".T") else "$"
        prev = dfi["Close"].iloc[-2]
        chg = (sig["price"] / prev - 1) * 100
        chg_cls = "up" if chg >= 0 else "down"
        chg_arrow = "▲" if chg >= 0 else "▼"

        vmap = {"買い": ("buy", "🟢 買い"), "売り": ("sell", "🔴 売り"), "様子見": ("hold", "🟡 様子見")}
        vcls, vlabel = vmap[sig["verdict"]]

        st.markdown(f"""
<div class="card">
  <div class="sc-top">
    <span class="sc-name">{UNIVERSE[code]}</span>
    <span class="verdict {vcls}">{vlabel}（{sig['score']:+d}）</span>
  </div>
  <div class="mrow">
    <div class="metric"><div class="m-label">現在値</div><div class="m-value">{fmt(sig['price'],cur)}</div></div>
    <div class="metric"><div class="m-label">前日比</div><div class="m-value {chg_cls}">{chg_arrow}{abs(chg):.2f}%</div></div>
    <div class="metric"><div class="m-label">RSI</div><div class="m-value">{sig['rsi']:.0f}</div></div>
    <div class="metric"><div class="m-label">トレンド</div><div class="m-value {'up' if uptrend else 'down'}">{'上昇' if uptrend else '下降'}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

        plot = dfi.tail(150)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot.index, open=plot["Open"], high=plot["High"], low=plot["Low"], close=plot["Close"],
            name="株価", increasing_line_color=UP, decreasing_line_color=DOWN,
            increasing_fillcolor=UP, decreasing_fillcolor=DOWN))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["SMA25"], name="SMA25",
                                 line=dict(color="#7CE0FF", width=1.4)))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["SMA75"], name="SMA75",
                                 line=dict(color="#9D8BFF", width=1.4)))
        fig.update_layout(
            template="plotly_dark", height=400, margin=dict(l=0, r=0, t=8, b=0),
            xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#EAF0F6"),
            legend=dict(orientation="h", y=1.04, x=0, bgcolor="rgba(0,0,0,0)"))
        fig.update_xaxes(gridcolor="rgba(255,255,255,.05)")
        fig.update_yaxes(gridcolor="rgba(255,255,255,.05)")
        st.plotly_chart(fig, use_container_width=True)

        figr = go.Figure()
        figr.add_trace(go.Scatter(x=plot.index, y=plot["RSI"], name="RSI",
                                  line=dict(color="#00E0A4", width=1.6), fill="tozeroy",
                                  fillcolor="rgba(0,224,164,.08)"))
        figr.add_hline(y=70, line_dash="dash", line_color=DOWN, opacity=.6)
        figr.add_hline(y=30, line_dash="dash", line_color=UP, opacity=.6)
        figr.update_layout(template="plotly_dark", height=170, margin=dict(l=0, r=0, t=8, b=0),
                           yaxis_range=[0, 100], paper_bgcolor="rgba(0,0,0,0)",
                           plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#EAF0F6"), showlegend=False)
        figr.update_xaxes(gridcolor="rgba(255,255,255,.05)")
        figr.update_yaxes(gridcolor="rgba(255,255,255,.05)")
        st.caption("RSI（70超=買われすぎ／30割れ=売られすぎ）")
        st.plotly_chart(figr, use_container_width=True)

        info = get_info(code)
        per = info.get("trailingPE")
        pbr = info.get("priceToBook")
        rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
        dy = (rate / sig["price"] * 100) if rate else None
        st.markdown(f"""
<div class="card">
  <div class="m-label" style="margin-bottom:8px">ファンダメンタル</div>
  <div class="mrow">
    <div class="metric"><div class="m-label">PER</div><div class="m-value">{f'{per:.1f}倍' if per else '—'}</div></div>
    <div class="metric"><div class="m-label">PBR</div><div class="m-value">{f'{pbr:.2f}倍' if pbr else '—'}</div></div>
    <div class="metric"><div class="m-label">配当利回り</div><div class="m-value up">{f'{dy:.2f}%' if dy else '—'}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ============ タブ3: AI分析 ============
def _ai_list(title, items, color):
    if not items:
        return ""
    lis = "".join(f"<li>{x}</li>" for x in items)
    return (f'<div style="margin-top:10px"><div class="m-label" style="color:{color}">{title}</div>'
            f'<ul style="margin:6px 0 0;padding-left:20px;line-height:1.7">{lis}</ul></div>')


with tab_ai:
    st.markdown("#### 🤖 AI銘柄分析")
    st.caption("選んだ成長株を、ニュース＋ファンダからClaude(AI)が評価します。実行ごとに少額のAPI費用がかかります（1回あたり数円程度）。")

    codes_ai = list(UNIVERSE.keys())
    code3 = st.selectbox("分析する銘柄", options=codes_ai, index=default_idx,
                         format_func=lambda c: f"{UNIVERSE[c]}（{c}）", key="ai_select")
    name3 = UNIVERSE[code3]

    if not config.ANTHROPIC_API_KEY:
        st.warning("⚠️ APIキーが未設定です。`src/secret_local.py` か Streamlitのsecrets に `ANTHROPIC_API_KEY` を設定してください。", icon="⚠️")

    run_ai = st.button("🤖 この銘柄をAI分析する", use_container_width=True,
                       disabled=not config.ANTHROPIC_API_KEY)

    skey = f"ai_result_{code3}"
    if run_ai:
        with st.spinner("AIが分析中…（10〜20秒ほど）"):
            df3 = get_price(code3)
            if df3 is None:
                st.session_state[skey] = (None, "株価データが取得できませんでした。")
            else:
                import ai_analysis
                snap3, items3 = ai_analysis.gather_inputs(code3, name3, df3, get_info(code3))
                st.session_state[skey] = ai_analysis.analyze_stock(name3, code3, snap3, items3)

    if skey in st.session_state:
        result, err = st.session_state[skey]
        if err:
            st.error(err)
        else:
            smap = {"強気": ("buy", "🟢 強気"), "中立": ("hold", "🟡 中立"), "弱気": ("sell", "🔴 弱気")}
            scls, slabel = smap.get(result.get("stance", "中立"), ("hold", "🟡 中立"))
            body = ""
            body += _ai_list("🚀 成長ドライバー", result.get("growth_drivers"), UP)
            body += _ai_list("🛡️ 強み・堀", result.get("strengths"), "#7CE0FF")
            body += _ai_list("📈 好材料", result.get("positive_catalysts"), NEUTRAL)
            body += _ai_list("⚠️ リスク・弱点", result.get("risks"), DOWN)

            def _para(label, val):
                if not val:
                    return ""
                return (f'<div style="margin-top:12px"><div class="m-label" style="color:{INK}">{label}</div>'
                        f'<div style="margin-top:4px;color:#EAF0F6;line-height:1.7">{val}</div></div>')

            paras = ""
            paras += _para("📊 業績・決算トレンド", result.get("earnings_take"))
            paras += _para("🏛️ 機関投資家・需給", result.get("institutional_take"))
            paras += _para("💰 割安度の所感", result.get("valuation_take"))
            paras += _para("🎯 目標株価の所感", result.get("target_take"))
            paras += _para("⏱️ なぜ今か（タイミング）", result.get("timing"))
            paras += _para("📝 総合所感", result.get("overall"))
            st.markdown(f"""
<div class="card">
  <div class="sc-top">
    <span class="sc-name">{name3}</span>
    <span class="verdict {scls}">{slabel}</span>
  </div>
  <div style="margin-top:8px;color:#EAF0F6;line-height:1.7">{result.get('summary','')}</div>
  {body}
  {paras}
</div>
""", unsafe_allow_html=True)
            u = result.get("_usage")
            if u:
                st.caption(f"モデル: {result.get('_model','')}／使用トークン 入力{u['in']:,}・出力{u['out']:,}（参考: この1回で約数円）")
        st.caption("※AIの評価は判断材料であり、的中を保証するものではありません。最終判断はご自身で。")

# ============ タブ4: AI相談チャット ============
with tab_talk:
    st.markdown("#### 💬 AIに相談")
    st.caption("自由に質問すると、AIが必要なデータを自分で取りに行って答えます。"
               "例：「今の買い候補は？」「ソニーは成長株として買い時？」「半導体で機関投資家が買ってるのは？」")

    if not config.ANTHROPIC_API_KEY:
        st.warning("⚠️ APIキーが未設定です。`ANTHROPIC_API_KEY` を設定してください。", icon="⚠️")

    st.session_state.setdefault("chat_api", [])
    st.session_state.setdefault("chat_display", [])

    if st.session_state.chat_display:
        if st.button("🗑️ 会話をリセット"):
            st.session_state.chat_api = []
            st.session_state.chat_display = []
            st.rerun()

    for m in st.session_state.chat_display:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            if m.get("tools"):
                st.caption("🔧 使ったツール: " + " / ".join(m["tools"]))
            st.markdown(m["text"])

    q = st.chat_input("質問を入力…", disabled=not config.ANTHROPIC_API_KEY)
    if q:
        st.session_state.chat_display.append({"role": "user", "text": q})
        st.session_state.chat_api.append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            tools_used = []
            with st.spinner("AIが調べています…（データ取得で20〜40秒かかることがあります）"):
                import ai_chat
                text, api, err = ai_chat.respond(
                    st.session_state.chat_api,
                    on_tool=lambda label, inp: tools_used.append(label),
                )
            if err:
                st.error(err)
            else:
                if tools_used:
                    st.caption("🔧 使ったツール: " + " / ".join(tools_used))
                st.markdown(text)
                st.session_state.chat_api = api
                st.session_state.chat_display.append({"role": "assistant", "text": text, "tools": tools_used})

# ============ タブ5: ニュース ============
with tab_news:
    codes_n = list(UNIVERSE.keys())
    code2 = st.selectbox("ニュースを見る銘柄", options=codes_n, index=default_idx,
                         format_func=lambda c: f"{UNIVERSE[c]}（{c}）", key="news_select")
    name2 = UNIVERSE[code2]
    with st.spinner("ニュース取得中…"):
        import news as news_mod
        items = news_mod.fetch_news(name2, limit=12)
    if not items:
        st.markdown('<div class="card">ニュースが見つかりませんでした。</div>', unsafe_allow_html=True)
    else:
        score = sum(it["sentiment"] for it in items)
        if score > 0:
            mood_cls, mood = "up", "🟢 やや好材料"
        elif score < 0:
            mood_cls, mood = "down", "🔴 やや悪材料"
        else:
            mood_cls, mood = "hold", "🟡 中立"
        rows = ""
        for it in items:
            dot = "🟢" if it["sentiment"] > 0 else ("🔴" if it["sentiment"] < 0 else "⚪")
            rows += (f'<div class="news-item"><span class="news-dot">{dot}</span>'
                     f'<span>{it["title"]}<br><span class="news-src">{it["source"]}</span></span></div>')
        st.markdown(f"""
<div class="card">
  <div class="sc-top">
    <span class="sc-name">{name2} のニュース</span>
    <span class="verdict {mood_cls}">{mood}</span>
  </div>
  <div style="margin-top:8px">{rows}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="foot-note">Powered by yfinance ・ ntfy ・ Streamlit｜サイン=必勝ではありません</div>', unsafe_allow_html=True)
