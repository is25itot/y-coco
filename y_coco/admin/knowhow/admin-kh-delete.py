"""admin-kh-delete.py : ノウハウ削除機能 (M-FL11)

管理者がユーザーのノウハウ投稿・コメントを削除する。
ノウハウ投稿とコメントは別々に削除できる。

  成功 : コミット、code = 0
  失敗 : ロールバック、code = 9

※ ファイル名にハイフンが含まれるため、通常の `import` では読み込めない。
   読み込む側(admin_views.py)では importlib を使うか、ファイル名を
   admin_kh_delete.py に変更すること。

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""

CODE_SUCCESS = 0
CODE_FAILURE = 9

# comment / notification テーブルの post_type の値(要確認: 設計書に値の定義なし)
POST_TYPE_KNOWHOW = 2

MSG_KNOWHOW_SUCCESS = "ノウハウを削除しました。"
MSG_KNOWHOW_FAILURE = "ノウハウの削除に失敗しました。"
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


def delete_knowhow(knowhow_id, db_conn=None):
    """ノウハウを削除する(紐づくコメント・通知も同じトランザクションで削除)。

    削除後にSELECTで存在確認し、まだ存在する場合はロールバックして code = 9。
    削除対象が最初から無かった場合(0件削除)も失敗(code = 9)として扱う。
    """
    target_id = _to_int(knowhow_id)
    if target_id is None:
        return _result(CODE_FAILURE, MSG_KNOWHOW_FAILURE)

    own_connection = db_conn is None
    conn = None
    try:
        conn = db_conn if db_conn is not None else _open_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM comment WHERE post_type = %s AND post_id = %s",
                (POST_TYPE_KNOWHOW, target_id),
            )
            cur.execute(
                "DELETE FROM notification WHERE post_type = %s AND post_id = %s",
                (POST_TYPE_KNOWHOW, target_id),
            )
            cur.execute("DELETE FROM knowhow WHERE id = %s", (target_id,))
            deleted_count = cur.rowcount

            # 該当のノウハウがまだ存在しないか確認する
            cur.execute("SELECT id FROM knowhow WHERE id = %s", (target_id,))
            still_exists = cur.fetchone() is not None

        if still_exists or deleted_count < 1:
            conn.rollback()
            return _result(CODE_FAILURE, MSG_KNOWHOW_FAILURE)

        conn.commit()
        return _result(CODE_SUCCESS, MSG_KNOWHOW_SUCCESS)

    except Exception:
        _safe_rollback(conn)
        return _result(CODE_FAILURE, MSG_KNOWHOW_FAILURE)
    finally:
        if own_connection and conn is not None:
            conn.close()


def delete_knowhow_comment(comment_id, db_conn=None):
    """ノウハウに付いたコメントを1件削除する(イベントのコメントは対象外)。"""
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
                (target_id, POST_TYPE_KNOWHOW),
            )
            deleted_count = cur.rowcount

            cur.execute(
                "SELECT id FROM comment WHERE id = %s AND post_type = %s",
                (target_id, POST_TYPE_KNOWHOW),
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


def admin_kh_delete(knowhow_id=None, comment_id=None, db_conn=None):
    """投稿詳細画面から渡された値に応じて削除を振り分ける。

    - comment_id がある  → コメントのみ削除(戻り先用に knowhow_id が一緒に来てもよい)
    - knowhow_id のみ    → ノウハウを削除
    - どちらも無い       → 失敗(code = 9)
    """
    if comment_id is not None:
        return delete_knowhow_comment(comment_id, db_conn)
    if knowhow_id is not None:
        return delete_knowhow(knowhow_id, db_conn)
    return _result(CODE_FAILURE, MSG_KNOWHOW_FAILURE)


def _safe_rollback(conn):
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception:
        pass
