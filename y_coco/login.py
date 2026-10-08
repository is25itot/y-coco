"""
login.py
ユーザーのログイン認証処理を行うモジュールです。
"""

from werkzeug.security import check_password_hash
# db.py からユーザー取得関数をインポート（プロジェクトのDB構造に合わせて調整してください）
from y_coco.db import get_user_by_username

"""login.py - ログイン機能 (FL11, FL12)

ユーザー・管理者にログイン機能を提供し、ログイン状態かどうかを確認する。
セッションには session["user"] = {"id", "imagepath", "admin_flg"} を格納する。
"""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

from y_coco import db

login_bp = Blueprint("login", __name__, template_folder="templates")

LOGIN_TEMPLATE = "login.html"

MAX_USERNAME_LENGTH = 10   # users.username VARCHAR(10)
MAX_PASSWORD_LENGTH = 64   # validation.py の上限

MSG_EMPTY = "ユーザーネームとパスワードを入力してください。"
MSG_INVALID = "ユーザーネームまたはパスワードが正しくありません。"
MSG_OTHER_ACCOUNT = "別のアカウントでログイン中です。先にログアウトしてください。"


def is_logged_in():
    """セッションを参照してログイン状態かを返す (login_flg)。"""
    return bool(session.get("user"))


def find_user_by_username(username):
    """ユーザーテーブルを検索する。存在しなければ None。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, passhash, imagepath, admin_flg "
                "FROM users WHERE username = %s",
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def authenticate(username, password):
    """ユーザー名とパスワードを検証し、一致したユーザー行を返す。失敗時は None。

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


def build_session_user(user):
    """セッションに保存するユーザー情報を作る。"""
    return {
        "id": user["id"],
        "imagepath": user["imagepath"],
        "admin_flg": bool(user["admin_flg"]),
    }


@login_bp.route("/login", methods=["GET", "POST"])
def login():
    login_flg = is_logged_in()

    if request.method == "GET":
        return render_template(LOGIN_TEMPLATE, login_flg=login_flg)

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash(MSG_EMPTY, "error")
        return render_template(LOGIN_TEMPLATE, login_flg=login_flg, username=username)

    # ログイン中: 同じアカウントなら処理をスキップ、別アカウントはエラー
    if login_flg:
        user = find_user_by_username(username)
        if user is not None and user["id"] == session["user"]["id"]:
            return redirect(url_for("event_list.index"))
        flash(MSG_OTHER_ACCOUNT, "error")
        return render_template(LOGIN_TEMPLATE, login_flg=login_flg, username=username)

    user = authenticate(username, password)
    if user is None:
        flash(MSG_INVALID, "error")
        return render_template(LOGIN_TEMPLATE, login_flg=False, username=username)

    session.clear()  # セッション固定化対策
    session["user"] = build_session_user(user)
    return redirect(url_for("event_list.index"))
def authenticate_user(username, password):
    """
    入力されたユーザーネームとパスワードを検証し、認証結果を返します。

    Parameters:
        username (str): 入力されたユーザーネーム
        password (str): 入力された平文パスワード

    Returns:
        tuple: (success: bool, message_or_user: str | dict)
            - 成功時: (True, user_dict)
            - 失敗時: (False, "エラーメッセージ")
    """
    # 必須項目の入力チェック
    if not username or not password:
        return False, "ユーザーネームとパスワードを入力してください。"

    # データベースからユーザー情報を取得
    user = get_user_by_username(username)
    if not user:
        # セキュリティ上、ユーザーが存在しない場合も一般的なエラーメッセージを返す
        return False, "ユーザーネームまたはパスワードが正しくありません。"

    # パスワードハッシュの検証
    # （DB側のカラム名に合わせて user['password_hash'] または user['password'] を参照）
    stored_hash = user.get('password_hash') or user.get('password')

    if not stored_hash or not check_password_hash(stored_hash, password):
        return False, "ユーザーネームまたはパスワードが正しくありません。"

    # 認証成功（ユーザー情報を返す）
    return True, user