"""logout.py - ログアウト機能 (FL13, FL14)

ログアウト状態なら処理を中止してエラーを返し、
ログイン状態ならログイン状態を破棄してログイン画面へ遷移する。
"""
from flask import Blueprint, flash, redirect, session, url_for
from flask_login import current_user, logout_user

logout_bp = Blueprint("logout", __name__)

CODE_OK = 0
CODE_NOT_LOGGED_IN = 2

MSG_NOT_LOGGED_IN = "ログインしていません。"


def do_logout():
    """ログイン状態を破棄する。戻り値は code (0: 成功 / 2: ログアウト状態)。"""
    if not current_user.is_authenticated:
        return CODE_NOT_LOGGED_IN
    logout_user()
    session.clear()   # flask-login 以外のセッション値(flashなど)も残さない
    return CODE_OK


@logout_bp.route("/logout", methods=["GET", "POST"])
def logout():
    code = do_logout()
    if code != CODE_OK:
        flash(MSG_NOT_LOGGED_IN, "error")
    return redirect(url_for("login.login"))