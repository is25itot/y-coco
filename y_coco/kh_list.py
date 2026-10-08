"""kh_list.py - ノウハウ一覧閲覧機能 (FL27, FL28)

ノウハウを ID の降順で取得し、一覧表示する。
本文は 50 文字を超えたら末尾に「...」を付ける。管理者には管理者用テンプレートを使う。
"""
from flask import Blueprint, redirect, render_template, session, url_for

import db

kh_list_bp = Blueprint("kh_list", __name__, template_folder="user/templates")

USER_TEMPLATE = "knowhow/kh_list.html"
ADMIN_TEMPLATE = "knowhow/admin_kh_list.html"

SUMMARY_LIMIT = 50
MSG_EMPTY = "ノウハウはまだ投稿されていません。"

KH_LIST_SQL = """
SELECT k.id, k.user_id, k.title, k.detail, k.created_at,
       u.username, u.imagepath AS usericon
FROM knowhow k
JOIN users u ON u.id = k.user_id
ORDER BY k.id DESC
"""


def truncate_text(text, limit=SUMMARY_LIMIT):
    """limit 文字を超える場合は後ろに「...」を付ける。"""
    if text is None:
        return ""
    return text if len(text) <= limit else text[:limit] + "..."


def fetch_kh_list():
    """ノウハウを ID 降順で返す。各行に summary (省略済み本文) を加える。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(KH_LIST_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()
    rows = sorted(rows, key=lambda r: r["id"], reverse=True)
    return [dict(r, summary=truncate_text(r["detail"])) for r in rows]


@kh_list_bp.route("/knowhow")
def index():
    user = session.get("user")
    if not user:
        return redirect(url_for("login.login"))

    knowhows = fetch_kh_list()
    template = ADMIN_TEMPLATE if user.get("admin_flg") else USER_TEMPLATE
    return render_template(
        template,
        knowhows=knowhows,
        result=bool(knowhows),
        message=None if knowhows else MSG_EMPTY,
        userid=user["id"],
    )