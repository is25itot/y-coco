"""user_views.py

一般ユーザー向け画面のルーティングをまとめる Blueprint。
user/ 配下に作成済みの各モジュールをインポートして呼び出すだけの「薄い層」にする。
(DB処理・バリデーションは各モジュール側が担当する)

【このファイルが前提にしている各モジュールの関数】
    account/register.py
        register_user(user_id, password) -> code(int)            0:成功 / 1:失敗
    account/edit.py
        get_username(userid) -> username(str)
        update_profile(userid, newusername, newimage) -> code     0:成功 / 1:失敗
        change_password(userid, nowpass, newpass, repass) -> code 0:成功 / それ以外:失敗
    account/myposts.py
        get_my_posts(user_id) -> (post_list, comment_list, display_msg)
    account/delete.py
        delete_post(post_id, user_id, kind) -> code               0:成功 / 3:失敗
            kind は "event" / "knowhow" / "comment"
    account/notification_check.py
        get_notifications(user_id) -> (notification_list, display_msg)
        mark_as_read(read_notification_ids) -> code               0:成功
    event/post.py
        post_event(form, image, userid) -> (code, event_post_id)  0:成功 / 3:失敗
    event/comment.py
        add_comment(post_id, user_id, comment_text) -> code       0:成功 / 5:失敗
    knowhow/kh-post.py
        post_knowhow(form, userid) -> (code, knowhow_post_id)     0:成功 / 4:失敗
    knowhow/kh-comment.py
        add_comment(post_id, user_id, comment_text) -> code       0:成功 / 6:失敗

    ※ notification.py(通知登録)は comment.py / kh-comment.py が「通知イベントを送信」
      する設計のため、ここからは呼び出さない。
    ※ バリデーションエラーのメッセージは設計書の備考どおり、各モジュール側で
      flash() して画面に表示される前提。
"""

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.routing import BuildError

from y_coco.user.account import delete, edit, myposts, notification_check, register

user_bp = Blueprint("user", __name__, template_folder="templates")

# ---------------------------------------------------------------------------
# 設定値
# ---------------------------------------------------------------------------
# 他の担当(app.py / list.py / detail.py / login.py など)側のエンドポイント名。
# 実際の名前に合わせて変更する。未登録でもエラーにならず fallback のURLへ遷移する。
LOGIN_ENDPOINT = "login.login"
EVENT_LIST_ENDPOINT = "event_list.index"
EVENT_DETAIL_ENDPOINT = "event_detail.show"
KNOWHOW_LIST_ENDPOINT = "kh_list.index"
KNOWHOW_DETAIL_ENDPOINT = "kh_detail.show"

DELETE_KINDS = ("event", "knowhow", "comment")

# codeごとの画面表示メッセージ
MSG_REGISTER_FAILED = "アカウント登録に失敗しました"
MSG_PROFILE_FAILED = "プロフィールの変更に失敗しました"
MSG_PASSWORD_FAILED = "パスワードの変更に失敗しました"
MSG_DELETE_FAILED = "削除に失敗しました"
MSG_DELETE_OK = "削除しました"
MSG_EVENT_POST_FAILED = "イベントの投稿に失敗しました"
MSG_KNOWHOW_POST_FAILED = "ノウハウの投稿に失敗しました"
MSG_COMMENT_FAILED = "コメントの保存に失敗しました"


# ---------------------------------------------------------------------------
# 共通処理
# ---------------------------------------------------------------------------
def _current_user_id():
    """セッションからユーザーIDを取得する。未ログインなら None。"""
    user = current_user.is_authenticated
    if isinstance(user, dict):
        return user.get("id")
    return user


def login_required(view):
    """ログインしていなければログイン画面へ戻すデコレータ。"""
    from functools import wraps

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _current_user_id():
            return _redirect_to(LOGIN_ENDPOINT, fallback="/login")
        return view(*args, **kwargs)

    return wrapper


def _redirect_to(endpoint, fallback="/", **values):
    """エンドポイントが存在しない場合は fallback へ遷移する redirect。"""
    try:
        return redirect(url_for(endpoint, **values))
    except BuildError:
        return redirect(fallback)


# ---------------------------------------------------------------------------
# アカウント: 新規登録(FL2)
# ---------------------------------------------------------------------------
@user_bp.route("/register", methods=["GET", "POST"])
def register_view():
    if request.method == "GET":
        return render_template("account/register.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")
    repassword = request.form.get("repassword", "")

    from y_coco.validation import UserForm, PasswordForm
    ok = True
    for form in (UserForm(), PasswordForm()):
        if not form.validate_on_submit():
            for errors in form.errors.values():
                for e in errors:
                    flash(e, "error")
            ok = False
    if ok and password != repassword:
        flash("パスワードが一致しません", "error")
        ok = False
    if not ok:
        return render_template("account/register.html"), 400

    code, error_msg = register.register_user(username, password)
    if code != 0:
        flash(error_msg or MSG_REGISTER_FAILED, "error")
        return render_template("account/register.html"), 400

    flash("アカウントを登録しました", "success")
    return _redirect_to(LOGIN_ENDPOINT, fallback="/login")


# ---------------------------------------------------------------------------
# アカウント: マイアカウント / プロフィール変更 / パスワード変更(FL3)
# ---------------------------------------------------------------------------
@user_bp.route("/myaccount")
@login_required
def myaccount():
    uid = _current_user_id()
    return render_template(
        "account/myaccount.html",
        username=edit.get_username(uid),
        imagepath=current_user.imagepath,
    )


@user_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    userid = _current_user_id()

    if request.method == "GET":
        username = edit.get_username(userid)
        return render_template("account/prof_edit.html", username=username)

    code = edit.update_profile(
        userid,
        request.form.get("newusername", ""),
        request.files.get("newimage"),
    )
    if code == 0:
        return redirect(url_for("user.myaccount"))

    flash(MSG_PROFILE_FAILED)
    username = edit.get_username(userid)
    return render_template("account/prof_edit.html", username=username), 400


@user_bp.route("/password/change", methods=["GET", "POST"])
@login_required
def password_change():
    if request.method == "GET":
        return render_template("account/pass_change.html")

    code = edit.change_password(
        _current_user_id(),
        request.form.get("nowpass", ""),
        request.form.get("newpass", ""),
        request.form.get("repass", ""),
    )
    if code == 0:
        return redirect(url_for("user.myaccount"))

    flash(MSG_PASSWORD_FAILED)
    return render_template("account/pass_change.html"), 400


# ---------------------------------------------------------------------------
# アカウント: 過去投稿の閲覧(FL4,5,6)
# ---------------------------------------------------------------------------
@user_bp.route("/myposts")
@login_required
def my_posts():
    post_list, comment_list, display_msg = myposts.get_my_posts(_current_user_id())
    return render_template(
        "account/myposts.html",
        post_list=post_list,
        comment_list=comment_list,
        display_msg=display_msg,
    )


# ---------------------------------------------------------------------------
# 投稿削除(FL7): イベント / ノウハウ / コメント
# 削除確認画面(モーダル)で「削除」を押したときに POST される。
# ---------------------------------------------------------------------------
@user_bp.route("/delete/<kind>/<int:post_id>", methods=["POST"])
@login_required
def delete_post(kind, post_id):
    if kind not in DELETE_KINDS:
        return "Not Found", 404

    code = delete.delete_post(post_id, _current_user_id(), kind)
    flash(MSG_DELETE_OK if code == 0 else MSG_DELETE_FAILED)
    return redirect(url_for("user.my_posts"))


# ---------------------------------------------------------------------------
# 通知確認(FL15,16,17)
# ---------------------------------------------------------------------------
@user_bp.route("/notifications")
@login_required
def notifications():
    notification_list, display_msg = notification_check.get_notifications(
        _current_user_id()
    )
    return render_template(
        "account/notifications.html",
        notification_list=notification_list,
        display_msg=display_msg,
    )


@user_bp.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    """画面で確認した通知IDを既読にする。(JSON または フォームで受け取る)"""
    payload = request.get_json(silent=True) or {}
    ids = payload.get("read_notification_ids")
    if ids is None:
        ids = request.form.getlist("read_notification_ids")

    code = notification_check.mark_as_read(ids)
    return jsonify({"code": code}), (200 if code == 0 else 500)