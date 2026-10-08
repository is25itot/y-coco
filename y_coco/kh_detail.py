"""kh_detail.py - ノウハウ詳細閲覧機能 (FL29, FL30)

選択したノウハウと、そのコメントを取得して表示する。
投稿者本人には投稿者用、管理者には管理者用のテンプレートを使う。
"""
from flask import Blueprint, redirect, render_template, session, url_for

import db

kh_detail_bp = Blueprint("kh_detail", __name__, template_folder="user/templates")

USER_TEMPLATE = "knowhow/kh_detail.html"
ORGANIZER_TEMPLATE = "knowhow/kh_detail_organizer.html"
ADMIN_TEMPLATE = "knowhow/admin_kh_detail.html"

POST_TYPE_KNOWHOW = 2  # comment.post_type: 2=ノウハウ (1=イベント)

ERROR_KH_NOT_FOUND = 11
MSG_NOT_FOUND = "ノウハウが存在しません。"
MSG_NO_COMMENT = "コメントはありません。"

KH_SQL = """
SELECT k.id, k.user_id, k.title, k.detail, k.created_at,
       u.username, u.imagepath AS usericon
FROM knowhow k
JOIN users u ON u.id = k.user_id
WHERE k.id = %s
"""

COMMENT_SQL = """
SELECT c.id, c.user_id, c.comment, c.created_at,
       u.username, u.imagepath AS usericon
FROM comment c
JOIN users u ON u.id = c.user_id
WHERE c.post_type = %s AND c.post_id = %s
ORDER BY c.id ASC
"""


def load_kh_detail(knowhow_id):
    """(knowhow, comment_list) を返す。存在しなければ (None, [])。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(KH_SQL, (knowhow_id,))
            knowhow = cur.fetchone()
            if knowhow is None:
                return None, []
            cur.execute(COMMENT_SQL, (POST_TYPE_KNOWHOW, knowhow_id))
            comment_list = list(cur.fetchall())
    finally:
        conn.close()
    return knowhow, comment_list


def select_template(user, knowhow):
    """管理者 → 管理者用 / 投稿者本人 → 投稿者用 / それ以外 → 通常。"""
    if user.get("admin_flg"):
        return ADMIN_TEMPLATE
    if knowhow is not None and knowhow["user_id"] == user["id"]:
        return ORGANIZER_TEMPLATE
    return USER_TEMPLATE


@kh_detail_bp.route("/knowhow/<int:knowhow_id>")
def show(knowhow_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login.login"))

    knowhow, comment_list = load_kh_detail(knowhow_id)
    template = select_template(user, knowhow)

    if knowhow is None:
        return render_template(
            template, knowhow=None, comment_list=[], comment_message=None,
            message=MSG_NOT_FOUND, code=ERROR_KH_NOT_FOUND, userid=user["id"],
        ), 404

    return render_template(
        template,
        knowhow=knowhow,
        comment_list=comment_list,
        comment_message=None if comment_list else MSG_NO_COMMENT,
        message=None,
        code=0,
        userid=user["id"],
    )