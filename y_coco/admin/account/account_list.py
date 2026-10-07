"""account_list.py : アカウント一覧閲覧機能 (M-FL3, M-FL4)

管理者がすべてのユーザーアカウントを閲覧する。
SELECT文でユーザーテーブルを検索し、アカウントIDの降順で全件取得する。

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""

NO_ACCOUNT_MESSAGE = "アカウントがありません。"


def _open_connection():
    # テスト時に db.py(=DB接続)を読み込まなくて済むよう、使う直前にimportする
    from db import get_connection
    return get_connection()


def get_all_accounts(db_conn=None):
    """全アカウントをIDの降順で取得する。

    passhash は画面に不要なので取得しない。
    db_conn を渡した場合は呼び出し側が管理するため close しない。
    """
    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else _open_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, imagepath, admin_flg "
                "FROM users ORDER BY id DESC"
            )
            rows = cur.fetchall()
        return list(rows) if rows else []
    finally:
        if own_connection:
            conn.close()


def get_account_list_context(db_conn=None):
    """テンプレート(user_list.html)へ渡す値を作る。

    戻り値: {"accounts": 配列, "display_msg": 文字列 or None}
    """
    accounts = get_all_accounts(db_conn)
    return {
        "accounts": accounts,
        "display_msg": None if accounts else NO_ACCOUNT_MESSAGE,
    }
