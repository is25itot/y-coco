"""logout.py - ログアウト機能 (FL13, FL14)

ログアウト状態なら処理を中止してエラーを返し、
ログイン状態ならセッションを破棄してログイン画面へ遷移する。
"""
from flask import Blueprint, flash, redirect, session, url_for

logout_bp = Blueprint("logout", __name__)

CODE_OK = 0
CODE_NOT_LOGGED_IN = 2

MSG_NOT_LOGGED_IN = "ログインしていません。"


def logout_user():
    """セッションを破棄する。戻り値は code (0: 成功 / 2: ログアウト状態)。"""
    session_check = bool(session.get("user"))
    if not session_check:
        return CODE_NOT_LOGGED_IN
    session.clear()
    return CODE_OK


@logout_bp.route("/logout", methods=["GET", "POST"])
def logout():
    code = logout_user()
    if code != CODE_OK:
        flash(MSG_NOT_LOGGED_IN, "error")
    return redirect(url_for("login.login"))