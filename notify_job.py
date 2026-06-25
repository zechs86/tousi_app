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
            tg = s.get("targets", {}).get(code)
            sp = s.get("stops", {}).get(code)

            k_t = f"{code}:target"
            if tg and cur >= tg:
                if not sent.get(k_t):
                    lines.append(f"🎯{who}{name} 利確ライン到達！ {cm}{cur:,.0f}（目標{cm}{tg:,.0f}）")
                    sent[k_t] = True
                    changed = True
            elif k_t in sent:       # 条件を外れたら次の到達でまた鳴らせるよう解除
                del sent[k_t]
                changed = True

            k_s = f"{code}:stop"
            if sp and cur <= sp:
                if not sent.get(k_s):
                    lines.append(f"🛑{who}{name} 損切りライン到達！ {cm}{cur:,.0f}（損切{cm}{sp:,.0f}）")
                    sent[k_s] = True
                    changed = True
            elif k_s in sent:
                del sent[k_s]
                changed = True
        if changed:
            try:
                paper.save(s, u)
            except Exception as e:
                print(f"alerts_sent 保存エラー({u}):", e)
    return "\n".join(lines), len(lines)


def main():
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
