"""register.py - アカウント登録 (使用機能: 登録機能 FL2)

検証済みのアカウント情報をトランザクションでDBへ登録する。

戻り値の code:
    0 ... 登録成功
    1 ... 登録失敗 (DB書き込みエラー・システム例外・ユーザーネーム重複など)
"""
import logging

from flask import Blueprint, flash, redirect, render_template, request
from werkzeug.security import generate_password_hash

from y_coco.db import run_in_transaction

logger = logging.getLogger(__name__)

CODE_SUCCESS = 0
CODE_ERROR = 1

MSG_REGISTER_FAILED = "アカウント登録に失敗しました"
MSG_DUPLICATE = "このユーザーネームは既に使用されています"

LOGIN_URL = "/login"  # 登録成功後の遷移先 (login.py のURLに合わせて変更)

register_bp = Blueprint("register", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# ロジック (単体テスト対象)
# ---------------------------------------------------------------------------
def register_user(user_id, password, db_conn=None):
    """検証済みのユーザーネームとパスワードを users テーブルへ登録する。

    user_id  : ユーザーネーム (users.username)。設計書上の名称は user_id(文字列)
    password : 平文パスワード (ハッシュ化して passhash に保存する)
    戻り値   : (code, error_msg)  成功時 error_msg は None
    """

    def work(conn):
        with conn.cursor() as cur:
            # 重複チェック (usernameにUNIQUE制約があれば二重の保険になる)
            cur.execute("SELECT id FROM users WHERE username = %s", (user_id,))
            if cur.fetchone() is not None:
                return False, MSG_DUPLICATE

            # INSERT文でアカウント情報を新規レコードとして挿入
            cur.execute(
                "INSERT INTO users (username, passhash, admin_flg) VALUES (%s, %s, 0)",
                (user_id, passhash),
            )
            insert_result = cur.rowcount == 1

        # DBに正しく挿入できたかチェック (is_success)
        if not insert_result:
            return False, MSG_REGISTER_FAILED
        return True, None

    try:
        passhash = generate_password_hash(password)
        is_success, error_msg = run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("アカウント登録中に例外が発生しました")
        return CODE_ERROR, MSG_REGISTER_FAILED

    if is_success:
        return CODE_SUCCESS, None
    return CODE_ERROR, error_msg or MSG_REGISTER_FAILED


# ---------------------------------------------------------------------------
# 画面 (新規登録画面 GD3)
# ---------------------------------------------------------------------------
def _validate(form_data):
    """validation.py のフォームで入力チェックする。

    ※ validation.py のクラス名 (UserForm) に合わせてください。
       エラーメッセージは flash でFlask側から画面に表示します。
    """
    from y_coco.validation import UserForm

    form = UserForm()
    if form.validate_on_submit():
        return True
    for errors in form.errors.values():
        for error in errors:
            flash(error)
    return False


@register_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("account/register.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    repassword = request.form.get("repassword", "")  # 「パスワード再入力」欄

    if not _validate(request.form):
        return render_template("account/register.html")
    if password != repassword:
        flash("パスワードが一致しません")
        return render_template("account/register.html")

    code, error_msg = register_user(username, password)
    if code != CODE_SUCCESS:
        # エラーメッセージ + 入力画面へ戻るボタン (テンプレート側)
        flash(error_msg)
        return render_template("account/register.html")

    flash("アカウントを登録しました")
    return redirect(LOGIN_URL)