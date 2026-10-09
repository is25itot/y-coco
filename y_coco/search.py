"""search.py - イベント検索機能 (FL23, FL24, FL25)

入力文を形態素解析 (Janome) で単語に分割し、題名・本文のOR検索を行う。
Janome が未インストールの場合は空白区切りで代用する。
"""
from functools import lru_cache

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from y_coco import db

search_bp = Blueprint("event_search", __name__, template_folder="user/templates")

USER_TEMPLATE = "event/event_search.html"
ADMIN_TEMPLATE = "event/admin_event_search.html"

MAX_QUERY_LENGTH = 100
SUMMARY_LIMIT = 50
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


def search_events(words):
    """単語のいずれかを題名・本文に含む開催前イベントを ID 降順で返す (OR検索)。"""
    if not words:
        return []

    conditions = " OR ".join(["(e.title LIKE %s OR e.description LIKE %s)"] * len(words))
    params = []
    for w in words:
        pattern = f"%{escape_like(w)}%"
        params.extend([pattern, pattern])

    sql = (
        "SELECT e.id, e.user_id, e.title, e.description, e.imagepath, "
        "e.`datetime`, u.username, u.imagepath AS usericon "
        "FROM event_post e JOIN users u ON u.id = e.user_id "
        f"WHERE e.`datetime` >= CURDATE() AND ({conditions}) "
        "ORDER BY e.id DESC"
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
        desc = r["description"] or ""
        summary = desc if len(desc) <= SUMMARY_LIMIT else desc[:SUMMARY_LIMIT] + "..."
        results.append(dict(r, summary=summary))
    return results


@search_bp.route("/events/search")
def search():
    user = current_user.is_authenticated
    if not user:
        return redirect(url_for("login.login"))

    template = ADMIN_TEMPLATE if user.get("admin_flg") else USER_TEMPLATE
    query = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]

    if not query:
        return render_template(
            template, query="", words=[], results=[], searched=False,
            has_result=False, message=None, userid=user["id"],
        )

    words = split_words(query)
    results = search_events(words)
    has_result = bool(results)
    return render_template(
        template,
        query=query,
        words=words,
        results=results,
        searched=True,
        has_result=has_result,
        message=None if has_result else MSG_NO_RESULT,
        userid=user["id"],
    )