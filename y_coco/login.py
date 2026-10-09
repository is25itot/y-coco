"""login.py - ログイン機能 (FL11, FL12)

ユーザー・管理者にログイン機能を提供する。
ログイン状態の管理は flask-login に任せる (y_coco/auth.py を参照)。
ログイン中のユーザー情報は current_user (id, username, imagepath, admin_flg) から参照する。
"""
from urllib.parse import urlparse

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash

from y_coco.auth import User, find_user_by_username

login_bp = Blueprint("login", __name__, template_folder="templates")

LOGIN_TEMPLATE = "login.html"
AFTER_LOGIN_ENDPOINT = "event_list.index"

MAX_USERNAME_LENGTH = 10   # users.username VARCHAR(10)
MAX_PASSWORD_LENGTH = 64   # validation.py の上限

MSG_EMPTY = "ユーザーネームとパスワードを入力してください。"
MSG_INVALID = "ユーザーネームまたはパスワードが正しくありません。"
MSG_OTHER_ACCOUNT = "別のアカウントでログイン中です。先にログアウトしてください。"


def is_logged_in():
    """ログイン状態かを返す (login_flg)。"""
    return current_user.is_authenticated


def authenticate(username, password):
    """ユーザー名とパスワードを検証し、一致したユーザー行(dict)を返す。失敗時は None。

    アカウント不在とパスワード不一致を区別しない (ユーザー名の存在を推測させない)。
    """
    if len(username) > MAX_USERNAME_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return None
    user = find_user_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user["passhash"], password):
        return None
    return user


def _redirect_after_login():
    """ログイン後の遷移先。@login_required から来た場合は元のページへ戻す。"""
    next_url = request.args.get("next", "")
    # オープンリダイレクト対策: 同一サイト内の相対パスのみ許可する
    parsed = urlparse(next_url)
    if next_url.startswith("/") and not next_url.startswith("//") and not parsed.netloc:
        return redirect(next_url)
    return redirect(url_for(AFTER_LOGIN_ENDPOINT))


@login_bp.route("/login", methods=["GET", "POST"])
def login():
    # login_flg はテンプレートへ app.py の context_processor が自動で渡す
    if request.method == "GET":
        return render_template(LOGIN_TEMPLATE)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash(MSG_EMPTY, "error")
        return render_template(LOGIN_TEMPLATE, username=username)

    # ログイン中: 同じアカウントなら処理をスキップ、別アカウントはエラー
    if current_user.is_authenticated:
        user = find_user_by_username(username)
        if user is not None and user["id"] == current_user.id:
            return redirect(url_for(AFTER_LOGIN_ENDPOINT))
        flash(MSG_OTHER_ACCOUNT, "error")
        return render_template(LOGIN_TEMPLATE, username=username)

    user = authenticate(username, password)
    if user is None:
        flash(MSG_INVALID, "error")
        return render_template(LOGIN_TEMPLATE, username=username)

    login_user(User(user))
    return _redirect_after_login()