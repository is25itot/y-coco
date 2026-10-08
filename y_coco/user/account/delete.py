"""delete.py - 投稿削除 (使用機能: 投稿削除機能 FL7)

自分の投稿 (イベント・ノウハウ・コメント) をトランザクションで削除する。
本人以外の削除を防ぐため、DELETE文の条件に user_id を含める。

戻り値の code:
    0 ... 削除成功
    3 ... 削除失敗 (対象なし・本人の投稿でない・DBエラー・不正な引数)
"""
import logging

from flask import Blueprint, flash, redirect, request, session

from y_coco.db import POST_TYPE_EVENT, POST_TYPE_KNOWHOW, run_in_transaction

logger = logging.getLogger(__name__)

CODE_SUCCESS = 0
CODE_ERROR = 3

MSG_DELETE_FAILED = "削除に失敗しました"

# 削除対象の種類 (画面から送られる値)
TARGET_EVENT = "event"
TARGET_KNOWHOW = "knowhow"
TARGET_COMMENT = "comment"

# 対象 -> テーブル名 (SQLに埋め込むのでここに載っているものだけ許可する)
_TABLES = {
    TARGET_EVENT: "event_post",
    TARGET_KNOWHOW: "knowhow",
    TARGET_COMMENT: "`comment`",
}
# イベント/ノウハウを消すときに、ぶら下がるコメント・通知も一緒に消す
_CASCADE_POST_TYPE = {
    TARGET_EVENT: POST_TYPE_EVENT,
    TARGET_KNOWHOW: POST_TYPE_KNOWHOW,
}

MYPOSTS_URL = "/account/myposts"  # 削除後の戻り先 (URLに合わせて変更)

delete_bp = Blueprint("delete", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# ロジック (単体テスト対象)
# ---------------------------------------------------------------------------
def delete_post(post_id, user_id, target, db_conn=None):
    """自分の投稿を1件削除する。

    post_id : 削除対象のID
    user_id : 操作ユーザーのID (投稿者本人かどうかの判定に使う)
    target  : TARGET_EVENT / TARGET_KNOWHOW / TARGET_COMMENT
    戻り値  : (code, error_msg)  成功時 error_msg は None
    """
    table = _TABLES.get(target)
    if table is None:
        return CODE_ERROR, MSG_DELETE_FAILED

    def work(conn):
        with conn.cursor() as cur:
            # DELETE文 (user_id も条件に含めて本人以外の削除を防ぐ)
            cur.execute(
                f"DELETE FROM {table} WHERE id = %s AND user_id = %s",
                (post_id, user_id),
            )
            # 影響を受けたレコードが1件以上なら正しく削除できたと判定
            is_success = cur.rowcount >= 1

            if is_success and target in _CASCADE_POST_TYPE:
                post_type = _CASCADE_POST_TYPE[target]
                cur.execute(
                    "DELETE FROM `comment` WHERE post_type = %s AND post_id = %s",
                    (post_type, post_id),
                )
                cur.execute(
                    "DELETE FROM notification WHERE post_type = %s AND post_id = %s",
                    (post_type, post_id),
                )
        return is_success, None

    try:
        is_success, _ = run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("投稿削除中に例外が発生しました")
        return CODE_ERROR, MSG_DELETE_FAILED

    if is_success:
        return CODE_SUCCESS, None
    return CODE_ERROR, MSG_DELETE_FAILED


# ---------------------------------------------------------------------------
# 画面 (削除ボタン押下)
# ---------------------------------------------------------------------------
@delete_bp.route("/account/delete", methods=["POST"])
def delete():
    # 削除は状態を変える操作なので GET ではなく POST で受ける
    user_id = session.get("user")
    if user_id is None:
        return redirect("/login")

    target = request.form.get("target", "")
    try:
        post_id = int(request.form.get("post_id", ""))
    except ValueError:
        flash(MSG_DELETE_FAILED)
        return redirect(request.referrer or MYPOSTS_URL)

    code, error_msg = delete_post(post_id, user_id, target)
    if code == CODE_SUCCESS:
        flash("削除しました")
        return redirect(MYPOSTS_URL)

    flash(error_msg)  # エラーメッセージ + 戻るボタン
    return redirect(request.referrer or MYPOSTS_URL)