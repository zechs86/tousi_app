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
    # yfinanceが一時的に例外を投げてもページごと落とさない(クラウドのYahoo一時エラー対策)。
    try:
        df = yf.download(code, period=period, interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty:
            return None
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])  # 当日の未確定(NaN)バーを除外
        return df if not df.empty else None
    except Exception:
        return None


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

# ===== ページ移動ナビ(タブ風) =====
# 💬AI相談は従量課金のため AI_CHAT_ENABLED=True の時だけ表示(getattrで安全に)。
CHAT_ON = bool(getattr(config, "AI_CHAT_ENABLED", False))
PAGES = ["🔎 今ここ！", "📊 銘柄分析", "🤖 AI分析"] + (["💬 AI相談"] if CHAT_ON else []) + ["💰 ペーパー", "🗓️ 予定", "📰 ニュース"]

# 他のボタンからのページ移動要求(_goto)を、ナビ生成前に反映
if "_goto" in st.session_state:
    _g = st.session_state.pop("_goto")
    if _g in PAGES:
        st.session_state["nav_page"] = _g
if st.session_state.get("nav_page") not in PAGES:
    st.session_state["nav_page"] = PAGES[0]

# ラジオをピル風に見せるCSS
st.markdown("""<style>
div[role="radiogroup"]{flex-direction:row;flex-wrap:wrap;gap:8px;}
div[role="radiogroup"] label{background:#151A23;border:1px solid rgba(255,255,255,.07);
  border-radius:999px;padding:7px 15px;margin:0;font-weight:600;}
div[role="radiogroup"] label:has(input:checked){
  background:linear-gradient(135deg,rgba(0,224,164,.25),rgba(108,99,255,.25));border-color:rgba(0,224,164,.5);}
div[role="radiogroup"] label>div:first-child{display:none;}
</style>""", unsafe_allow_html=True)

page = st.radio("ページ", PAGES, horizontal=True, key="nav_page", label_visibility="collapsed")

# 銘柄選択の既定(全ページ共通で使う)
codes = list(UNIVERSE.keys())
default_idx = codes.index("8267.T") if "8267.T" in codes else 0

# ===== 利用者(任意・共有時に人ごとに分ける) =====
# サイドバー(左の控えめな場所)に置く。一度入れれば保持される(URLにも記憶)。
if "user_name" not in st.session_state:
    st.session_state["user_name"] = st.query_params.get("u", "")
with st.sidebar:
    st.markdown("### 👤 利用者")
    st.text_input("名前（友人と共有する時だけ）", key="user_name",
                  placeholder="例: ken（空欄=ゲスト）")
    _uval = st.session_state["user_name"].strip()
    if _uval and st.query_params.get("u", "") != _uval:
        st.query_params["u"] = _uval  # URLに記憶(ブックマークで次回も自動)
    st.caption(f"現在: {'ゲスト共用' if not _uval else _uval}")
    st.caption("一度入れれば保持されます。自分のURLをブックマークすると次回も自動で入ります。")
USER = _uval or "guest"

# ============ ページ: スキャナー ============
if page == "🔎 今ここ！":
    import favorites
    # ⭐ お気に入りウォッチ: 登録銘柄の今の状態(トレンド・押し目/待ち・レンジ位置)を一覧
    favs = favorites.load(USER)
    if favs:
        st.markdown("#### ⭐ お気に入りウォッチ")
        st.caption("登録銘柄の今の状態。🟢=押し目買いゾーン（上昇中の一時的な下げ）、↗=上昇、↘=下降（待ち）。")
        for code in favs:
            df = get_price(code)
            if df is None or len(df) < 80:   # SMA75 を出せる行数が必要
                continue
            last = add_all_indicators(df).iloc[-1]
            price = float(last["Close"])
            rsi = float(last["RSI"])
            uptrend = bool(last["SMA25"] > last["SMA75"])
            lo, hi = float(df["Close"].min()), float(df["Close"].max())
            pos = (price - lo) / (hi - lo) * 100 if hi != lo else 50
            zone = "安値圏" if pos <= 30 else ("高値圏" if pos >= 70 else "中間")
            in_dip = uptrend and rsi <= getattr(config, "DIP_RSI", 40)
            if in_dip:
                status, scls = "🟢 押し目買いゾーン", "up"
            elif uptrend:
                status, scls = "↗ 上昇トレンド", "up"
            else:
                status, scls = "↘ 下降（待ち）", "down"
            cm = "" if code.endswith(".T") else "$"
            zcls = "up" if zone == "安値圏" else ("down" if zone == "高値圏" else "")
            name = UNIVERSE.get(code, code.replace(".T", ""))
            st.markdown(f"""
<div class="card" style="padding:12px 16px">
  <div class="sc-top"><span class="sc-name" style="font-size:1rem">⭐ {name}（{code}）</span>
    <span class="m-value {scls}" style="font-size:.95rem">{status}</span></div>
  <div class="sc-foot">{cm}{price:,.0f} ／ RSI {rsi:.0f} ／ 1年レンジ <span class="{zcls}">{pos:.0f}%（{zone}）</span></div>
</div>
""", unsafe_allow_html=True)
        st.divider()

    cL, cR = st.columns([3, 1])
    cL.markdown("#### 全銘柄スキャン")
    if cR.button("🔄 更新", width='stretch'):
        run_scan_cached.clear()
    st.caption("買いサインが点灯した銘柄を強い順に表示（約110銘柄を分析）。")

    try:
        with st.spinner("スキャン中…（初回は30秒ほど）"):
            hits = run_scan_cached()
    except Exception:
        hits = []
        st.error("スキャンに失敗しました（データ取得の一時的な不調かも）。少し待って🔄更新を押してください。")

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
            if st.button(f"📝 {h['name']}をペーパーで買う準備", key=f"toscanbuy_{h['code']}",
                         width='stretch'):
                sh = 100 if h["is_jp"] else 1
                st.session_state["paper_prefill"] = {
                    "code": h["code"], "name": h["name"], "shares": sh,
                    "target": round(h["target"]), "stop": round(h["stop"]), "price": round(h["price"]),
                }
                st.session_state["paper_buy_sel"] = h["code"]
                st.session_state["paper_buy_sh"] = sh
                st.session_state["_goto"] = "💰 ペーパー"  # ペーパーへ移動
                st.rerun()

# ============ ページ: 銘柄分析 ============
if page == "📊 銘柄分析":
    import favorites
    favs = favorites.load(USER)
    # ⭐お気に入りをワンタップ表示
    if favs:
        st.markdown("**⭐ お気に入り**")
        fcols = st.columns(min(len(favs), 4))
        for i, fc in enumerate(favs):
            if fcols[i % 4].button(UNIVERSE.get(fc, fc), key=f"favpick_{fc}",
                                   width='stretch'):
                st.session_state["chart_sel"] = fc
                st.rerun()

    st.session_state.setdefault("chart_sel", "8267.T" if "8267.T" in codes else codes[0])
    cc1, cc2 = st.columns([4, 1])
    code = cc1.selectbox("銘柄を選ぶ", options=codes, key="chart_sel",
                         format_func=lambda c: f"{UNIVERSE[c]}（{c}）")
    is_f = favorites.is_fav(code, USER)
    if cc2.button("⭐解除" if is_f else "☆登録", key="fav_toggle", width='stretch'):
        favorites.toggle(code, USER)
        st.rerun()

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
        st.plotly_chart(fig, width='stretch')

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
        st.plotly_chart(figr, width='stretch')

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


if page == "🤖 AI分析":
    st.markdown("#### 🤖 AI銘柄分析")
    st.caption("選んだ成長株を、ニュース＋ファンダからClaude(AI)が評価します。実行ごとに少額のAPI費用がかかります（1回あたり数円程度）。")

    codes_ai = list(UNIVERSE.keys())
    code3 = st.selectbox("分析する銘柄", options=codes_ai, index=default_idx,
                         format_func=lambda c: f"{UNIVERSE[c]}（{c}）", key="ai_select")
    name3 = UNIVERSE[code3]

    if not config.ANTHROPIC_API_KEY:
        st.warning("⚠️ APIキーが未設定です。`src/secret_local.py` か Streamlitのsecrets に `ANTHROPIC_API_KEY` を設定してください。", icon="⚠️")

    run_ai = st.button("🤖 この銘柄をAI分析する", width='stretch',
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

# ============ ページ: AI相談チャット (CHAT_ON=Trueの時だけ表示) ============
if CHAT_ON and page == "💬 AI相談":
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

# ============ タブ5: ペーパートレード ============
@st.cache_data(ttl=900, show_spinner=False)
def last_price(code):
    try:
        df = get_price(code, period="5d")
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


if page == "💰 ペーパー":
    import paper
    st.markdown("#### 💰 ペーパートレード（仮想資金で練習）")
    st.caption("実弾の前に“練習売買”。仮想資金で買い/売りを記録し、成績を見られます。"
               "※クラウドではアプリが眠ると記録が消えることがあります（手元PCでは永続）。")

    pstate = paper.load(USER)
    st.caption(f"👤 {'ゲスト共用' if USER == 'guest' else USER} さんのペーパー口座")

    # 「今ここ！」から準備した買い注文の案内
    prefill = st.session_state.get("paper_prefill")
    if prefill:
        cpf = "" if str(prefill["code"]).endswith(".T") else "$"
        st.success(
            f"🔎 『{prefill['name']}』を準備しました（{prefill['shares']}株）。"
            f"利確 {cpf}{prefill['target']:,} ／ 損切り {cpf}{prefill['stop']:,}。"
            f"下の「🟢 買う」で確定すると、利確・損切りも自動でセットされます。", icon="🛒")

    # 保有銘柄の現在値を取得して集計
    prices = {}
    for code_p in pstate["positions"]:
        prices[code_p] = last_price(code_p)
    summ = paper.summary(pstate, prices)
    paper.record_equity(pstate, summ["total"], USER)  # 今日の総資産を記録
    pstats = paper.stats(pstate)

    pcls = "up" if summ["ret_pct"] >= 0 else "down"
    arrow = "▲" if summ["ret_pct"] >= 0 else "▼"
    rcls = "up" if pstats["total_realized"] >= 0 else "down"
    st.markdown(f"""
<div class="card">
  <div class="mrow">
    <div class="metric"><div class="m-label">総資産</div><div class="m-value">¥{summ['total']:,.0f}</div></div>
    <div class="metric"><div class="m-label">現金</div><div class="m-value">¥{summ['cash']:,.0f}</div></div>
    <div class="metric"><div class="m-label">評価額</div><div class="m-value">¥{summ['holdings_value']:,.0f}</div></div>
    <div class="metric"><div class="m-label">リターン</div><div class="m-value {pcls}">{arrow}{abs(summ['ret_pct']):.1f}%</div></div>
  </div>
  <div class="mrow" style="margin-top:8px">
    <div class="metric"><div class="m-label">勝率</div><div class="m-value">{pstats['win_rate']:.0f}%</div></div>
    <div class="metric"><div class="m-label">取引回数</div><div class="m-value">{pstats['trades']}</div></div>
    <div class="metric"><div class="m-label">実現損益</div><div class="m-value {rcls}">{pstats['total_realized']:+,}円</div></div>
    <div class="metric"><div class="m-label">初期資金</div><div class="m-value">¥{pstate['start_cash']:,.0f}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

    ec = pstate.get("equity_curve", [])
    if len(ec) >= 2:
        fige = go.Figure()
        fige.add_trace(go.Scatter(x=[e["date"] for e in ec], y=[e["total"] for e in ec],
                                  name="総資産", line=dict(color=UP, width=2), fill="tozeroy",
                                  fillcolor="rgba(0,224,164,.08)"))
        fige.add_hline(y=pstate["start_cash"], line_dash="dash", line_color=INK, opacity=.5)
        fige.update_layout(template="plotly_dark", height=200, margin=dict(l=0, r=0, t=8, b=0),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#EAF0F6"), showlegend=False)
        fige.update_xaxes(gridcolor="rgba(255,255,255,.05)")
        fige.update_yaxes(gridcolor="rgba(255,255,255,.05)")
        st.caption("資産推移（点線＝初期資金）")
        st.plotly_chart(fige, width='stretch')

    # 成績の内訳（月別実現損益・銘柄別成績）
    mrows = paper.monthly_realized(pstate)
    srows = paper.by_symbol(pstate)
    if mrows or srows:
        with st.expander("📈 成績の内訳（月別・銘柄別）"):
            if mrows:
                st.caption("月別の実現損益")
                figm = go.Figure()
                figm.add_trace(go.Bar(
                    x=[m["month"] for m in mrows],
                    y=[m["realized"] for m in mrows],
                    marker_color=[UP if m["realized"] >= 0 else DOWN for m in mrows]))
                figm.update_layout(template="plotly_dark", height=200,
                                   margin=dict(l=0, r=0, t=8, b=0),
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font=dict(color="#EAF0F6"), showlegend=False)
                figm.update_xaxes(gridcolor="rgba(255,255,255,.05)")
                figm.update_yaxes(gridcolor="rgba(255,255,255,.05)", zeroline=True,
                                  zerolinecolor="rgba(255,255,255,.2)")
                st.plotly_chart(figm, width='stretch')
            if srows:
                st.caption("銘柄別の成績（実現損益の大きい順）")
                for r in srows:
                    rc = "up" if r["realized"] >= 0 else "down"
                    sgn = "+" if r["realized"] >= 0 else ""
                    st.markdown(f"""
<div class="card" style="padding:10px 14px">
  <div class="sc-top"><span class="sc-name" style="font-size:.95rem">{r['name']}（{r['code']}）</span>
    <span class="m-value {rc}" style="font-size:.95rem">{sgn}{r['realized']:,}円</span></div>
  <div class="sc-foot">{r['trades']}回 ／ 勝率 {r['win_rate']:.0f}%（{r['wins']}勝{r['trades']-r['wins']}敗）</div>
</div>
""", unsafe_allow_html=True)

    # 保有ポジション
    if summ["rows"]:
        st.markdown("##### 保有ポジション")
        for r in summ["rows"]:
            cur = "" if r["code"].endswith(".T") else "$"
            plcls = "up" if r["pl"] >= 0 else "down"
            sgn = "+" if r["pl"] >= 0 else ""
            tgt = pstate.get("targets", {}).get(r["code"])
            stp = pstate.get("stops", {}).get(r["code"])
            tgt_line = ""
            if tgt:
                if r["cur"] >= tgt:
                    tgt_line = f'<div class="sc-foot" style="color:{UP}">🎯 利確目標 {cur}{tgt:,.0f} 到達！利確を検討</div>'
                else:
                    rem = (tgt / r["cur"] - 1) * 100
                    tgt_line = f'<div class="sc-foot">🎯 利確目標 {cur}{tgt:,.0f}（あと+{rem:.1f}%）</div>'
            if stp:
                if r["cur"] <= stp:
                    tgt_line += f'<div class="sc-foot" style="color:{DOWN}">🛑 損切りライン {cur}{stp:,.0f} 割れ！損切りを検討</div>'
                else:
                    dn = (1 - stp / r["cur"]) * 100
                    tgt_line += f'<div class="sc-foot">🛑 損切りライン {cur}{stp:,.0f}（あと-{dn:.1f}%）</div>'
            st.markdown(f"""
<div class="card" style="padding:12px 16px">
  <div class="sc-top"><span class="sc-name" style="font-size:1rem">{r['name']}（{r['code']}）</span>
    <span class="m-value {plcls}" style="font-size:1rem">{sgn}{r['pl']:,.0f}円（{sgn}{r['pl_pct']:.1f}%）</span></div>
  <div class="sc-foot">{r['shares']}株 ／ 平均 {cur}{r['avg_cost']:,.0f} → 現在 {cur}{r['cur']:,.0f} ／ 評価額 ¥{r['value']:,.0f}</div>
  {tgt_line}
</div>
""", unsafe_allow_html=True)

        with st.expander("🎯 利確・🛑 損切りラインを設定/変更"):
            tcode = st.selectbox("銘柄", options=list(pstate["positions"].keys()),
                                 format_func=lambda c: f"{pstate['positions'][c]['name']}（{c}）",
                                 key="paper_tgt_sel")
            cur_t = float(pstate.get("targets", {}).get(tcode, 0.0))
            cur_s = float(pstate.get("stops", {}).get(tcode, 0.0))
            # 銘柄を切り替えたら、その銘柄の現在の設定値を入力欄に反映
            if st.session_state.get("_tgt_last_sel") != tcode:
                st.session_state["paper_tgt_val"] = cur_t
                st.session_state["paper_stop_val"] = cur_s
                st.session_state["_tgt_last_sel"] = tcode
            e1, e2 = st.columns(2)
            tval = e1.number_input("🎯 利確（0で解除）", min_value=0.0, step=10.0, key="paper_tgt_val")
            sval = e2.number_input("🛑 損切り（0で解除）", min_value=0.0, step=10.0, key="paper_stop_val")
            if st.button("設定する", key="paper_tgt_btn"):
                paper.set_target(pstate, tcode, tval, USER)
                paper.set_stop(pstate, tcode, sval, USER)
                st.success("利確・損切りを設定しました。"); st.rerun()
    else:
        st.info("まだ保有なし。下の「買う」で練習を始めましょう。")

    # 売買フォーム
    c_buy, c_sell = st.columns(2)
    with c_buy:
        st.markdown("##### 🟢 買う")
        codes_b = list(UNIVERSE.keys())
        bcode = st.selectbox("銘柄", options=codes_b, index=default_idx,
                             format_func=lambda c: f"{UNIVERSE[c]}（{c}）", key="paper_buy_sel")
        bp = last_price(bcode)
        cur_b = "" if bcode.endswith(".T") else "$"
        if bp:
            st.caption(f"現在値 {cur_b}{bp:,.0f}")
        bsh = st.number_input("株数", min_value=1, value=100, step=100, key="paper_buy_sh")
        if bp:
            st.caption(f"必要資金 ¥{bp*bsh:,.0f}")
        # 「今ここ！」から準備された銘柄なら、確定で利確/損切りも自動セット
        pf = st.session_state.get("paper_prefill")
        btn_label = "買う（仮想・確定）" if (pf and pf["code"] == bcode) else "買う（仮想）"
        if st.button(btn_label, width='stretch', key="paper_buy_btn"):
            if bp:
                _, err = paper.buy(pstate, bcode, UNIVERSE[bcode], bsh, bp, USER)
                if err:
                    st.error(err)
                else:
                    msg_extra = ""
                    if pf and pf["code"] == bcode:
                        paper.set_target(pstate, bcode, pf["target"], USER)  # 利確
                        paper.set_stop(pstate, bcode, pf["stop"], USER)       # 損切り
                        msg_extra = f"／利確{cur_b}{pf['target']:,}・損切り{cur_b}{pf['stop']:,}も設定"
                        st.session_state.pop("paper_prefill", None)
                    st.success(f"{UNIVERSE[bcode]} を {bsh}株 買いました（仮想）{msg_extra}"); st.rerun()
            else:
                st.error("現在値が取得できませんでした。")
    with c_sell:
        st.markdown("##### 🔴 売る")
        held = list(pstate["positions"].keys())
        if not held:
            st.caption("保有銘柄がありません。")
        else:
            scode = st.selectbox("銘柄", options=held,
                                 format_func=lambda c: f"{pstate['positions'][c]['name']}（{c}）",
                                 key="paper_sell_sel")
            maxsh = pstate["positions"][scode]["shares"]
            st.caption(f"保有 {maxsh}株")
            ssh = st.number_input("株数", min_value=1, max_value=maxsh, value=maxsh, step=100, key="paper_sell_sh")
            if st.button("売る（仮想）", width='stretch', key="paper_sell_btn"):
                sp = last_price(scode)
                if sp:
                    _, err = paper.sell(pstate, scode, ssh, sp, USER)
                    if err:
                        st.error(err)
                    else:
                        st.success(f"{pstate['positions'].get(scode,{}).get('name',scode)} を {ssh}株 売りました（仮想）"); st.rerun()
                else:
                    st.error("現在値が取得できませんでした。")

    # 履歴
    if pstate["history"]:
        with st.expander("📜 売買履歴"):
            for h in pstate["history"][:20]:
                cur_h = "" if h["code"].endswith(".T") else "$"
                rz = f"／実現{h['realized']:+,}円" if "realized" in h else ""
                mark = "🟢" if h["action"] == "買" else "🔴"
                st.write(f"{mark}{h['time']} {h['name']} {h['action']} {h['shares']}株 @{cur_h}{h['price']:,.0f}{rz}")

    if st.button("🗑️ ペーパー口座をリセット", key="paper_reset"):
        paper.reset(USER)
        st.rerun()

# ============ ページ: 予定（優待・決算カレンダー） ============
if page == "🗓️ 予定":
    import calendar_view
    import favorites
    import paper
    import store
    st.markdown("#### 🗓️ 予定（株主優待・決算）")
    st.caption("優待の権利付最終日と、お気に入り＋保有銘柄の次回決算日をまとめて確認できます。"
               "※日本株は決算日が取れない/ズレることがあります。")

    # --- 株主優待カレンダー ---
    st.markdown("##### 🎁 株主優待カレンダー")
    # 利用者ごとに保存した「優待の年間価値(円)」を読み、総合利回りに反映
    yval_key = f"yutaival:{favorites._safe_user(USER)}"
    yvals = store.get_json(yval_key, {}) or {}
    with st.spinner("優待スケジュール計算中…"):
        yrows = calendar_view.yutai_schedule(yutai_values=yvals)
    if not yrows:
        st.info("優待銘柄が未登録です。config.py の YUTAI_RECORD_MONTHS に追加できます。")

    # 優待の価値を入力して総合利回りを出す(プログラム不要・利用者ごとに保存)
    if yrows:
        with st.expander("🎁 優待の価値を入れて総合利回りを見る"):
            st.caption("優待の『年間価値(円)』を入れると 総合利回り(配当＋優待) が出ます。"
                       "イオンのオーナーズカードは“買物○%キャッシュバック”なので、"
                       "あなたの年間イオン利用額×3%程度が目安です（例: 年20万円利用→6000円）。")
            new_vals = dict(yvals)
            changed_y = False
            for r in yrows:
                cur_v = int(yvals.get(r["code"], 0) or 0)
                v = st.number_input(f"{r['name']}（{r['code']}）の優待 年間価値（円・0で無し）",
                                    min_value=0, step=1000, value=cur_v, key=f"yval_{r['code']}")
                if int(v) != cur_v:
                    new_vals[r["code"]] = int(v)
                    changed_y = True
            if st.button("保存する", key="yval_save"):
                store.set_json(yval_key, {k: v for k, v in new_vals.items() if v})
                st.success("保存しました。総合利回りに反映します。"); st.rerun()
    for r in yrows:
        cm = "" if r["code"].endswith(".T") else "$"
        urgent = "up" if r["days"] <= 14 else ""
        price_line = ""
        if r["price"] is not None:
            zcls = "up" if r["zone"] == "安値圏" else ("down" if r["zone"] == "高値圏" else "")
            price_line = (f'<div class="sc-foot">現在 {cm}{r["price"]:,.0f}／'
                          f'1年レンジ <span class="{zcls}">{r["pos"]:.0f}%（{r["zone"]}）</span></div>')
            # 利回り(配当・優待・総合)。取れたものだけ表示。
            yparts = []
            if r.get("div_yield") is not None:
                yparts.append(f'配当{r["div_yield"]:.2f}%')
            if r.get("yutai_yield") is not None:
                yparts.append(f'優待{r["yutai_yield"]:.2f}%')
            if r.get("total_yield") is not None and len(yparts) >= 2:
                yparts.append(f'<span class="up">総合{r["total_yield"]:.2f}%</span>')
            if yparts:
                unit_txt = f'（100株 {cm}{r["unit_cost"]:,.0f}）' if r.get("unit_cost") else ''
                price_line += f'<div class="sc-foot">利回り {" ／ ".join(yparts)} {unit_txt}</div>'
        st.markdown(f"""
<div class="card" style="padding:12px 16px">
  <div class="sc-top"><span class="sc-name" style="font-size:1rem">🎁 {r['name']}（{r['code']}）</span>
    <span class="m-value {urgent}" style="font-size:1rem">あと{r['days']}日</span></div>
  <div class="sc-foot">権利付最終日 <b>{r['kenri']}</b> ／ 権利確定 {r['record']}</div>
  {price_line}
</div>
""", unsafe_allow_html=True)

    # --- 決算カレンダー ---
    st.markdown("##### 📅 決算カレンダー（お気に入り＋保有）")
    ecodes = list(dict.fromkeys(list(favorites.load(USER)) + list(paper.load(USER).get("positions", {}))))
    if not ecodes:
        st.info("お気に入り（⭐）や保有銘柄がありません。先に登録すると決算日が並びます。")
    else:
        with st.spinner("決算日を取得中…"):
            erows = calendar_view.earnings_schedule(ecodes)
        if not erows:
            st.caption("対象銘柄の決算日が取得できませんでした（日本株はデータが無いことがあります）。")
        for r in erows:
            urgent = "up" if r["days"] <= 7 else ""
            st.markdown(f"""
<div class="card" style="padding:10px 14px">
  <div class="sc-top"><span class="sc-name" style="font-size:.95rem">📅 {r['name']}（{r['code']}）</span>
    <span class="m-value {urgent}" style="font-size:.95rem">あと{r['days']}日</span></div>
  <div class="sc-foot">次回決算 <b>{r['date']}</b></div>
</div>
""", unsafe_allow_html=True)

# ============ ページ: ニュース ============
if page == "📰 ニュース":
    code2 = st.selectbox("ニュースを見る銘柄", options=codes, index=default_idx,
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

        # AIニュース要約(既定オフ・押した時だけ課金)。config.AI_NEWS_SUMMARY_ENABLED=Trueで表示。
        if getattr(config, "AI_NEWS_SUMMARY_ENABLED", False):
            import ai_analysis
            if not ai_analysis.has_key():
                st.caption("🤖 AI要約はAPIキー未設定のため使えません（config.ANTHROPIC_API_KEY）。")
            else:
                st.caption("🤖 押した時だけAIが見出しを要約します（1回およそ¥1〜2の従量課金）。")
                if st.button("🤖 AIでニュースを要約する", key="news_ai_sum", width='stretch'):
                    with st.spinner("AIが要約中…"):
                        text, err = ai_analysis.summarize_news(name2, items)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["news_ai_result"] = {"code": code2, "text": text}
                res = st.session_state.get("news_ai_result")
                if res and res.get("code") == code2 and res.get("text"):
                    st.markdown(f'<div class="card">🤖 <b>AIニュース要約</b><br>'
                                f'{res["text"].replace(chr(10), "<br>")}</div>',
                                unsafe_allow_html=True)

st.markdown('<div class="foot-note">Powered by yfinance ・ ntfy ・ Streamlit｜サイン=必勝ではありません</div>', unsafe_allow_html=True)
