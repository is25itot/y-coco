"""notification_check.py - 通知の確認 (使用機能: 通知確認機能 FL15, 16, 17)

自分宛ての通知を新しい順に取得して一覧表示し、確認した通知を既読にする。
"""
import logging

from flask import Blueprint, jsonify, redirect, render_template, request
from flask_login import current_user, login_required

from y_coco.db import connection_scope, run_in_transaction

logger = logging.getLogger(__name__)

CODE_SUCCESS = 0
CODE_ERROR = 1

MSG_NO_NOTIFICATIONS = "通知無し"
MSG_FETCH_FAILED = "通知の取得に失敗しました"
MSG_READ_FAILED = "既読状態の更新に失敗しました"

LOGIN_URL = "/login"

notification_check_bp = Blueprint("notification_check", __name__,
                                  template_folder="../templates")

# 自分宛て(receiver_id)の通知を新しい順に。送信者名と投稿の題名も一緒に取得する
_SQL_NOTIFICATIONS = """
    SELECT n.id AS notification_id, n.senduser_id AS senduser_id,
           u.username AS sender_name, n.post_type AS post_type, n.post_id AS post_id,
           COALESCE(e.title, k.title) AS post_title,
           n.created_at AS created_at, n.read_flg AS read_flg
    FROM notification n
    JOIN users u ON u.id = n.senduser_id
    LEFT JOIN event_post e ON n.post_type = 1 AND e.id = n.post_id
    LEFT JOIN knowhow k ON n.post_type = 2 AND k.id = n.post_id
    WHERE n.receiver_id = %s
    ORDER BY n.created_at DESC, n.id DESC
"""


def get_notifications(user_id, db_conn=None):
    """自分宛ての通知一覧を新しい順で取得する。

    戻り値: (notification_list, display_msg)
        display_msg: 通知が無いとき「通知無し」、取得失敗時はエラー文、それ以外は None
    """
    try:
        with connection_scope(db_conn) as conn:
            with conn.cursor() as cur:
                cur.execute(_SQL_NOTIFICATIONS, (user_id,))
                notification_list = list(cur.fetchall())
    except Exception:
        logger.exception("通知の取得中に例外が発生しました")
        return [], MSG_FETCH_FAILED

    display_msg = None if notification_list else MSG_NO_NOTIFICATIONS
    return notification_list, display_msg


def mark_as_read(read_notification_ids, user_id, db_conn=None):
    """確認された通知を既読 (read_flg=1) に更新する。

    read_notification_ids : 画面で確認された通知IDの一覧
    user_id               : 操作ユーザー (他人宛ての通知は更新しない)
    戻り値                : (code, error_msg)  成功時 error_msg は None
    """
    try:
        ids = sorted({int(i) for i in (read_notification_ids or [])})
    except (TypeError, ValueError):
        return CODE_ERROR, MSG_READ_FAILED

    if not ids:  # 更新対象が無ければ何もしない
        return CODE_SUCCESS, None

    placeholders = ", ".join(["%s"] * len(ids))

    def work(conn):
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE notification SET read_flg = 1 "
                f"WHERE receiver_id = %s AND id IN ({placeholders})",
                (user_id, *ids),
            )
        return True, None

    try:
        run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("既読状態の更新中に例外が発生しました")
        return CODE_ERROR, MSG_READ_FAILED
    return CODE_SUCCESS, None


def count_unread(user_id, db_conn=None):
    """未読の通知件数を返す (失敗時は 0)。"""
    try:
        with connection_scope(db_conn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM notification "
                    "WHERE receiver_id = %s AND read_flg = 0",
                    (user_id,),
                )
                return cur.fetchone()["cnt"]
    except Exception:
        logger.exception("未読件数の取得中に例外が発生しました")
        return 0


# ---------------------------------------------------------------------------
# 画面 (通知確認画面 GD8)
# ---------------------------------------------------------------------------
@notification_check_bp.route("/account/notifications")
def notifications():
    user_id = current_user.is_authenticated
    if user_id is None:
        return redirect(LOGIN_URL)

    notification_list, display_msg = get_notifications(user_id)
    return render_template("account/notifications.html",
                           notification_list=notification_list,
                           display_msg=display_msg)


@notification_check_bp.route("/account/notifications/read", methods=["POST"])
def notifications_read():
    """画面を閉じるときに JS から {"ids": [1, 2, ...]} を送って既読にする。"""
    user_id = current_user.is_authenticated
    if user_id is None:
        return jsonify(code=CODE_ERROR), 401

    data = request.get_json(silent=True, force=True) or {}
    code, _ = mark_as_read(data.get("ids", []), user_id)
    return jsonify(code=code), (200 if code == CODE_SUCCESS else 500)