"""notification.py - 通知の登録 (使用機能: 通知機能 FL8, 9, 10)

自分の投稿にコメントが付いたときに呼び出す。
投稿者自身のコメントなら何もせず、他人のコメントなら notification テーブルへ登録する。

comment.py / kh-comment.py など、コメントを保存する処理の後に
    notify_comment(投稿者のID, コメントしたユーザーのID, 投稿ID, POST_TYPE_EVENT など)
の形で呼び出す。

戻り値の code:
    0 ... 通知を登録した
    1 ... 登録失敗 (ロールバック済み)
    2 ... 自分自身のコメントのため登録をスキップした
"""
import logging

from y_coco.db import run_in_transaction

logger = logging.getLogger(__name__)

NOTIFY_OK = 0
NOTIFY_ERROR = 1
NOTIFY_SKIPPED = 2

MSG_NOTIFY_FAILED = "通知の登録に失敗しました"


def notify_comment(post_owner_id, comment_user_id, post_id, post_type, db_conn=None):
    """コメントされたことを投稿者へ通知する。

    post_owner_id   : 投稿者のユーザーID (通知の受信者 receiver_id)
    comment_user_id : コメントしたユーザーのID (通知の送信者 senduser_id)
    post_id         : コメントされた投稿のID
    post_type       : 投稿の種類 (db.POST_TYPE_EVENT / db.POST_TYPE_KNOWHOW)
                      ※ 設計書の入力には無いが、通知テーブルの必須項目のため追加している
    戻り値          : (code, error_msg)  成功・スキップ時 error_msg は None
    """
    # 投稿者自身がコメントした場合は通知しない
    is_self_comment = str(post_owner_id) == str(comment_user_id)
    if is_self_comment:
        return NOTIFY_SKIPPED, None

    def work(conn):
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notification "
                "(senduser_id, receiver_id, post_type, post_id, created_at, read_flg) "
                "VALUES (%s, %s, %s, %s, NOW(), 0)",
                (comment_user_id, post_owner_id, post_type, post_id),
            )
            insert_result = cur.rowcount == 1
        return insert_result, None

    try:
        insert_result, _ = run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("通知の登録中に例外が発生しました")
        return NOTIFY_ERROR, MSG_NOTIFY_FAILED

    if insert_result:
        return NOTIFY_OK, None
    return NOTIFY_ERROR, MSG_NOTIFY_FAILED