# tdnet.py 【適時開示(TDnet)の取得】
# 企業が証券取引所に出す“公式な開示情報”(決算/業績修正/配当/優待変更/自己株式 など)を取得します。
# Googleニュースより精度が高く、株価に直接効く“本物の材料”が分かります。
#
# データ源: yanoshin の無料TDnet WebAPI(認証不要・公開データ)。
#   https://webapi.yanoshin.jp/webapi/tdnet/list/<code>.json?limit=N
# ※非公式ミラー。落ちている場合もあるので、失敗時は空リストを返す(画面は壊さない)。

import warnings
warnings.simplefilter("ignore")

import _net  # noqa: F401  日本語フォルダ対策(SSL)
import requests

# 注目度が高い開示の見分け用キーワード(タイトルに含むと重要マーク)
IMPORTANT = ["決算", "業績予想", "上方修正", "下方修正", "配当", "株主優待", "優待",
             "自己株式", "自社株", "増資", "新株", "公開買付", "TOB", "分割", "業務提携",
             "M&A", "経営統合", "特別損失", "減損"]


def _code_for_api(code):
    """'8267.T' → '8267'。数字以外を落とす。"""
    return "".join(c for c in str(code) if c.isdigit()) or str(code)


def is_important(title):
    return any(w in title for w in IMPORTANT)


def fetch_disclosures(code, limit=8):
    """銘柄の適時開示を新しい順で返す。
    戻り値: [{date, title, url, company, important(bool)}]。失敗時は []。"""
    c = _code_for_api(code)
    url = f"https://webapi.yanoshin.jp/webapi/tdnet/list/{c}.json?limit={int(limit)}"
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    items = data.get("items", []) if isinstance(data, dict) else (data or [])
    out = []
    for it in items:
        t = it.get("Tdnet", it) if isinstance(it, dict) else {}
        title = t.get("title", "")
        if not title:
            continue
        pub = t.get("pubdate", "") or ""
        date = pub[:16]   # 'YYYY-MM-DD HH:MM'
        out.append({
            "id": str(t.get("id", "")) or f"{t.get('company_code','')}_{pub}_{title[:20]}",
            "date": date,
            "title": title,
            "url": t.get("document_url", ""),
            "company": t.get("company_name", ""),
            "important": is_important(title),
        })
        if len(out) >= limit:
            break
    return out


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "8267"
    for d in fetch_disclosures(code):
        mark = "★" if d["important"] else "・"
        print(f"{mark} {d['date']}  {d['title']}")
