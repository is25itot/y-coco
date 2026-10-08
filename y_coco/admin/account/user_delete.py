"""user_delete.py : アカウント削除機能 (M-FL1, M-FL2)

トランザクションを使用してアカウント情報および関連データを削除する。
  成功 : コミット、code = 0
  失敗 : ロールバック、code = 7

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""

CODE_SUCCESS = 0
CODE_FAILURE = 7

# comment / notification テーブルの post_type の値(要確認: 設計書に値の定義なし)
POST_TYPE_EVENT = 1
POST_TYPE_KNOWHOW = 2

MSG_SUCCESS = "アカウントを削除しました。"
MSG_FAILURE = "アカウントの削除に失敗しました。"


def _open_connection():
    from db import get_connection
    return get_connection()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _result(code, message, is_logged_out=False):
    return {"code": code, "message": message, "is_logged_out": is_logged_out}


def _delete_related_data(cur, user_id):
    """ユーザーに関連する投稿・コメント・通知を削除する。

    外部キー制約に引っかからないよう、子 → 親の順に削除する。
    """
    # 1. ユーザーのイベント/ノウハウに付いた他人のコメント
    cur.execute(
        "DELETE FROM comment WHERE post_type = %s AND post_id IN "
        "(SELECT id FROM event_post WHERE user_id = %s)",
        (POST_TYPE_EVENT, user_id),
    )
    cur.execute(
        "DELETE FROM comment WHERE post_type = %s AND post_id IN "
        "(SELECT id FROM knowhow WHERE user_id = %s)",
        (POST_TYPE_KNOWHOW, user_id),
    )
    # 2. ユーザー自身のコメント
    cur.execute("DELETE FROM comment WHERE user_id = %s", (user_id,))
    # 3. 通知(送信/受信どちらも + ユーザーの投稿に紐づくもの)
    cur.execute(
        "DELETE FROM notification WHERE senduser_id = %s OR receiver_id = %s",
        (user_id, user_id),
    )
    cur.execute(
        "DELETE FROM notification WHERE post_type = %s AND post_id IN "
        "(SELECT id FROM event_post WHERE user_id = %s)",
        (POST_TYPE_EVENT, user_id),
    )
    cur.execute(
        "DELETE FROM notification WHERE post_type = %s AND post_id IN "
        "(SELECT id FROM knowhow WHERE user_id = %s)",
        (POST_TYPE_KNOWHOW, user_id),
    )
    # 4. 投稿本体
    cur.execute("DELETE FROM event_post WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM knowhow WHERE user_id = %s", (user_id,))


def delete_user(user_id, db_conn=None, session_obj=None):
    """アカウントと関連データを削除する。

    Args:
        user_id: 削除対象のユーザーID
        db_conn: テスト用などで接続を差し込む場合に指定
        session_obj: Flaskの session。削除されたのが
            ログイン中のユーザー本人なら、セッションを破棄してログアウトさせる

    Returns:
        {"code": 0 or 7, "message": str, "is_logged_out": bool}
    """
    target_id = _to_int(user_id)
    if target_id is None:
        return _result(CODE_FAILURE, MSG_FAILURE)

    own_connection = db_conn is None
    conn = None
    try:
        conn = db_conn if db_conn is not None else _open_connection()
        with conn.cursor() as cur:
            # 削除対象の確認(存在しない・管理者アカウントは削除しない)
            cur.execute(
                "SELECT id, admin_flg FROM users WHERE id = %s", (target_id,)
            )
            target = cur.fetchone()
            if not target or target.get("admin_flg"):
                conn.rollback()
                return _result(CODE_FAILURE, MSG_FAILURE)

            _delete_related_data(cur, target_id)
            delete_posts_result = True  # 例外が出ていなければ成功扱い

            cur.execute("DELETE FROM users WHERE id = %s", (target_id,))
            delete_user_result = cur.rowcount >= 1

        is_success = delete_posts_result and delete_user_result
        if not is_success:
            conn.rollback()
            return _result(CODE_FAILURE, MSG_FAILURE)

        conn.commit()
        is_logged_out = _force_logout(session_obj, target_id)
        return _result(CODE_SUCCESS, MSG_SUCCESS, is_logged_out)

    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return _result(CODE_FAILURE, MSG_FAILURE)
    finally:
        if own_connection and conn is not None:
            conn.close()


def _force_logout(session_obj, deleted_user_id):
    """削除されたのがログイン中の本人なら、セッションを破棄する。"""
    if session_obj is None:
        return False
    current = session_obj.get("user")
    if not current:
        return False
    if _to_int(current.get("id")) != deleted_user_id:
        return False
    session_obj.clear()
    return True
