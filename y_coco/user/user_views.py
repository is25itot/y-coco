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
    redirect,
    render_template,
    request,
    url_for,
    abort,
    current_app,
)
from flask_login import current_user, login_required, login_user
from y_coco.auth import User
from werkzeug.routing import BuildError

from y_coco.db import POST_TYPE_EVENT, POST_TYPE_KNOWHOW, connection_scope, get_user_by_username
from y_coco.detail import load_event_detail
from y_coco.kh_detail import load_kh_detail
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
    return current_user.id if current_user.is_authenticated else None


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
    # すでにログイン中なら登録画面は見せない
    if current_user.is_authenticated:
        return _redirect_to(EVENT_LIST_ENDPOINT, fallback="/events")

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

    # ★ 登録成功 → そのままログイン状態にする
    row = get_user_by_username(username)
    if row is None:
        # 登録は成功したが取得できなかった場合は、通常のログイン画面へ
        flash("アカウントを登録しました。ログインしてください", "success")
        return _redirect_to(LOGIN_ENDPOINT, fallback="/login")

    login_user(User(row))
    flash("アカウントを登録しました", "success")
    return _redirect_to(EVENT_LIST_ENDPOINT, fallback="/events")


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
        return render_template("account/prof_edit.html",
                               username=edit.get_username(userid))

    from y_coco.validation import ImageForm, UserForm

    newusername = request.form.get("username", "").strip()
    newimage = request.files.get("image")

    ok = True
    for form in (UserForm(), ImageForm()):
        if not form.validate_on_submit():
            for errors in form.errors.values():
                for e in errors:
                    flash(e, "error")
            ok = False
    if not ok:
        return render_template("account/prof_edit.html", username=newusername), 400

    code, error_msg = edit.update_profile(
        userid, newusername, newimage,
        upload_root=current_app.config["UPLOAD_FOLDER"],
    )
    if code != 0:
        flash(error_msg or MSG_PROFILE_FAILED, "error")
        return render_template("account/prof_edit.html", username=newusername), 400

    flash("プロフィールを変更しました", "success")
    return redirect(url_for("user.myaccount"))


@user_bp.route("/password/change", methods=["GET", "POST"])
@login_required
def password_change():
    if request.method == "GET":
        return render_template("account/pass_change.html")

    from y_coco.validation import PassChangeForm

    form = PassChangeForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for e in errors:
                flash(e, "error")
        return render_template("account/pass_change.html"), 400

    code, error_msg = edit.change_password(
        _current_user_id(),
        form.nowpass.data,
        form.newpass.data,
        form.repass.data,
    )
    if code != 0:
        flash(error_msg or MSG_PASSWORD_FAILED, "error")
        return render_template("account/pass_change.html"), 400

    flash("パスワードを変更しました", "success")
    return redirect(url_for("user.myaccount"))


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

    code, _msg = delete.delete_post(post_id, _current_user_id(), kind)
    flash(MSG_DELETE_OK if code == 0 else MSG_DELETE_FAILED)
    return redirect(url_for("user.my_posts"))


# ---------------------------------------------------------------------------
# 通知確認(FL15,16,17)
# ---------------------------------------------------------------------------
@user_bp.route("/notifications")
@login_required
def notifications():
    uid = _current_user_id()
    notification_list, display_msg = notification_check.get_notifications(uid)

    # 画面に出した未読を既読にする (今回の表示では未読の強調が残る)
    unread_ids = [n["notification_id"] for n in notification_list if not n["read_flg"]]
    if unread_ids:
        notification_check.mark_as_read(unread_ids, uid)

    return render_template(
        "account/notifications.html",
        notification_list=notification_list,
        display_msg=display_msg,
    )


# ---------------------------------------------------------------------------
# 削除確認画面 (GET)。実際の削除は delete_post (POST) が行う
# ---------------------------------------------------------------------------
def _load_comment(comment_id, post_type):
    with connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.id, c.user_id, c.post_id, c.comment, c.created_at, "
                "u.username, u.imagepath AS usericon "
                "FROM `comment` c JOIN users u ON u.id = c.user_id "
                "WHERE c.id = %s AND c.post_type = %s",
                (comment_id, post_type),
            )
            return cur.fetchone()


@user_bp.route("/event/<int:event_id>/delete/confirm")
@login_required
def event_delete_confirm(event_id):
    event, _ = load_event_detail(event_id)
    if event is None or event["user_id"] != _current_user_id():
        abort(404)
    return render_template("event/event_delete_confirm.html", event=event)


@user_bp.route("/knowhow/<int:knowhow_id>/delete/confirm")
@login_required
def kh_delete_confirm(knowhow_id):
    knowhow, _ = load_kh_detail(knowhow_id)
    if knowhow is None or knowhow["user_id"] != _current_user_id():
        abort(404)
    return render_template("knowhow/kh_delete_confirm.html", knowhow=knowhow)


@user_bp.route("/event-comments/<int:comment_id>/delete/confirm")
@login_required
def event_comment_delete_confirm(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_EVENT)
    if comment is None or comment["user_id"] != _current_user_id():
        abort(404)
    return render_template("event/event_comment_delete_confirm.html", comment=comment)


@user_bp.route("/knowhow-comments/<int:comment_id>/delete/confirm")
@login_required
def kh_comment_delete_confirm(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_KNOWHOW)
    if comment is None or comment["user_id"] != _current_user_id():
        abort(404)
    return render_template("knowhow/kh_comment_delete_confirm.html", comment=comment)