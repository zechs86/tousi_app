# appconfig.py 【アプリ設定の保存と反映】
# 非プログラマーでも ⚙️設定ページから しきい値/トグル を変えられるよう、
# 上書き可能な設定を store(Upstash) に保存し、起動時に config へ反映する。
#   ・dashboard.py … 起動時に apply_to_config() で反映（画面表示やウォッチ判定に効く）
#   ・notify_job.py … main()冒頭で apply_to_config()（朝夜通知のしきい値に効く）
# 保存はアプリ全体で1つ（キー "appcfg"）。利用者ごとではなく共通設定。

import store
import config

KEY = "appcfg"

# 上書きを許す設定: 名前 -> (型, 既定, ラベル, ヘルプ)
FIELDS = {
    "DIP_RSI":               ("int",  40,   "押し目とみなすRSI", "小さいほど厳しめ（深い押し目だけ通知）"),
    "DIP_ALERT_ENABLED":     ("bool", True, "押し目買いアラート", "お気に入りが押し目買いゾーンに入ったら通知"),
    "YUTAI_REMIND_DAYS":     ("int",  75,   "優待リマインド開始日数", "権利付最終日まで何日前から通知に出すか"),
    "EARNINGS_REMIND_DAYS":  ("int",  14,   "決算リマインド日数", "決算がこの日数以内なら通知（0でオフ）"),
    "NEAR_ALERT_PCT":        ("float", 2.0, "利確/損切り 接近予告(%)", "ラインのこの%以内で『もうすぐ』予告（0でオフ）"),
    "SCAN_TOP_N":            ("int",  8,    "通知する上位件数", "買い候補を上位何件まで通知するか"),
    "AI_NOTIFY_COMMENT":     ("bool", True, "通知のAIコメント", "朝夜通知にAIの一言（月¥20〜40の課金）"),
    "AI_NEWS_SUMMARY_ENABLED": ("bool", False, "ニュースAI要約ボタン", "📰に要約ボタン表示（押した時だけ¥1〜2）"),
}


# 起動時(まだ上書き前)の config 既定値を控えておく。これが“真の既定”。
_DEFAULTS = {name: getattr(config, name, fld[1]) for name, fld in FIELDS.items()}


def _coerce(typ, v):
    try:
        if typ == "int":
            return int(v)
        if typ == "float":
            return float(v)
        if typ == "bool":
            return bool(v)
    except Exception:
        return None
    return v


def load():
    """保存済みの上書き(dict)。無ければ空。"""
    try:
        return store.get_json(KEY, {}) or {}
    except Exception:
        return {}


def save(d):
    """上書きdictを保存（FIELDSにある項目だけ・型を整える）。"""
    clean = {}
    for name, (typ, *_rest) in FIELDS.items():
        if name in d and d[name] is not None:
            cv = _coerce(typ, d[name])
            if cv is not None:
                clean[name] = cv
    store.set_json(KEY, clean)
    return clean


def effective():
    """真の既定(_DEFAULTS)に保存値を重ねた、現在有効な設定dict。"""
    saved = load()
    out = {}
    for name in FIELDS:
        out[name] = saved.get(name, _DEFAULTS[name])
    return out


def apply_to_config():
    """有効値を config へ反映。保存が無い項目は“真の既定”へ戻す（ライブ更新でリセットも効く）。失敗は無視。"""
    try:
        saved = load()
    except Exception:
        return
    for name, (typ, *_rest) in FIELDS.items():
        v = saved.get(name, _DEFAULTS[name])
        cv = _coerce(typ, v)
        setattr(config, name, cv if cv is not None else _DEFAULTS[name])
