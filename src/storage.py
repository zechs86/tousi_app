# storage.py
# 【データ保存の部品】
# 集めた株価や分析結果を data\market.db という1つのファイル(SQLite)に貯めます。
# SQLite = Pythonに最初から入っている小さなデータベース。インストール不要。
#
# テーブル(表)は2つ:
#   prices    … 日々の株価(始値/高値/安値/終値/出来高)。全履歴を貯める。
#   snapshots … 毎日の分析結果(RSI/点数/判定/PER/割安度など)を1日1行で記録。
#
# 「INSERT OR REPLACE」を使うので、同じ銘柄・同じ日付を二重に入れても上書きされ、
# 何度実行してもデータが重複しません(毎日安心して回せる)。

import os
import sqlite3

# このファイルから見た data\market.db の場所を組み立てる
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "..", "data", "market.db")


def connect():
    """DBに接続する。フォルダが無ければ作る。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    """テーブルが無ければ作る(初回だけ実際に作成される)。"""
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            code   TEXT,
            date   TEXT,
            open   REAL,
            high   REAL,
            low    REAL,
            close  REAL,
            volume INTEGER,
            PRIMARY KEY (code, date)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            code        TEXT,
            date        TEXT,
            name        TEXT,
            close       REAL,
            rsi         REAL,
            macd_hist   REAL,
            score       INTEGER,
            verdict     TEXT,
            per         REAL,
            pbr         REAL,
            div_yield   REAL,
            pos_in_range REAL,
            PRIMARY KEY (code, date)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            code      TEXT,
            published TEXT,
            title     TEXT,
            source    TEXT,
            link      TEXT,
            sentiment INTEGER,
            PRIMARY KEY (code, link)
        )
    """)
    conn.commit()
    conn.close()


def save_news(rows):
    """ニュース(リスト)をnewsテーブルに保存。link重複は上書き。返り値: 新規含む件数。
    rows: (code, published, title, source, link, sentiment) のタプルのリスト。"""
    if not rows:
        return 0
    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO news (code,published,title,source,link,sentiment) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


def save_prices(code, df):
    """株価データ(DataFrame)をpricesテーブルに保存する。重複は上書き。
    返り値: 保存した行数。"""
    rows = []
    for date, r in df.iterrows():
        rows.append((
            code,
            date.strftime("%Y-%m-%d"),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            int(r["Volume"]) if r["Volume"] == r["Volume"] else 0,  # NaN対策
        ))
    conn = connect()
    conn.executemany(
        "INSERT OR REPLACE INTO prices (code,date,open,high,low,close,volume) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


def save_snapshot(snap):
    """1銘柄ぶんの分析結果(dict)をsnapshotsテーブルに保存する。重複は上書き。"""
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO snapshots "
        "(code,date,name,close,rsi,macd_hist,score,verdict,per,pbr,div_yield,pos_in_range) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (snap["code"], snap["date"], snap["name"], snap["close"], snap["rsi"],
         snap["macd_hist"], snap["score"], snap["verdict"], snap["per"],
         snap["pbr"], snap["div_yield"], snap["pos_in_range"]))
    conn.commit()
    conn.close()


def db_summary():
    """今DBに何件たまっているかを返す(確認用)。"""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT code), MIN(date), MAX(date) FROM prices")
    p = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM snapshots")
    s = cur.fetchone()
    conn.close()
    return {"price_rows": p[0], "price_codes": p[1],
            "price_from": p[2], "price_to": p[3], "snapshot_rows": s[0]}
