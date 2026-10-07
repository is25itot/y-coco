"""user_detail.py : アカウント詳細閲覧機能 (M-FL5, M-FL6)

ユーザー一覧で選択されたユーザーIDを基に、DBからアカウント情報
(アイコン・ユーザーネーム・投稿内容など)を取得してHTMLへ引き渡す。

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""


def _open_connection():
    from db import get_connection
    return get_connection()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_user_detail(selected_user_id, db_conn=None):
    """選択されたユーザーの詳細情報を取得する。

    戻り値:
        {"user": dict, "events": list, "knowhows": list, "comments": list}
        ユーザーIDが不正、または該当ユーザーが存在しない場合は None
    """
    user_id = _to_int(selected_user_id)
    if user_id is None:
        return None

    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else _open_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, imagepath, admin_flg "
                "FROM users WHERE id = %s",
                (user_id,),
            )
            user = cur.fetchone()
            if not user:
                return None

            cur.execute(
                "SELECT id, title, created_at FROM event_post "
                "WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            events = cur.fetchall()

            cur.execute(
                "SELECT id, title, created_at FROM knowhow "
                "WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            knowhows = cur.fetchall()

            cur.execute(
                "SELECT id, post_type, post_id, comment, created_at "
                "FROM comment WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            comments = cur.fetchall()

        return {
            "user": user,
            "events": list(events) if events else [],
            "knowhows": list(knowhows) if knowhows else [],
            "comments": list(comments) if comments else [],
        }
    finally:
        if own_connection:
            conn.close()
