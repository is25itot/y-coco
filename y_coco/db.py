"""db.py - データベース接続 (XAMPP の MySQL / MariaDB)

get_connection() は DictCursor 付きの pymysql 接続を返す。
トランザクションは autocommit=False。共通の補助として
connection_scope() / run_in_transaction() / get_user_by_username() を持つ。
接続情報は config.py (環境変数で上書き可) に書く。
"""
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

from y_coco.config import Config

# comment.post_type / notification.post_type の値
POST_TYPE_EVENT = 1      # イベント
POST_TYPE_KNOWHOW = 2    # ノウハウ


def get_connection():
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def connection_scope(db_conn=None):
    """with connection_scope(db_conn) as conn: の形で使う接続管理。

    db_conn を渡した場合 (テストなど) はそれを使い、close しない。
    渡さなければ新しく接続し、ブロックを抜けるときに close する。
    """
    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else get_connection()
    try:
        yield conn
    finally:
        if own_connection:
            conn.close()


def run_in_transaction(work, db_conn=None):
    """work(conn) をトランザクション内で実行し、work の戻り値をそのまま返す。

    work は (成功かどうか, 追加情報) のタプルを返す約束。
      先頭が真  -> commit
      先頭が偽  -> rollback (戻り値は呼び出し元へそのまま返す)
      例外      -> rollback して例外を再送出 (呼び出し側で except する)
    """
    with connection_scope(db_conn) as conn:
        try:
            result = work(conn)
        except Exception:
            conn.rollback()
            raise

        ok = result[0] if isinstance(result, tuple) else result
        if ok:
            conn.commit()
        else:
            conn.rollback()
        return result


def get_user_by_username(username, db_conn=None):
    """ユーザーネームで users を1件検索する。存在しなければ None。"""
    with connection_scope(db_conn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, passhash, imagepath, admin_flg "
                "FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()