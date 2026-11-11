"""admin_views.py - 管理者向け画面のルーティング (M-FL1〜M-FL11)

URL はすべて /admin 配下。ログインしていなければログイン画面へ、
管理者でなければ 403 を返す。

このファイルは「薄い層」で、DB処理は各モジュールが担当する。
  アカウント一覧 ..... admin/account/account_list.py  (M-FL3, M-FL4)
  アカウント詳細 ..... admin/account/user_detail.py    (M-FL5, M-FL6)
  アカウント検索 ..... admin/account/user_search.py    (M-FL7〜M-FL9)
  アカウント削除 ..... admin/account/user_delete.py    (M-FL1, M-FL2 / エラーコード 7)
  イベント削除 ....... admin/event/admin_delete.py     (M-FL10 / エラーコード 8)
  ノウハウ削除 ....... admin/knowhow/admin_kh_delete.py(M-FL11 / エラーコード 9)

イベント・ノウハウの「一覧 / 詳細 / 検索」は共通モジュール (list.py / detail.py / search.py /
kh_*.py) が管理者を判定して管理者用テンプレートを使うため、ここには含まない。
"""
import os

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user

from y_coco.admin.account.account_list import get_account_list_context
from y_coco.admin.account.user_delete import delete_user
from y_coco.admin.account.user_detail import get_account, get_user_detail
from y_coco.admin.account.user_search import search_accounts
from y_coco.admin.event.admin_delete import (delete_event, delete_event_comment,
                                             get_event_comment)
from y_coco.admin.knowhow.admin_kh_delete import (delete_knowhow,
                                                  delete_knowhow_comment,
                                                  get_knowhow_comment)
from y_coco.detail import load_event_detail
from y_coco.kh_detail import load_kh_detail

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

CODE_OK = 0

MSG_NOT_FOUND = "対象が存在しません。"
MSG_ADMIN_PROTECTED = "管理者アカウントは削除できません。"

MAX_QUERY_LENGTH = 100


@admin_bp.before_request
def require_admin():
    if not current_user.is_authenticated:
        return redirect(url_for("login.login"))
    if not current_user.admin_flg:   # auth.User.admin_flg は bool
        abort(403)
    return None


# ------------------------------------------------------------------ 共通の補助
def _remove_upload(filename):
    """アップロード済み画像を削除する(失敗しても処理は続行)。"""
    if not filename:
        return
    folder = current_app.config.get("UPLOAD_FOLDER")
    if not folder:
        return
    try:
        os.remove(os.path.join(folder, os.path.basename(filename)))
    except OSError:
        pass


def _is_ok(result):
    return result["code"] == CODE_OK


def _flash_result(result):
    """モジュールの戻り値 {"code", "message"} を画面に出す。"""
    if _is_ok(result):
        flash(result["message"], "success")
    else:
        flash(f'{result["message"]}(エラーコード: {result["code"]})', "error")


# ------------------------------------------------------------------ アカウント
@admin_bp.route("/accounts")
def account_list():
    ctx = get_account_list_context()
    return render_template(
        "account/user_list.html",
        accounts=ctx["accounts"],
        message=ctx["display_msg"],
    )


@admin_bp.route("/accounts/search")
def account_search():
    query = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]
    if not query:
        return render_template(
            "account/user_search.html", query="", results=[], searched=False, error_code=0
        )

    result = search_accounts(query)
    if result["error_code"]:
        # 該当なし: エラーメッセージを出して入力欄を空に戻す
        flash(result["error_message"], "error")
        return render_template(
            "account/user_search.html", query="", results=[], searched=True,
            error_code=result["error_code"],
        )
    return render_template(
        "account/user_search.html", query=query, results=result["results"],
        searched=True, error_code=0,
    )


@admin_bp.route("/accounts/<int:user_id>")
def account_detail(user_id):
    detail = get_user_detail(user_id)
    if detail is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))
    return render_template(
        "account/user_detail.html",
        account=detail["user"],
        posts=detail["posts"],
        comments=detail["comments"],
    )


@admin_bp.route("/accounts/<int:user_id>/delete/confirm")
def account_delete_confirm(user_id):
    account = get_account(user_id)
    if account is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))
    if account["admin_flg"]:
        flash(MSG_ADMIN_PROTECTED, "error")
        return redirect(url_for("admin.account_detail", user_id=user_id))
    return render_template("account/user_delete_confirm.html", account=account)


@admin_bp.route("/accounts/<int:user_id>/delete", methods=["POST"])
def account_delete(user_id):
    account = get_account(user_id)
    if account is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))
    if account["admin_flg"]:
        flash(MSG_ADMIN_PROTECTED, "error")
        return redirect(url_for("admin.account_detail", user_id=user_id))

    result = delete_user(user_id)
    if _is_ok(result):
        for filename in result["image_files"]:
            _remove_upload(filename)
    _flash_result(result)
    if _is_ok(result):
        return redirect(url_for("admin.account_list"))
    return redirect(url_for("admin.account_detail", user_id=user_id))


# ------------------------------------------------------------------ イベント削除
@admin_bp.route("/events/<int:event_id>/delete/confirm")
def event_delete_confirm(event_id):
    event, _ = load_event_detail(event_id)
    if event is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("event_list.index"))
    return render_template("event/admin_event_delete_confirm.html", event=event)


@admin_bp.route("/events/<int:event_id>/delete", methods=["POST"])
def event_delete(event_id):
    result = delete_event(event_id)
    if _is_ok(result):
        _remove_upload(result["image_file"])
    _flash_result(result)
    if _is_ok(result):
        return redirect(url_for("event_list.index"))
    return redirect(url_for("event_detail.show", event_id=event_id))


@admin_bp.route("/event-comments/<int:comment_id>/delete/confirm")
def event_comment_delete_confirm(comment_id):
    comment = get_event_comment(comment_id)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("event_list.index"))
    return render_template("event/admin_event_comment_delete_confirm.html", comment=comment)


@admin_bp.route("/event-comments/<int:comment_id>/delete", methods=["POST"])
def event_comment_delete(comment_id):
    comment = get_event_comment(comment_id)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("event_list.index"))
    _flash_result(delete_event_comment(comment_id))
    return redirect(url_for("event_detail.show", event_id=comment["post_id"]))


# ------------------------------------------------------------------ ノウハウ削除
@admin_bp.route("/knowhow/<int:knowhow_id>/delete/confirm")
def kh_delete_confirm(knowhow_id):
    knowhow, _ = load_kh_detail(knowhow_id)
    if knowhow is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("kh_list.index"))
    return render_template("knowhow/admin_kh_delete_confirm.html", knowhow=knowhow)


@admin_bp.route("/knowhow/<int:knowhow_id>/delete", methods=["POST"])
def kh_delete(knowhow_id):
    result = delete_knowhow(knowhow_id)
    _flash_result(result)
    if _is_ok(result):
        return redirect(url_for("kh_list.index"))
    return redirect(url_for("kh_detail.show", knowhow_id=knowhow_id))


@admin_bp.route("/knowhow-comments/<int:comment_id>/delete/confirm")
def kh_comment_delete_confirm(comment_id):
    comment = get_knowhow_comment(comment_id)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("kh_list.index"))
    return render_template("knowhow/admin_kh_comment_delete_confirm.html", comment=comment)


@admin_bp.route("/knowhow-comments/<int:comment_id>/delete", methods=["POST"])
def kh_comment_delete(comment_id):
    comment = get_knowhow_comment(comment_id)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("kh_list.index"))
    _flash_result(delete_knowhow_comment(comment_id))
    return redirect(url_for("kh_detail.show", knowhow_id=comment["post_id"]))