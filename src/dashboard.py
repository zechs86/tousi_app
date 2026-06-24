# dashboard.py 【ブラウザで見る投資ダッシュボード(スマホ対応)】
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

st.set_page_config(page_title="投資ダッシュボード", page_icon="📈", layout="centered")


@st.cache_data(ttl=900, show_spinner=False)
def get_price(code, period="1y"):
    df = yf.download(code, period=period, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    return df


@st.cache_data(ttl=1800, show_spinner=True)
def run_scan_cached():
    from scanner import scan
    return scan()


@st.cache_data(ttl=1800, show_spinner=False)
def get_info(code):
    try:
        return yf.Ticker(code).info
    except Exception:
        return {}


st.title("📈 投資ダッシュボード")
st.caption("※投資助言ではなく判断材料です。最終判断はご自身で。")

tab_scan, tab_chart, tab_news = st.tabs(["🔎 今ここ！", "📊 銘柄分析", "📰 ニュース"])

with tab_scan:
    st.subheader("全銘柄スキャン")
    st.write("買いサインが点灯した銘柄を強い順に表示します（約110銘柄を分析）。")
    if st.button("🔄 最新スキャンを実行", use_container_width=True):
        run_scan_cached.clear()
    with st.spinner("スキャン中..."):
        hits = run_scan_cached()
    if not hits:
        st.info("今日はサイン点灯銘柄なし（様子見の相場）。")
    else:
        for h in hits[:config.SCAN_TOP_N]:
            cur = "" if h["is_jp"] else "$"
            emoji = "🟢" if h["type"] == "押し目" else "🚀"
            afford = "✅10万円で買える" if h["affordable"] else "⚠️10万円では足りない"
            with st.container(border=True):
                st.markdown(f"### {emoji} {h['name']}　**{h['type']}**（強さ {h['strength']:.0f}）")
                c1, c2, c3 = st.columns(3)
                c1.metric("株価", f"{cur}{h['price']:,.0f}")
                c2.metric("損切り目安", f"{cur}{h['stop']:,.0f}")
                c3.metric("利確目安", f"{cur}{h['target']:,.0f}")
                st.caption(f"RSI {h['rsi']:.0f}／{afford}")

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

        c1, c2, c3 = st.columns(3)
        c1.metric("現在値", f"{cur}{sig['price']:,.0f}")
        c2.metric("RSI", f"{sig['rsi']:.0f}")
        c3.metric("トレンド", "上昇" if uptrend else "下降")

        verdict_label = {"買い": "🟢買い", "売り": "🔴売り", "様子見": "🟡様子見"}[sig["verdict"]]
        st.markdown(f"**テクニカル判定: {verdict_label}**（点数 {sig['score']:+d}）")

        plot = dfi.tail(150)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=plot.index, open=plot["Open"], high=plot["High"],
                                     low=plot["Low"], close=plot["Close"], name="株価"))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["SMA25"], name="SMA25", line=dict(color="orange", width=1)))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["SMA75"], name="SMA75", line=dict(color="purple", width=1)))
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis_rangeslider_visible=False, legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

        figr = go.Figure()
        figr.add_trace(go.Scatter(x=plot.index, y=plot["RSI"], name="RSI", line=dict(color="teal")))
        figr.add_hline(y=70, line_dash="dash", line_color="red")
        figr.add_hline(y=30, line_dash="dash", line_color="green")
        figr.update_layout(height=180, margin=dict(l=0, r=0, t=10, b=0), yaxis_range=[0, 100])
        st.plotly_chart(figr, use_container_width=True)

        info = get_info(code)
        st.subheader("ファンダメンタル")
        f1, f2, f3 = st.columns(3)
        per = info.get("trailingPE")
        pbr = info.get("priceToBook")
        rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate")
        dy = (rate / sig["price"] * 100) if rate else None
        f1.metric("PER", f"{per:.1f}倍" if per else "—")
        f2.metric("PBR", f"{pbr:.2f}倍" if pbr else "—")
        f3.metric("配当利回り", f"{dy:.2f}%" if dy else "—")

with tab_news:
    codes_n = list(UNIVERSE.keys())
    code2 = st.selectbox("ニュースを見る銘柄", options=codes_n, index=default_idx,
                         format_func=lambda c: f"{UNIVERSE[c]}（{c}）", key="news_select")
    name2 = UNIVERSE[code2]
    with st.spinner("ニュース取得中..."):
        import news as news_mod
        items = news_mod.fetch_news(name2, limit=12)
    if not items:
        st.info("ニュースが見つかりませんでした。")
    else:
        score = sum(it["sentiment"] for it in items)
        mood = "🟢やや好材料" if score > 0 else ("🔴やや悪材料" if score < 0 else "🟡中立")
        st.markdown(f"**全体の雰囲気: {mood}**（スコア {score:+d}）")
        for it in items:
            mark = "🟢" if it["sentiment"] > 0 else ("🔴" if it["sentiment"] < 0 else "・")
            st.markdown(f"{mark} {it['title']}　<small>{it['source']}</small>", unsafe_allow_html=True)
