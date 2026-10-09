"""kh_search.py - ノウハウ検索機能 (FL32, FL33, FL34)

入力文を形態素解析 (Janome) で単語に分割し、題名・本文のOR検索を行う。
検索結果が無い場合は error_code=1 とし、エラーメッセージを表示して入力欄を空にする。
Janome が未インストールの場合は空白区切りで代用する。
"""
from functools import lru_cache

from flask import (Blueprint, flash, redirect, render_template, request, url_for)
from flask_login import current_user, login_required

from y_coco import db

kh_search_bp = Blueprint("kh_search", __name__, template_folder="user/templates")

USER_TEMPLATE = "knowhow/kh_search.html"
ADMIN_TEMPLATE = "knowhow/admin_kh_search.html"

MAX_QUERY_LENGTH = 100
SUMMARY_LIMIT = 50

ERROR_NO_RESULT = 1
MSG_NO_RESULT = "該当するものがありませんでした。"

# 検索語として意味を持たない品詞 (助詞・助動詞・記号)
_SKIP_POS = {"助詞", "助動詞", "記号"}


@lru_cache(maxsize=1)
def _get_tokenizer():
    try:
        from janome.tokenizer import Tokenizer
    except ImportError:
        return None
    return Tokenizer()


def split_words(text):
    """文章を単語(重複なし・出現順)のリストに分割する。"""
    text = (text or "").strip()
    if not text:
        return []

    tokenizer = _get_tokenizer()
    if tokenizer is None:
        raw = text.replace("\u3000", " ").split()
    else:
        raw = [
            t.surface
            for t in tokenizer.tokenize(text)
            if t.part_of_speech.split(",")[0] not in _SKIP_POS
        ]

    words, seen = [], set()
    for w in raw:
        w = w.strip()
        if w and w not in seen:
            seen.add(w)
            words.append(w)

    # 助詞だけの入力などで空になった場合は入力全体を1語として扱う
    return words or [text]


def escape_like(word):
    """LIKE のワイルドカード文字をエスケープする。"""
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_knowhow(words):
    """単語のいずれかを題名・本文に含むノウハウを ID 降順で返す (OR検索)。"""
    if not words:
        return []

    conditions = " OR ".join(["(k.title LIKE %s OR k.detail LIKE %s)"] * len(words))
    params = []
    for w in words:
        pattern = f"%{escape_like(w)}%"
        params.extend([pattern, pattern])

    sql = (
        "SELECT k.id, k.user_id, k.title, k.detail, k.created_at, "
        "u.username, u.imagepath AS usericon "
        "FROM knowhow k JOIN users u ON u.id = k.user_id "
        f"WHERE {conditions} "
        "ORDER BY k.id DESC"
    )

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    results = []
    for r in rows:
        detail = r["detail"] or ""
        summary = detail if len(detail) <= SUMMARY_LIMIT else detail[:SUMMARY_LIMIT] + "..."
        results.append(dict(r, summary=summary))
    return results


@kh_search_bp.route("/knowhow/search")
def search():
    if not current_user.is_authenticated:
        return redirect(url_for("login.login"))

    template = ADMIN_TEMPLATE if current_user.admin_flg else USER_TEMPLATE
    query = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]

    if not query:
        return render_template(
            template, query="", words=[], results=[], searched=False,
            error_code=0, userid=current_user.id,
        )

    words = split_words(query)
    results = search_knowhow(words)

    if not results:
        # 結果なし: error_code=1、エラーメッセージを出して入力欄を空にする
        flash(MSG_NO_RESULT, "error")
        return render_template(
            template, query="", words=words, results=[], searched=True,
            error_code=ERROR_NO_RESULT, userid=current_user.id,
        )

    return render_template(
        template, query=query, words=words, results=results, searched=True,
        error_code=0, userid=current_user.id,
    )