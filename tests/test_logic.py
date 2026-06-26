# tests/test_logic.py 【純粋ロジックの回帰テスト(ネット接続なし)】
# 実行: .\.venv\Scripts\python.exe tests\test_logic.py
#   緑(OK)が並べば合格。1つでも失敗すると最後に件数を出して異常終了します。
# pytest不要(標準ライブラリのassertのみ)。ネットや株価取得が要る関数は対象外。

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)   # notify_job.py はルート直下にある

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  OK  {name}")
    else:
        _failed += 1
        print(f"  NG  {name}")


# ---- risk.suggest_shares ----
def test_suggest_shares():
    import risk
    # 1000円・損切5%・上限5000 → 1株損失50・100株(loss5000=上限ちょうど)
    s = risk.suggest_shares(1000, 5, 5000, True)
    check("suggest: 1000/5%/5000 → 100株", s["unit_shares"] == 100)
    check("suggest: 必要資金10万", s["need"] == 100000)
    check("suggest: 最大損失5000", round(s["max_loss"]) == 5000)
    # 単元に届かない例
    s2 = risk.suggest_shares(1300, 5, 5000, True)
    check("suggest: 1300/5%/5000 → 単元未達0株", s2["unit_shares"] == 0)
    # 米国株(単元1)
    s3 = risk.suggest_shares(100, 5, 1000, False)
    check("suggest: 米国株 単元1で200株", s3["unit_shares"] == 200)
    # 損切り0や価格0で安全に0
    check("suggest: stop0で0株", risk.suggest_shares(1000, 0, 5000, True)["unit_shares"] == 0)


# ---- analog.historical_analog ----
def test_analog():
    import analog
    import pandas as pd
    # 30日未満は None
    check("analog: 短いデータはNone", analog.historical_analog(pd.DataFrame({"Close": [1, 2, 3]})) is None)
    # 合成: 単調上昇 + 指標を自前付与。似た局面が十分あれば dict、samples>=10
    n = 300
    closes = [100 + i * 0.5 for i in range(n)]
    df = pd.DataFrame({"Close": closes})
    df["SMA25"] = df["Close"].rolling(25).mean()
    df["SMA75"] = df["Close"].rolling(75).mean()
    # RSIは一定にして「似た局面」を量産(全行同じRSI=50相当)
    df["RSI"] = 55.0
    res = analog.historical_analog(df, horizon=5)
    check("analog: 上昇相場でdict返る", isinstance(res, dict))
    if isinstance(res, dict):
        check("analog: samples>=10", res["samples"] >= 10)
        check("analog: 上昇相場は勝率100%", round(res["win_rate"]) == 100)
        check("analog: avgが正", res["avg"] > 0)


# ---- paper 集計 ----
def test_paper_stats():
    import paper
    state = {"history": [
        {"time": "2026-05-10 10:00", "action": "売", "code": "8267.T", "name": "イオン", "realized": 5000},
        {"time": "2026-05-20 10:00", "action": "売", "code": "8267.T", "name": "イオン", "realized": -2000},
        {"time": "2026-06-02 10:00", "action": "売", "code": "7203.T", "name": "トヨタ", "realized": 8000},
        {"time": "2026-06-02 10:00", "action": "買", "code": "7203.T", "name": "トヨタ"},  # realizedなし=無視
    ]}
    m = paper.monthly_realized(state)
    check("paper: 月数2", len(m) == 2)
    check("paper: 5月実現+3000", m[0]["realized"] == 3000 and m[0]["month"] == "2026-05")
    check("paper: 6月実現+8000", m[1]["realized"] == 8000)
    by = paper.by_symbol(state)
    check("paper: 銘柄2", len(by) == 2)
    check("paper: トヨタ先頭(損益大)", by[0]["code"] == "7203.T")
    aeon = next(b for b in by if b["code"] == "8267.T")
    check("paper: イオン勝率50%", round(aeon["win_rate"]) == 50)
    st = paper.stats(state)
    check("paper: 取引3回", st["trades"] == 3)
    check("paper: 合計実現+11000", st["total_realized"] == 11000)


# ---- notify_job._level_status (到達/接近判定) ----
def test_level_status():
    import notify_job as nj
    # target: 利確。現在>=level→reached、near%以内→near
    check("level: target reached", nj._level_status(105, 100, "target", 2) == "reached")
    check("level: target near(1%以内)", nj._level_status(99, 100, "target", 2) == "near")
    check("level: target 遠い→None", nj._level_status(90, 100, "target", 2) is None)
    # stop: 損切り。現在<=level→reached
    check("level: stop reached", nj._level_status(95, 100, "stop", 2) == "reached")
    check("level: stop near", nj._level_status(101, 100, "stop", 2) == "near")
    check("level: stop 遠い→None", nj._level_status(110, 100, "stop", 2) is None)
    check("level: level無し→None", nj._level_status(100, 0, "target", 2) is None)


# ---- tdnet 純粋部分 ----
def test_tdnet():
    import tdnet
    check("tdnet: コード整形 8267.T→8267", tdnet._code_for_api("8267.T") == "8267")
    check("tdnet: 重要判定(決算)", tdnet.is_important("2026年3月期 決算短信") is True)
    check("tdnet: 重要判定(優待変更)", tdnet.is_important("株主優待制度の変更について") is True)
    check("tdnet: 非重要(通常)", tdnet.is_important("月次の営業データについて") is False)


# ---- appconfig ----
def test_appconfig():
    import appconfig
    check("appconfig: int変換", appconfig._coerce("int", "40") == 40)
    check("appconfig: bool変換", appconfig._coerce("bool", 1) is True)
    check("appconfig: float変換", appconfig._coerce("float", "2.5") == 2.5)
    eff = appconfig.effective()
    check("appconfig: effectiveに全FIELD", set(eff.keys()) == set(appconfig.FIELDS.keys()))


# ---- watch 営業日ロジック(純粋・ネット不要) ----
def test_watch_dates():
    import datetime as dt
    import watch
    # 2026-08は最終営業日が月曜8/31。権利付最終日はその2営業日前
    rec = watch.last_business_day(2026, 8)
    check("watch: 2026/8末営業日=8/31(月)", rec == dt.date(2026, 8, 31))
    kenri = watch.minus_business_days(rec, 2)
    check("watch: 権利付最終日=8/27(木)", kenri == dt.date(2026, 8, 27))


def main():
    print("=== 純粋ロジック 回帰テスト ===")
    for fn in [test_suggest_shares, test_analog, test_paper_stats, test_level_status,
               test_tdnet, test_appconfig, test_watch_dates]:
        print(f"[{fn.__name__}]")
        try:
            fn()
        except Exception as e:
            global _failed
            _failed += 1
            print(f"  NG  {fn.__name__} で例外: {e}")
    print(f"\n結果: {_passed} OK / {_failed} NG")
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
