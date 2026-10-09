"""myposts.py - 過去の投稿の閲覧 (使用機能: 投稿閲覧機能 FL4, 5, 6)

ログインユーザー自身の投稿 (イベント・ノウハウ) と、それに付いたコメントをDBから取得する。
投稿が1件もなければ「投稿なし」のメッセージを設定する。
"""
import logging

from flask import Blueprint, redirect, render_template
from flask_login import current_user, login_required

from y_coco.db import POST_TYPE_EVENT, POST_TYPE_KNOWHOW, connection_scope

logger = logging.getLogger(__name__)

MSG_NO_POSTS = "投稿なし"
MSG_FETCH_FAILED = "投稿の取得に失敗しました"
PREVIEW_LENGTH = 50  # 本文の表示文字数 (超えたら末尾に ... を付ける)

LOGIN_URL = "/login"

myposts_bp = Blueprint("myposts", __name__, template_folder="../templates")

_SQL_MY_EVENTS = """
    SELECT e.id AS post_id, %s AS post_type, e.title AS title,
           e.description AS body, e.created_at AS created_at, u.username AS username
    FROM event_post e JOIN users u ON u.id = e.user_id
    WHERE e.user_id = %s
"""
_SQL_MY_KNOWHOWS = """
    SELECT k.id AS post_id, %s AS post_type, k.title AS title,
           k.detail AS body, k.created_at AS created_at, u.username AS username
    FROM knowhow k JOIN users u ON u.id = k.user_id
    WHERE k.user_id = %s
"""
# 自分の投稿に付いたコメント
_SQL_COMMENTS_ON_MY_POSTS = """
    SELECT c.id AS comment_id, c.user_id AS user_id, u.username AS username,
           c.post_type AS post_type, c.post_id AS post_id,
           c.comment AS comment, c.created_at AS created_at
    FROM `comment` c JOIN users u ON u.id = c.user_id
    WHERE (c.post_type = %s AND c.post_id IN (SELECT id FROM event_post WHERE user_id = %s))
       OR (c.post_type = %s AND c.post_id IN (SELECT id FROM knowhow WHERE user_id = %s))
    ORDER BY c.created_at ASC, c.id ASC
"""


def make_preview(text, limit=PREVIEW_LENGTH):
    """本文の一部を返す。limit文字を超えたら後ろに ... を付ける。"""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "..."


def get_my_posts(user_id, db_conn=None):
    """自分の投稿とコメントを取得する。

    戻り値: (post_list, comment_list, display_msg)
        post_list   : 新しい投稿順の配列。各要素は dict
                      (post_id, post_type, title, body, body_preview, created_at, username)
        comment_list: 自分の投稿に付いたコメントの配列
        display_msg : 投稿が無いとき「投稿なし」、取得失敗時はエラー文、それ以外は None
    """
    post_list = []      # 投稿を格納する空配列を初期化
    comment_list = []   # コメントを格納する空配列を初期化

    try:
        with connection_scope(db_conn) as conn:
            with conn.cursor() as cur:
                cur.execute(_SQL_MY_EVENTS, (POST_TYPE_EVENT, user_id))
                post_list.extend(cur.fetchall())
                cur.execute(_SQL_MY_KNOWHOWS, (POST_TYPE_KNOWHOW, user_id))
                post_list.extend(cur.fetchall())
                cur.execute(_SQL_COMMENTS_ON_MY_POSTS,
                            (POST_TYPE_EVENT, user_id, POST_TYPE_KNOWHOW, user_id))
                comment_list.extend(cur.fetchall())
    except Exception:
        logger.exception("自分の投稿の取得中に例外が発生しました")
        return [], [], MSG_FETCH_FAILED

    # イベントとノウハウを合わせて新しい順に並べる
    post_list.sort(key=lambda p: (p["created_at"], p["post_id"]), reverse=True)
    for post in post_list:
        post["body_preview"] = make_preview(post.get("body"))

    # 投稿配列が空なら「投稿なし」を設定
    display_msg = None if post_list else MSG_NO_POSTS
    return post_list, comment_list, display_msg


# ---------------------------------------------------------------------------
# 画面 (過去投稿閲覧画面 GD7)
# ---------------------------------------------------------------------------
@myposts_bp.route("/account/myposts")
def myposts():
    user_id = current_user.is_authenticated
    if user_id is None:
        return redirect(LOGIN_URL)

    post_list, comment_list, display_msg = get_my_posts(user_id)
    return render_template("account/myposts.html",
                           post_list=post_list,
                           comment_list=comment_list,
                           display_msg=display_msg)