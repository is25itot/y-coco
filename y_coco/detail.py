"""detail.py - イベント詳細閲覧機能 (FL20, FL21)

選択したイベントと、そのコメントを取得して表示する。
開催者本人には開催者用、管理者には管理者用のテンプレートを使う。
"""
from flask import Blueprint, redirect, render_template, session, url_for

from y_coco import db

detail_bp = Blueprint("event_detail", __name__, template_folder="user/templates")

USER_TEMPLATE = "event/detail.html"
ORGANIZER_TEMPLATE = "event/event_detail_organizer.html"
ADMIN_TEMPLATE = "event/admin_event_detail.html"

POST_TYPE_EVENT = 1  # comment.post_type: 1=イベント (2=ノウハウ)

ERROR_EVENT_NOT_FOUND = 10
MSG_NOT_FOUND = "投稿が存在しません。"
MSG_NO_COMMENT = "コメントはありません。"

EVENT_SQL = """
SELECT e.id, e.user_id, e.title, e.description, e.imagepath, e.`datetime`,
       e.fee, e.location, e.address, e.parking_info, e.contact_info,
       e.created_at, u.username, u.imagepath AS usericon
FROM event_post e
JOIN users u ON u.id = e.user_id
WHERE e.id = %s
"""

COMMENT_SQL = """
SELECT c.id, c.user_id, c.comment, c.created_at,
       u.username, u.imagepath AS usericon
FROM comment c
JOIN users u ON u.id = c.user_id
WHERE c.post_type = %s AND c.post_id = %s
ORDER BY c.id ASC
"""


def load_event_detail(event_id):
    """(event, comment_list) を返す。イベントが存在しなければ (None, [])。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(EVENT_SQL, (event_id,))
            event = cur.fetchone()
            if event is None:
                return None, []
            cur.execute(COMMENT_SQL, (POST_TYPE_EVENT, event_id))
            comment_list = list(cur.fetchall())
    finally:
        conn.close()
    return event, comment_list


def select_template(user, event):
    """管理者 → 管理者用 / 開催者本人 → 開催者用 / それ以外 → 通常。"""
    if user.get("admin_flg"):
        return ADMIN_TEMPLATE
    if event is not None and event["user_id"] == user["id"]:
        return ORGANIZER_TEMPLATE
    return USER_TEMPLATE


@detail_bp.route("/events/<int:event_id>")
def show(event_id):
    user = session.get("user")
    if not user:
        return redirect(url_for("login.login"))

    event, comment_list = load_event_detail(event_id)
    template = select_template(user, event)

    if event is None:
        return render_template(
            template, event=None, comment_list=[], comment_message=None,
            message=MSG_NOT_FOUND, code=ERROR_EVENT_NOT_FOUND, userid=user["id"],
        ), 404

    return render_template(
        template,
        event=event,
        comment_list=comment_list,
        comment_message=None if comment_list else MSG_NO_COMMENT,
        message=None,
        code=0,
        userid=user["id"],
    )