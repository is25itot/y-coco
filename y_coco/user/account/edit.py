"""edit.py - アカウント編集 (使用機能: アカウント編集機能 FL3)

1. プロフィール変更 (ユーザーネーム・アイコン画像)
2. パスワード変更 (設計書の change_pass モジュール)

戻り値の code:
    プロフィール変更   0 ... 成功 / 1 ... 失敗 (画像・ユーザーネームのどちらかが更新できなかった)
    パスワード変更     0 ... 成功
                       5 ... 現在のパスワードが違う
                       6 ... 新しいパスワードが現在のパスワードと同じ
                       7 ... 新しいパスワードと再入力が一致しない
                       9 ... DB更新に失敗

※ パスワード変更の code は設計書で「(整数)」とだけ書かれているため、
   他モジュールで使用済みの 0/1/3/4/8 と重ならない値を割り当てています。
"""
import logging
import os
import uuid

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request)
from flask_login import current_user, login_required

from werkzeug.security import check_password_hash, generate_password_hash

from y_coco.db import connection_scope, run_in_transaction

logger = logging.getLogger(__name__)

CODE_SUCCESS = 0
CODE_PROFILE_ERROR = 1
CODE_PASS_CURRENT_WRONG = 5
CODE_PASS_SAME_AS_CURRENT = 6
CODE_PASS_MISMATCH = 7
CODE_PASS_DB_ERROR = 9

MSG_PROFILE_FAILED = "プロフィールの更新に失敗しました"
MSG_IMAGE_FAILED = "画像の更新に失敗しました"
MSG_NAME_DUPLICATE = "このユーザーネームは既に使用されています"
MSG_BAD_IMAGE = "対応していない画像形式です (png / jpg / jpeg / gif / webp)"
MSG_USER_NOT_FOUND = "ユーザー情報が見つかりません"
MSG_PASS_CURRENT_WRONG = "現在のパスワードが正しくありません"
MSG_PASS_SAME = "新しいパスワードは現在のパスワードと異なるものにしてください"
MSG_PASS_MISMATCH = "新しいパスワードと再入力のパスワードが一致しません"
MSG_PASS_FAILED = "パスワードの更新に失敗しました"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
UPLOAD_SUBDIR = "uploads"  # static/ 配下の保存先。imagepath は "uploads/<UUID>.<拡張子>" (50文字以内)

LOGIN_URL = "/login"
MYACCOUNT_URL = "/account"  # マイアカウント画面のURLに合わせて変更

edit_bp = Blueprint("edit", __name__, template_folder="../templates")


# ---------------------------------------------------------------------------
# 画像ファイルの扱い
# ---------------------------------------------------------------------------
def save_image(image, upload_root):
    """画像にUUIDのファイル名を付けて保存し、DBに入れる相対パスを返す。

    image       : filename 属性と save(path) メソッドを持つオブジェクト (werkzeugのFileStorage)
    upload_root : 保存先の基準フォルダ (通常は Flask の static フォルダ)
    例外        : 対応していない拡張子の場合 ValueError
    """
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(MSG_BAD_IMAGE)

    new_filename = uuid.uuid4().hex + ext  # UUIDでファイル名を付け替える
    save_dir = os.path.join(upload_root, UPLOAD_SUBDIR)
    os.makedirs(save_dir, exist_ok=True)
    image.save(os.path.join(save_dir, new_filename))
    return f"{UPLOAD_SUBDIR}/{new_filename}"


def _remove_image(upload_root, rel_path):
    """保存済み画像を削除する (失敗しても処理は止めない)。"""
    if not rel_path or os.path.isabs(rel_path) or ".." in rel_path.split("/"):
        return
    try:
        os.remove(os.path.join(upload_root, rel_path))
    except OSError:
        pass


# ---------------------------------------------------------------------------
# ロジック (単体テスト対象)
# ---------------------------------------------------------------------------
def get_username(user_id, db_conn=None):
    """ユーザーIDに紐づくユーザーネームを取得する (見つからなければ None)。"""
    with connection_scope(db_conn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return row["username"] if row else None


def update_profile(user_id, newusername=None, newimage=None,
                   upload_root=None, db_conn=None):
    """ユーザーネームとアイコン画像を更新する。どちらも省略可。

    どちらか一方でも更新できなければ全体をロールバックする。
    画像ファイルはDBのコミットが成功してから古いものを消す
    (失敗時に新しく保存したファイルを消す)ので、DBとファイルが食い違わない。

    戻り値: (code, error_msg)  成功時 error_msg は None
    """
    new_image_path = None
    has_new_image = newimage is not None and bool(getattr(newimage, "filename", ""))

    try:
        if has_new_image:
            new_image_path = save_image(newimage, upload_root)
    except ValueError as e:
        return CODE_PROFILE_ERROR, str(e)
    except Exception:
        logger.exception("画像の保存に失敗しました")
        return CODE_PROFILE_ERROR, MSG_IMAGE_FAILED

    old = {}

    def work(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT username, imagepath FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row is None:
                return False, MSG_USER_NOT_FOUND
            old["imagepath"] = row["imagepath"]

            # --- 画像 ---
            imgble = True
            if new_image_path:
                cur.execute("UPDATE users SET imagepath = %s WHERE id = %s",
                            (new_image_path, user_id))
                # where句で更新後のパスがあるか検索して確認
                cur.execute("SELECT id FROM users WHERE id = %s AND imagepath = %s",
                            (user_id, new_image_path))
                imgble = cur.fetchone() is not None
            if not imgble:
                return False, MSG_IMAGE_FAILED

            # --- ユーザーネーム ---
            if newusername is not None and newusername != row["username"]:
                # 自分以外に同じユーザーネームがいないか
                cur.execute("SELECT id FROM users WHERE username = %s AND id <> %s",
                            (newusername, user_id))
                if cur.fetchone() is not None:
                    return False, MSG_NAME_DUPLICATE
                cur.execute("UPDATE users SET username = %s WHERE id = %s",
                            (newusername, user_id))
                cur.execute("SELECT id FROM users WHERE id = %s AND username = %s",
                            (user_id, newusername))
                if cur.fetchone() is None:
                    return False, MSG_PROFILE_FAILED
        return True, None

    try:
        ok, error_msg = run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("プロフィール更新中に例外が発生しました")
        _remove_image(upload_root, new_image_path)
        return CODE_PROFILE_ERROR, MSG_PROFILE_FAILED

    if not ok:
        _remove_image(upload_root, new_image_path)  # ロールバックしたので新しい画像は不要
        return CODE_PROFILE_ERROR, error_msg or MSG_PROFILE_FAILED

    if new_image_path and old.get("imagepath") != new_image_path:
        _remove_image(upload_root, old.get("imagepath"))  # コミット後に元の画像を削除
    return CODE_SUCCESS, None


def change_password(user_id, nowpass, newpass, repass, db_conn=None):
    """パスワードを変更する。

    nowpass : 現在のパスワード (入力値)
    newpass : 新しいパスワード
    repass  : 新しいパスワード(再入力)
    戻り値  : (code, error_msg)  成功時 error_msg は None
    """
    if newpass != repass:
        return CODE_PASS_MISMATCH, MSG_PASS_MISMATCH
    if nowpass == newpass:
        return CODE_PASS_SAME_AS_CURRENT, MSG_PASS_SAME

    def work(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT passhash FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row is None:
                return False, (CODE_PASS_DB_ERROR, MSG_USER_NOT_FOUND)
            if not check_password_hash(row["passhash"], nowpass):
                return False, (CODE_PASS_CURRENT_WRONG, MSG_PASS_CURRENT_WRONG)

            newhash = generate_password_hash(newpass)  # 新パスワードをハッシュ化
            cur.execute("UPDATE users SET passhash = %s WHERE id = %s", (newhash, user_id))
            # where句で更新後のハッシュがあるか検索して確認 (passble)
            cur.execute("SELECT id FROM users WHERE id = %s AND passhash = %s",
                        (user_id, newhash))
            if cur.fetchone() is None:
                return False, (CODE_PASS_DB_ERROR, MSG_PASS_FAILED)
        return True, (CODE_SUCCESS, None)

    try:
        _, (code, error_msg) = run_in_transaction(work, db_conn)
    except Exception:
        logger.exception("パスワード更新中に例外が発生しました")
        return CODE_PASS_DB_ERROR, MSG_PASS_FAILED
    return code, error_msg


# ---------------------------------------------------------------------------
# 画面 (プロフィール変更 GD5 / パスワード変更 GD6)
# ---------------------------------------------------------------------------
def _flash_form_errors(form):
    for errors in form.errors.values():
        for error in errors:
            flash(error)


def _validate_profile():
    """userform / imageform でバリデーションチェック。

    ※ validation.py のクラス名 (UserForm / ImageForm) に合わせてください。
    """
    from y_coco.validation import ImageForm, UserForm

    ok = True
    for form in (UserForm(), ImageForm()):
        if not form.validate_on_submit():
            _flash_form_errors(form)
            ok = False
    return ok


def _validate_password():
    """passform でバリデーションチェック。※ validation.py のクラス名 (PassForm) に合わせてください。"""
    from y_coco.validation import PassForm

    form = PassForm()
    if form.validate_on_submit():
        return True
    _flash_form_errors(form)
    return False


@edit_bp.route("/account/profile/edit", methods=["GET", "POST"])
def profile_edit():
    user_id = current_user.is_authenticated
    if user_id is None:
        return redirect(LOGIN_URL)

    if request.method == "GET":
        return render_template("account/prof_edit.html",
                               username=get_username(user_id))

    newusername = request.form.get("username", "")
    newimage = request.files.get("image")

    if not _validate_profile():
        return render_template("account/prof_edit.html", username=newusername)

    code, error_msg = update_profile(user_id, newusername, newimage,
                                     upload_root=current_app.static_folder)
    if code != CODE_SUCCESS:
        flash(error_msg)
        return render_template("account/prof_edit.html", username=newusername)
    return redirect(MYACCOUNT_URL)


@edit_bp.route("/account/password/edit", methods=["GET", "POST"])
def pass_change():
    user_id = current_user.is_authenticated
    if user_id is None:
        return redirect(LOGIN_URL)

    if request.method == "GET":
        return render_template("account/pass_change.html")

    if not _validate_password():
        return render_template("account/pass_change.html")

    code, error_msg = change_password(
        user_id,
        request.form.get("nowpass", ""),
        request.form.get("newpass", ""),
        request.form.get("repass", ""),
    )
    if code != CODE_SUCCESS:
        flash(error_msg)
        return render_template("account/pass_change.html")
    flash("パスワードを変更しました")
    return redirect(MYACCOUNT_URL)