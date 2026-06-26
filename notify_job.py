# notify_job.py
# 【自動通知ジョブ】GitHub Actions が朝・夜に自動実行します(PC不要)。
#   全銘柄をスキャン → 「今ここ！」候補の上位を ntfy でスマホに1通にまとめて通知。
#
# 手元テスト:  .\.venv\Scripts\python.exe notify_job.py
# 朝/夜の文言を変えたい時は、環境変数 RUN_LABEL に "朝" や "夜" を入れて実行。

import os
import sys
import warnings

warnings.simplefilter("ignore")

# src/ の中のモジュール(scanner, notify など)を import できるようにする
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import _net  # noqa: F401  日本語フォルダ対策(SSL)。yfinanceより先に。
import config
from scanner import scan
from notify import send_push
from risk import detect_risks
import ai_analysis
import paper
import store


def build_message(hits):
    """買いサインを、スマホで読みやすくまとめる。"""
    top = hits[: config.SCAN_TOP_N]
    lines = []
    for h in top:
        cur = "" if h["is_jp"] else "$"
        mark = "🟢" if h["type"] == "押し目" else "🚀"
        afford = "✅" if h["affordable"] else "⚠️"
        lines.append(
            f"{mark}{h['name']} {h['type']}(強{h['strength']:.0f})\n"
            f"　{cur}{h['price']:,.0f}／損切{cur}{h['stop']:,.0f}・利確{cur}{h['target']:,.0f} {afford}"
        )
    return "\n".join(lines)


def build_risk_message(risks):
    """急変・下落で要注意の銘柄をまとめる。"""
    lines = []
    for r in risks[: config.SCAN_TOP_N]:
        cur = "" if r["is_jp"] else "$"
        lines.append(f"🔻{r['name']} {r['reason']}（{cur}{r['price']:,.0f}）")
    return "\n".join(lines)


def _fetch_prices(codes):
    """保有銘柄の現在値(直近終値)を {code: price} で返す。失敗は除外。"""
    codes = list(codes)
    if not codes:
        return {}
    try:
        import pandas as pd
        import yfinance as yf
        data = yf.download(codes, period="5d", interval="1d", auto_adjust=True,
                           group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print("価格取得エラー:", e)
        return {}
    prices = {}
    multi = isinstance(data.columns, pd.MultiIndex)  # group_by='ticker'は単一銘柄でもMultiIndex
    for code in codes:
        try:
            sub = data[code] if multi else data
            sub = sub.dropna(subset=["Close"])
            if len(sub):
                prices[code] = float(sub["Close"].iloc[-1])
        except Exception:
            continue
    return prices


def _level_status(cur, level, kind, near_pct):
    """現在値が利確/損切りラインに対してどの段階か。
    戻り値: 'reached'(到達) / 'near'(あと near_pct% 以内) / None(まだ遠い・未設定)。"""
    if not level or level <= 0:
        return None
    if kind == "target":          # 利確: 上に到達
        if cur >= level:
            return "reached"
        if near_pct > 0 and cur >= level * (1 - near_pct / 100):
            return "near"
    else:                         # stop: 下に到達
        if cur <= level:
            return "reached"
        if near_pct > 0 and cur <= level * (1 + near_pct / 100):
            return "near"
    return None


def _watched_codes():
    """お気に入り＋ペーパー保有の全コード(全利用者の和集合)。決算カレンダー用。"""
    import favorites
    codes = set()
    users = set()
    try:
        users |= set(paper.all_users())
    except Exception:
        pass
    try:
        for k in store.list_keys("fav:*"):
            if k.startswith("fav:"):
                users.add(k[len("fav:"):])
            elif k.startswith("fav_"):
                users.add(k[len("fav_"):])
    except Exception:
        pass
    for u in users:
        try:
            codes |= set(favorites.load(u))
        except Exception:
            pass
        try:
            codes |= set(paper.load(u).get("positions", {}))
        except Exception:
            pass
    return codes


def build_earnings_reminder():
    """お気に入り/保有のうち、次の決算発表日が近い銘柄を知らせる(無料)。
    ※日本株はyfinanceに決算日が無い/ズレることがあるので、取れた範囲で表示する。"""
    remind_days = getattr(config, "EARNINGS_REMIND_DAYS", 0)
    if not remind_days or remind_days <= 0:
        return ""
    import calendar_view
    codes = list(_watched_codes())[:20]   # API回数を抑えるため上限
    if not codes:
        return ""
    lines = [f"📅{r['name']} 決算まであと{r['days']}日（{r['date']}）"
             for r in calendar_view.earnings_schedule(codes) if r["days"] <= remind_days]
    return "\n".join(lines)


def _dip_signal(code):
    """押し目シグナル判定。(押し目ゾーンか, 現在値, RSI, 上昇トレンドか) を返す。失敗時 None。
    改良③: 上昇トレンド(SMA25>SMA75)中に RSI<=config.DIP_RSI なら押し目買いゾーン。"""
    try:
        import pandas as pd
        import yfinance as yf
        from indicators import add_all_indicators
        df = yf.download(code, period="1y", interval="1d",
                         auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        if len(df) < 80:          # SMA75 を出すのに足りない
            return None
        last = add_all_indicators(df).iloc[-1]
        if pd.isna(last["SMA75"]) or pd.isna(last["RSI"]):
            return None
        uptrend = bool(last["SMA25"] > last["SMA75"])
        rsi = float(last["RSI"])
        in_dip = uptrend and rsi <= getattr(config, "DIP_RSI", 40)
        return in_dip, float(last["Close"]), rsi, uptrend
    except Exception:
        return None


def _trend_label(code):
    """銘柄の今の状態を短いラベルで返す。押し目/上昇/下降(待ち)。取れなければ空。"""
    r = _dip_signal(code)
    if r is None:
        return ""
    in_dip, _price, _rsi, uptrend = r
    if in_dip:
        return "🟢押し目買いゾーン"
    if uptrend:
        return "↗上昇トレンド"
    return "↘下降(待ち)"


def build_dip_alerts():
    """お気に入り銘柄が押し目買いゾーンに入ったら知らせる(利用者ごと)。
    入った時に1回だけ通知し、ゾーンを抜けたら再アーム。戻り値: (メッセージ, 件数)。"""
    if not getattr(config, "DIP_ALERT_ENABLED", True):
        return "", 0
    import favorites
    try:
        from universe import UNIVERSE
    except Exception:
        UNIVERSE = {}
    # 利用者を集める(ペーパー利用者 ∪ お気に入り利用者)
    users = set()
    try:
        users |= set(paper.all_users())
    except Exception:
        pass
    try:
        for k in store.list_keys("fav:*"):
            if k.startswith("fav:"):
                users.add(k[len("fav:"):])
            elif k.startswith("fav_"):
                users.add(k[len("fav_"):])
    except Exception:
        pass
    if not users:
        return "", 0
    # 利用者→お気に入りコード、と全コード集合
    user_codes, allcodes = {}, set()
    for u in users:
        try:
            fc = list(favorites.load(u))
        except Exception:
            fc = []
        user_codes[u] = fc
        allcodes |= set(fc)
    if not allcodes:
        return "", 0
    # 各コードのシグナルは1回だけ計算(共有)
    sig = {}
    for code in allcodes:
        r = _dip_signal(code)
        if r is not None:
            sig[code] = r
    lines, total = [], 0
    for u, codes_u in user_codes.items():
        key = f"dipsent:{u}"
        sent = set(store.get_json(key, []) or [])
        changed = False
        who = "" if u == "guest" else f"[{u}] "
        for code in codes_u:
            r = sig.get(code)
            if r is None:
                continue
            in_dip, price, rsi, _uptrend = r
            cm = "" if code.endswith(".T") else "$"
            name = UNIVERSE.get(code, code.replace(".T", ""))
            if in_dip:
                if code not in sent:
                    lines.append(f"🟢{who}{name} 押し目買いゾーン（上昇中・RSI{rsi:.0f}）{cm}{price:,.0f}")
                    sent.add(code)
                    changed = True
                    total += 1
            elif code in sent:        # ゾーンを抜けたら再アーム
                sent.discard(code)
                changed = True
        if changed:
            store.set_json(key, sorted(sent))
    return "\n".join(lines), total


def build_yutai_reminder():
    """株主優待の権利付最終日が近い銘柄を、残り日数＋現在値＋1年レンジ位置で知らせる。
    対象は watch.RECORD_MONTHS と config.YUTAI_RECORD_MONTHS の合算。
    残り日数が config.YUTAI_REMIND_DAYS 以下のものだけ。戻り値: メッセージ(該当なしは空)。"""
    remind_days = getattr(config, "YUTAI_REMIND_DAYS", 0)
    if not remind_days or remind_days <= 0:
        return ""
    import calendar_view
    lines = []
    for r in calendar_view.yutai_schedule():
        if r["days"] > remind_days:
            continue
        cm = "" if r["code"].endswith(".T") else "$"
        if r["price"] is not None:
            # 2行目に現在値・レンジ位置・配当利回り・トレンド状態を入れて“毎日ブリーフィング”化
            extras = [f"1年レンジ{r['pos']:.0f}%（{r['zone']}）"]
            if r.get("yutai_yield") is not None and r.get("total_yield") is not None:
                extras.append(f"総合利回り{r['total_yield']:.1f}%")
            elif r.get("div_yield") is not None:
                extras.append(f"配当{r['div_yield']:.1f}%")
            trend = _trend_label(r["code"])
            if trend:
                extras.append(trend)
            lines.append(f"🎁{r['name']} 優待まであと{r['days']}日（権利付最終日{r['kenri']}）\n"
                         f"　現在{cm}{r['price']:,.0f}・" + "・".join(extras))
        else:
            lines.append(f"🎁{r['name']} 優待まであと{r['days']}日（権利付最終日{r['kenri']}）")
    return "\n".join(lines)


def build_paper_alerts():
    """各利用者のペーパー保有が利確🎯/損切り🛑ラインに到達したら通知文を作る。
    同じ到達を毎回鳴らさないよう、状態(alerts_sent)で1回だけ通知し条件解除で再アーム。
    戻り値: (メッセージ文字列, 件数)。"""
    try:
        users = paper.all_users()
    except Exception as e:
        print("利用者一覧の取得エラー:", e)
        return "", 0
    if not users:
        return "", 0

    states = {}
    codes = set()
    for u in users:
        try:
            s = paper.load(u)
        except Exception:
            continue
        states[u] = s
        for code in s.get("positions", {}):
            if code in s.get("targets", {}) or code in s.get("stops", {}):
                codes.add(code)
    if not codes:
        return "", 0

    near_pct = getattr(config, "NEAR_ALERT_PCT", 0) or 0
    _RANK = {None: 0, "near": 1, "reached": 2}
    prices = _fetch_prices(codes)
    lines = []
    for u, s in states.items():
        sent = s.setdefault("alerts_sent", {})
        changed = False
        who = "" if u == "guest" else f"[{u}] "
        for code, pos in s.get("positions", {}).items():
            cur = prices.get(code)
            if cur is None:
                continue
            cm = "" if code.endswith(".T") else "$"
            name = pos.get("name", code)
            for kind, level, icon, word in (
                    ("target", s.get("targets", {}).get(code), "🎯", "利確"),
                    ("stop",   s.get("stops", {}).get(code),   "🛑", "損切り")):
                key = f"{code}:{kind}"
                status = _level_status(cur, level, kind, near_pct)
                prev = sent.get(key)
                # 正規化(旧データの True は reached 扱い)
                if prev is True:
                    prev = "reached"
                if status is None:                 # 圏外→マーカー解除して再アーム
                    if prev is not None:
                        sent.pop(key, None)
                        changed = True
                    continue
                if _RANK[status] > _RANK.get(prev, 0):   # 前進した時だけ通知
                    if status == "reached":
                        lines.append(f"{icon}{who}{name} {word}ライン到達！ {cm}{cur:,.0f}"
                                     f"（{word}{cm}{level:,.0f}）")
                    else:  # near = もうすぐ
                        rem = (level / cur - 1) * 100 if kind == "target" else (1 - level / cur) * 100
                        lines.append(f"{icon}{who}{name} もうすぐ{word}（あと{abs(rem):.1f}%） "
                                     f"{cm}{cur:,.0f}（{word}{cm}{level:,.0f}）")
                    sent[key] = status
                    changed = True
                elif status != prev:               # 後退(到達→near等)は無音で記録だけ
                    sent[key] = status
                    changed = True
        if changed:
            try:
                paper.save(s, u)
            except Exception as e:
                print(f"alerts_sent 保存エラー({u}):", e)
    return "\n".join(lines), len(lines)


def main():
    try:
        import appconfig
        appconfig.apply_to_config()  # ⚙️設定の保存値を反映(しきい値/トグル)
    except Exception as e:
        print("設定反映スキップ:", e)
    label = os.environ.get("RUN_LABEL", "").strip()
    prefix = f"【{label}のチェック】" if label else "【自動チェック】"

    # 先に「利確/損切り到達アラート」を確認(保有のフォロー)。到達があれば最優先で別通知。
    print("利確/損切り到達チェック中...")
    topic = (os.environ.get("NTFY_TOPIC") or "").strip() or None
    app_url = (os.environ.get("APP_URL") or getattr(config, "APP_URL", "") or "").strip()
    try:
        alert_msg, alert_n = build_paper_alerts()
    except Exception as e:
        print("到達チェックエラー:", e)
        alert_msg, alert_n = "", 0
    if alert_n:
        amsg = "🔔【利確/損切り 到達アラート】\n" + alert_msg + "\n\n※ペーパーのライン到達です。実弾の判断はご自身で。"
        if app_url:
            amsg += f"\n\n📱 アプリを開く: {app_url}"
        ok_a = send_push(amsg, title=f"Tousi ALERT x{alert_n}", tags="rotating_light",
                         priority="high", topic=topic, click=(app_url or None))
        print("アラート通知 送信成功" if ok_a else "アラート通知 送信失敗")

    print("スキャン中...")
    hits = scan()
    print("リスク検知中...")
    try:
        risks = detect_risks()
    except Exception as e:
        print("リスク検知エラー:", e)
        risks = []

    parts = [prefix.rstrip("】") + "】"]

    if hits:
        n = min(len(hits), config.SCAN_TOP_N)
        parts.append(f"\n🟢 買い候補 {len(hits)}件中 上位{n}件\n{build_message(hits)}")
        tags = "chart_with_upwards_trend"
    else:
        parts.append("\n🟢 買いサイン点灯なし（様子見）")
        tags = "coffee"

    if risks:
        parts.append(f"\n⚠️ 急変・下落で要注意 {len(risks)}件\n{build_risk_message(risks)}")
        tags = "warning"

    # お気に入りの押し目買いアラート(上昇トレンド中RSI≤40で点灯)
    try:
        dip_msg, dip_n = build_dip_alerts()
    except Exception as e:
        print("押し目アラートエラー:", e)
        dip_msg, dip_n = "", 0
    if dip_n:
        parts.append(f"\n🟢 お気に入りが押し目買いゾーン {dip_n}件\n{dip_msg}")

    # 株主優待カウントダウン(イオン優待など。権利付最終日が近いと表示)
    try:
        yutai = build_yutai_reminder()
    except Exception as e:
        print("優待リマインダーエラー:", e)
        yutai = ""
    if yutai:
        parts.append(f"\n🎁 株主優待カウントダウン\n{yutai}")

    # 決算カレンダー(お気に入り/保有で決算が近い銘柄)
    try:
        earn = build_earnings_reminder()
    except Exception as e:
        print("決算カレンダーエラー:", e)
        earn = ""
    if earn:
        parts.append(f"\n📅 決算が近い銘柄\n{earn}")

    # AIによる一言総括(config.AI_NOTIFY_COMMENT=True かつ APIキーがある時だけ。既定オフ=無課金)
    if getattr(config, "AI_NOTIFY_COMMENT", False):
        ai = ai_analysis.comment_on_scan(hits, risks)
        if ai:
            parts.append(f"\n🤖 {ai}")

    parts.append("\n※サイン/警告=必勝ではありません。最終判断はご自身で。")
    msg = "\n".join(parts)
    # ntfyの本文上限(約4096バイト)対策。日本語は1文字3バイトなので余裕をみて1100文字で打ち切る。
    if len(msg) > 1100:
        msg = msg[:1100] + "…(省略)"

    # 一番下にアプリURL(タップで開く)。env優先→configの順。
    app_url = (os.environ.get("APP_URL") or getattr(config, "APP_URL", "") or "").strip()
    if app_url:
        msg += f"\n\n📱 アプリを開く: {app_url}"

    title = f"Tousi: buy{len(hits)} / risk{len(risks)}"  # ntfyのTitleは英数字のみ

    # トピックは環境変数(GitHub Secrets)で上書き可。無ければ config.py の値を使う。
    # Secretに改行や空白が混じってもURLが壊れないよう strip する。
    topic = (os.environ.get("NTFY_TOPIC") or "").strip() or None
    ok = send_push(msg, title=title, tags=tags, priority="default", topic=topic,
                   click=(app_url or None))  # 通知タップでアプリを開く
    print("通知 送信成功" if ok else "通知 送信失敗")
    # GitHub Actions上で失敗を検知できるよう、失敗時は異常終了
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
