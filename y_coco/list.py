"""list.py - イベント一覧閲覧機能 (FL18, FL19)

開催前のイベントを ID の降順で取得し、一覧表示する。
本文は 50 文字を超えたら末尾に「...」を付ける。管理者には管理者用テンプレートを使う。
"""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from y_coco import db

list_bp = Blueprint("event_list", __name__, template_folder="user/templates")

USER_TEMPLATE = "event/list.html"
ADMIN_TEMPLATE = "event/admin_event_list.html"

SUMMARY_LIMIT = 50
MSG_EMPTY = "イベントはまだ投稿されていません。"

EVENT_LIST_SQL = """
SELECT e.id, e.user_id, e.title, e.description, e.imagepath,
       e.`datetime`, u.username, u.imagepath AS usericon
FROM event_post e
JOIN users u ON u.id = e.user_id
WHERE e.`datetime` >= CURDATE()
ORDER BY e.id DESC
"""


def truncate_text(text, limit=SUMMARY_LIMIT):
    """limit 文字を超える場合は後ろに「...」を付ける。"""
    if text is None:
        return ""
    return text if len(text) <= limit else text[:limit] + "..."


def fetch_event_list():
    """開催前イベントを ID 降順で返す。各行に summary (省略済み本文) を加える。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(EVENT_LIST_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()
    rows = sorted(rows, key=lambda r: r["id"], reverse=True)
    return [dict(r, summary=truncate_text(r["description"])) for r in rows]


@list_bp.route("/events")
def index():
    user = current_user.is_authenticated
    if not user:
        return redirect(url_for("login.login"))

    events = fetch_event_list()
    template = ADMIN_TEMPLATE if current_user.admin_flg else USER_TEMPLATE
    return render_template(
        template,
        events=events,
        result=bool(events),  # データなしなら False
        message=None if events else MSG_EMPTY,
        userid=current_user.id,
    )