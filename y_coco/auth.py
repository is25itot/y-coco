"""auth.py - flask-login の設定とユーザークラス

ログイン状態の扱いはこのファイルと flask-login に一本化する。
  - ログイン/ログアウト : flask_login.login_user / logout_user
  - ログイン中ユーザー  : flask_login.current_user (id, username, imagepath, admin_flg)
  - ログイン必須の画面  : flask_login.login_required
  - 管理者必須の画面    : auth.admin_required
"""
from functools import wraps

from flask import abort
from flask_login import LoginManager, UserMixin, current_user, login_required

from y_coco import db

login_manager = LoginManager()
login_manager.login_view = "login.login"          # 未ログイン時の遷移先 (Blueprint名.関数名)
login_manager.login_message = "ログインしてください。"
login_manager.login_message_category = "error"    # flash のカテゴリを既存の "error" に合わせる


class User(UserMixin):
    """users テーブルの1行を flask-login 用に包んだクラス。

    UserMixin が is_authenticated / is_active / is_anonymous / get_id() を提供する。
    get_id() は str(self.id) を返す。
    """

    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.imagepath = row["imagepath"]
        self.admin_flg = bool(row["admin_flg"])


_SELECT_USER = (
    "SELECT id, username, passhash, imagepath, admin_flg FROM users WHERE {where}"
)


def _fetch_one(where, params):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT_USER.format(where=where), params)
            return cur.fetchone()
    finally:
        conn.close()


def find_user_by_username(username):
    """ユーザー名で users テーブルを検索する。存在しなければ None。(行は dict)"""
    return _fetch_one("username = %s", (username,))


def find_user_by_id(user_id):
    """id で users テーブルを検索する。存在しなければ None。(行は dict)"""
    return _fetch_one("id = %s", (user_id,))


@login_manager.user_loader
def load_user(user_id):
    """セッションに保存された id (文字列) から User を復元する。

    毎リクエスト呼ばれるため、プロフィール画像の変更や管理者権限の変更が
    次のリクエストからすぐ反映される。
    """
    try:
        row = find_user_by_id(int(user_id))
    except (TypeError, ValueError):
        return None
    if row is None:
        return None
    return User(row)


def admin_required(view):
    """管理者のみ許可するデコレータ。未ログインはログイン画面へ、一般ユーザーは403。"""

    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.admin_flg:
            abort(403)
        return view(*args, **kwargs)

    return wrapper