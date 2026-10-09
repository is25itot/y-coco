"""ノウハウのコメント機能 (モジュール設計書: kh-comment.py / 機能ID FL50, FL51)

トランザクションを使い、コメントデータを安全に登録し通知イベントを送信する。

処理の流れ
    1. 入力フォーム(コメント)から comment_text を読み取る
    2. CommentForm でバリデーションチェック (is_valid)
         is_valid = FALSE -> エラーメッセージを出力し処理を中止
    3. user_id を受け取る (改ざん防止のため画面ではなく current_user.is_authenticated から取得)
    4. DB接続を確立しトランザクション開始
    5. INSERT 文で comment テーブルに新規レコードを挿入 (insert_result)
    6. is_success = TRUE  -> コミットし通知イベントを送信, code = 0
       is_success = FALSE -> ロールバックして処理を中止,   code = 6

code の意味
    0: 登録成功
    6: ノウハウコメントの登録失敗 (ロールバック済み)

通知イベント
    blinker のシグナル "comment-posted" を送信する (event/comment.py と共通)。
    post_type でイベント(1)とノウハウ(2)を区別できる。
"""
import logging

from blinker import signal
from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template_string,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.routing import BuildError

from y_coco.db import get_connection
from y_coco.validation import CommentForm

logger = logging.getLogger(__name__)

knowhow_comment_bp = Blueprint("knowhow_comment", __name__, url_prefix="/knowhow")

# イベント・ノウハウ共通のシグナル (event/comment.py と同じ名前)
comment_posted = signal("comment-posted")

# --- 定数 -------------------------------------------------------------
CODE_SUCCESS = 0
CODE_COMMENT_FAILED = 6

POST_TYPE_KNOWHOW = 2  # comment.post_type / notification.post_type の値 (ノウハウ)

LOGIN_ENDPOINT = "login"  # login.py 側のエンドポイント名に合わせる
DETAIL_ENDPOINT = "kh_detail"  # kh_detail.py 側のエンドポイント名に合わせる

FIND_POST_SQL = "SELECT user_id FROM knowhow WHERE id = %s"
INSERT_SQL = (
    "INSERT INTO `comment` (user_id, post_type, post_id, `comment`, created_at) "
    "VALUES (%s, %s, %s, %s, NOW())"
)

ERROR_PAGE = """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>エラー</title></head>
<body>
  <main>
    {% for message in messages %}<p class="error">{{ message }}</p>{% endfor %}
    <a class="back-button" href="{{ back_url }}">戻る</a>
  </main>
</body>
</html>
"""


# --- 補助関数 ---------------------------------------------------------
def _url(endpoint, fallback, **values):
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return fallback


def _detail_url(post_id):
    return _url(DETAIL_ENDPOINT, f"/knowhow/{post_id}", post_id=post_id)


def _owner_id(row):
    return row["user_id"] if isinstance(row, dict) else row[0]


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:
        logger.exception("ロールバックに失敗しました")


def _form_error_messages(form):
    messages = []
    for field_errors in getattr(form, "errors", {}).values():
        if isinstance(field_errors, (list, tuple)):
            messages.extend(str(e) for e in field_errors)
        else:
            messages.append(str(field_errors))
    return messages


def _error_page(messages, post_id, status):
    """エラーメッセージと元の画面へ戻るボタンを表示する。"""
    html = render_template_string(
        ERROR_PAGE, messages=messages, back_url=_detail_url(post_id)
    )
    return html, status


def _send_notification_event(sender_id, receiver_id, post_id, comment_id):
    """コミット後に通知イベントを送る。

    コメントはすでに保存済みなので、受信側で例外が起きてもコメント投稿は失敗にしない。
    """
    try:
        comment_posted.send(
            current_app._get_current_object(),
            sender_id=sender_id,
            receiver_id=receiver_id,
            post_type=POST_TYPE_KNOWHOW,
            post_id=post_id,
            comment_id=comment_id,
        )
    except Exception:
        logger.exception("通知イベントの送信に失敗しました")


# --- 登録処理 ---------------------------------------------------------
def save_comment(user_id, post_id, comment_text):
    """トランザクションでコメントを登録し、成功時に通知イベントを送信する。

    戻り値: (code, comment_id)
        成功時 (0, 登録したコメントのid) / 失敗時 (6, None)
    """
    receiver_id = None
    comment_id = None
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            # コメント先のノウハウが存在するか確認し、通知の宛先(投稿者)を取得する
            cur.execute(FIND_POST_SQL, (post_id,))
            post_row = cur.fetchone()
            if post_row is None:
                insert_result = False
            else:
                receiver_id = _owner_id(post_row)
                cur.execute(
                    INSERT_SQL,
                    (user_id, POST_TYPE_KNOWHOW, post_id, comment_text),
                )
                insert_result = cur.rowcount == 1
                comment_id = cur.lastrowid

        is_success = bool(insert_result)
        if not is_success:
            _safe_rollback(conn)
            return CODE_COMMENT_FAILED, None

        conn.commit()
    except Exception:
        logger.exception("コメントの登録に失敗しました")
        _safe_rollback(conn)
        return CODE_COMMENT_FAILED, None
    finally:
        conn.close()

    _send_notification_event(user_id, receiver_id, post_id, comment_id)
    return CODE_SUCCESS, comment_id


# --- ルート -----------------------------------------------------------
@knowhow_comment_bp.route("/<int:post_id>/comment", methods=["POST"])
def post_comment(post_id):
    user_id = current_user.is_authenticated
    if user_id is None:
        return redirect(_url(LOGIN_ENDPOINT, "/login"))

    # バリデーションチェック (is_valid)
    form = CommentForm()
    is_valid = form.validate_on_submit()
    if not is_valid:
        return _error_page(_form_error_messages(form), post_id, 400)

    comment_text = request.form.get("comment", "")
    code, _comment_id = save_comment(user_id, post_id, comment_text)
    if code != CODE_SUCCESS:
        return _error_page(
            ["コメントの保存に失敗しました。もう一度お試しください。"], post_id, 500
        )

    return redirect(_detail_url(post_id))