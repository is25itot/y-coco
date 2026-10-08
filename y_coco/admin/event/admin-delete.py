"""admin-delete.py : イベント削除機能 (M-FL10)

管理者がユーザーのイベント投稿・コメントを削除する。
イベント投稿とコメントは別々に削除できる。

  成功 : コミット、code = 0
  失敗 : ロールバック、code = 8

※ ファイル名にハイフンが含まれるため、通常の `import` では読み込めない。
   読み込む側(admin_views.py)では importlib を使うか、ファイル名を
   admin_delete.py に変更すること。

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""

CODE_SUCCESS = 0
CODE_FAILURE = 8

# comment / notification テーブルの post_type の値(要確認: 設計書に値の定義なし)
POST_TYPE_EVENT = 1

MSG_EVENT_SUCCESS = "イベント投稿を削除しました。"
MSG_EVENT_FAILURE = "イベント投稿の削除に失敗しました。"
MSG_COMMENT_SUCCESS = "コメントを削除しました。"
MSG_COMMENT_FAILURE = "コメントの削除に失敗しました。"


def _open_connection():
    from db import get_connection
    return get_connection()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _result(code, message):
    return {"code": code, "message": message}


def delete_event(event_id, db_conn=None):
    """イベント投稿を削除する(紐づくコメント・通知も同じトランザクションで削除)。

    削除後にSELECTで存在確認し、まだ存在する場合はロールバックして code = 8。
    削除対象が最初から無かった場合(0件削除)も失敗(code = 8)として扱う。
    """
    target_id = _to_int(event_id)
    if target_id is None:
        return _result(CODE_FAILURE, MSG_EVENT_FAILURE)

    own_connection = db_conn is None
    conn = None
    try:
        conn = db_conn if db_conn is not None else _open_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM comment WHERE post_type = %s AND post_id = %s",
                (POST_TYPE_EVENT, target_id),
            )
            cur.execute(
                "DELETE FROM notification WHERE post_type = %s AND post_id = %s",
                (POST_TYPE_EVENT, target_id),
            )
            cur.execute("DELETE FROM event_post WHERE id = %s", (target_id,))
            deleted_count = cur.rowcount

            # 該当のイベント投稿がまだ存在しないか確認する
            cur.execute("SELECT id FROM event_post WHERE id = %s", (target_id,))
            still_exists = cur.fetchone() is not None

        if still_exists or deleted_count < 1:
            conn.rollback()
            return _result(CODE_FAILURE, MSG_EVENT_FAILURE)

        conn.commit()
        return _result(CODE_SUCCESS, MSG_EVENT_SUCCESS)

    except Exception:
        _safe_rollback(conn)
        return _result(CODE_FAILURE, MSG_EVENT_FAILURE)
    finally:
        if own_connection and conn is not None:
            conn.close()


def delete_event_comment(comment_id, db_conn=None):
    """イベントに付いたコメントを1件削除する(ノウハウのコメントは対象外)。"""
    target_id = _to_int(comment_id)
    if target_id is None:
        return _result(CODE_FAILURE, MSG_COMMENT_FAILURE)

    own_connection = db_conn is None
    conn = None
    try:
        conn = db_conn if db_conn is not None else _open_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM comment WHERE id = %s AND post_type = %s",
                (target_id, POST_TYPE_EVENT),
            )
            deleted_count = cur.rowcount

            cur.execute(
                "SELECT id FROM comment WHERE id = %s AND post_type = %s",
                (target_id, POST_TYPE_EVENT),
            )
            still_exists = cur.fetchone() is not None

        if still_exists or deleted_count < 1:
            conn.rollback()
            return _result(CODE_FAILURE, MSG_COMMENT_FAILURE)

        conn.commit()
        return _result(CODE_SUCCESS, MSG_COMMENT_SUCCESS)

    except Exception:
        _safe_rollback(conn)
        return _result(CODE_FAILURE, MSG_COMMENT_FAILURE)
    finally:
        if own_connection and conn is not None:
            conn.close()


def admin_delete(event_id=None, comment_id=None, db_conn=None):
    """投稿詳細画面から渡された値に応じて削除を振り分ける。

    - comment_id がある  → コメントのみ削除(戻り先用に event_id が一緒に来てもよい)
    - event_id のみ      → イベント投稿を削除
    - どちらも無い       → 失敗(code = 8)
    """
    if comment_id is not None:
        return delete_event_comment(comment_id, db_conn)
    if event_id is not None:
        return delete_event(event_id, db_conn)
    return _result(CODE_FAILURE, MSG_EVENT_FAILURE)


def _safe_rollback(conn):
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception:
        pass
