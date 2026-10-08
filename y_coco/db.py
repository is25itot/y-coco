"""DB接続設定 (XAMPP の MariaDB / MySQL)

XAMPP の初期設定 (ユーザー root / パスワード空 / ポート 3306) に合わせてあります。
変更したい場合は、下の既定値を直接書き換えるか、環境変数で上書きしてください。

事前準備:
    1. XAMPP コントロールパネルで MySQL を Start する
    2. phpMyAdmin (http://localhost/phpmyadmin) でデータベース y_coco を作成する
       (照合順序: utf8mb4_general_ci など utf8mb4 系)
    3. pip install pymysql
"""
import os
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# 接続設定
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.environ.get("YCOCO_DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("YCOCO_DB_PORT", "3306")),
    "user": os.environ.get("YCOCO_DB_USER", "root"),
    "password": os.environ.get("YCOCO_DB_PASSWORD", ""),
    "database": os.environ.get("YCOCO_DB_NAME", "y_coco"),
    "charset": "utf8mb4",
    # トランザクションは各モジュールで明示的に commit / rollback する
    "autocommit": False,
}

# ---------------------------------------------------------------------------
# テーブル共通の定数 (comment / notification テーブルの post_type 列の値)
# ---------------------------------------------------------------------------
POST_TYPE_EVENT = 1     # event_post
POST_TYPE_KNOWHOW = 2   # knowhow


def get_connection():
    """DB接続を作成して返す (結果は dict 形式の行で受け取れる)。"""
    # pymysql はここで読み込む (未インストールでも他モジュールの import を妨げない)
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(cursorclass=DictCursor, **DB_CONFIG)


@contextmanager
def connection_scope(db_conn=None):
    """db_conn が None なら新規接続し、終了時に閉じる。渡された接続は閉じない。"""
    owned = db_conn is None
    conn = get_connection() if owned else db_conn
    try:
        yield conn
    finally:
        if owned:
            conn.close()


def run_in_transaction(work, db_conn=None):
    """トランザクションを開始して work(conn) を実行する。

    work は (ok, result) を返す関数。
        ok=True  -> commit
        ok=False -> rollback
        例外発生 -> rollback して例外をそのまま再送出
    戻り値は work の (ok, result) をそのまま返す。

    db_conn を渡した場合は、その接続に対して begin / commit / rollback を行う
    (主にテスト用。通常は省略して内部で接続を作成する)。
    """
    with connection_scope(db_conn) as conn:
        try:
            conn.begin()
            ok, result = work(conn)
            if ok:
                conn.commit()
            else:
                conn.rollback()
            return ok, result
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise