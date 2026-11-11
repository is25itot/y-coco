"""user_detail.py : アカウント詳細閲覧機能 (M-FL5, M-FL6)

ユーザー一覧で選択されたユーザーIDを基に、DBからアカウント情報
(アイコン・ユーザーネーム・投稿内容など)を取得してHTMLへ引き渡す。

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""


def _open_connection():
    from y_coco.db import get_connection
    return get_connection()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fetch_account(cur, user_id):
    cur.execute(
        "SELECT id, username, imagepath, admin_flg FROM users WHERE id = %s",
        (user_id,),
    )
    return cur.fetchone()


def get_account(selected_user_id, db_conn=None):
    """ユーザー1件を取得する。IDが不正・存在しない場合は None。(削除確認画面などで使う)"""
    user_id = _to_int(selected_user_id)
    if user_id is None:
        return None

    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else _open_connection()
    try:
        with conn.cursor() as cur:
            return _fetch_account(cur, user_id)
    finally:
        if own_connection:
            conn.close()


def merge_posts(events, knowhows):
    """イベントとノウハウを post_type 付きで1つの配列にし、新しい順に並べる。"""
    posts = [dict(e, post_type="event") for e in events] + \
            [dict(k, post_type="knowhow") for k in knowhows]
    posts.sort(key=lambda p: (str(p.get("created_at") or ""), p["id"]), reverse=True)
    return posts


def get_user_detail(selected_user_id, db_conn=None):
    """選択されたユーザーの詳細情報を取得する。

    戻り値:
        {"user": dict, "events": list, "knowhows": list,
         "posts": list(イベント+ノウハウ), "comments": list}
        ユーザーIDが不正、または該当ユーザーが存在しない場合は None
    """
    user_id = _to_int(selected_user_id)
    if user_id is None:
        return None

    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else _open_connection()
    try:
        with conn.cursor() as cur:
            user = _fetch_account(cur, user_id)
            if not user:
                return None

            cur.execute(
                "SELECT id, title, created_at FROM event_post "
                "WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            events = list(cur.fetchall() or [])

            cur.execute(
                "SELECT id, title, created_at FROM knowhow "
                "WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            knowhows = list(cur.fetchall() or [])

            cur.execute(
                "SELECT id, post_type, post_id, comment, created_at "
                "FROM comment WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            comments = list(cur.fetchall() or [])

        return {
            "user": user,
            "events": events,
            "knowhows": knowhows,
            "posts": merge_posts(events, knowhows),
            "comments": comments,
        }
    finally:
        if own_connection:
            conn.close()