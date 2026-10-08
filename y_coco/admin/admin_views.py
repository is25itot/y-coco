"""admin_views.py - 管理者向け画面のルーティング (M-FL1〜M-FL11)

URL はすべて /admin 配下。ログインしていなければログイン画面へ、
管理者でなければ 403 を返す。DB 処理はトランザクションで行い、失敗時はロールバックする。

  アカウント一覧 / 検索 / 詳細 / 削除 ... M-FL1〜M-FL9  (エラーコード 7)
  イベント・コメントの削除 .............. M-FL10          (エラーコード 8)
  ノウハウ・コメントの削除 .............. M-FL11          (エラーコード 9)

イベント・ノウハウの「一覧 / 詳細 / 検索」は共通モジュール (list.py / detail.py / search.py /
kh_*.py) が管理者を判定して管理者用テンプレートを使うため、ここには含まない。
"""
import os

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

import db
from detail import POST_TYPE_EVENT, load_event_detail
from kh_detail import POST_TYPE_KNOWHOW, load_kh_detail

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="templates")

CODE_OK = 0
CODE_USER_DELETE_FAILED = 7
CODE_EVENT_DELETE_FAILED = 8
CODE_KH_DELETE_FAILED = 9

MSG_NO_RESULT = "該当するものがありませんでした。"
MSG_NOT_FOUND = "対象が存在しません。"
MSG_ADMIN_PROTECTED = "管理者アカウントは削除できません。"
MSG_DELETED = "削除しました。"
MSG_DELETE_FAILED = "削除に失敗しました。(エラーコード: {code})"

MAX_QUERY_LENGTH = 100


@admin_bp.before_request
def require_admin():
    user = session.get("user")
    if not user:
        return redirect(url_for("login.login"))
    if not user.get("admin_flg"):
        abort(403)
    return None


# ------------------------------------------------------------------ DB helpers
def _fetch_all(sql, params=()):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def _fetch_one(sql, params=()):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def _transaction(work):
    """work(cur) が True を返したらコミット、False / 例外ならロールバックする。成功なら True。"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            ok = work(cur)
        if ok:
            conn.commit()
            return True
        conn.rollback()
        return False
    except Exception:
        conn.rollback()
        current_app.logger.exception("管理者の削除処理に失敗しました")
        return False
    finally:
        conn.close()


def _remove_upload(filename):
    """アップロード済み画像を削除する(失敗しても処理は続行)。"""
    if not filename:
        return
    folder = current_app.config.get("UPLOAD_FOLDER")
    if not folder:
        return
    path = os.path.join(folder, os.path.basename(filename))
    try:
        os.remove(path)
    except OSError:
        pass


def _flash_result(ok, code):
    if ok:
        flash(MSG_DELETED, "success")
    else:
        flash(MSG_DELETE_FAILED.format(code=code), "error")


def escape_like(word):
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ------------------------------------------------------------------ アカウント
@admin_bp.route("/accounts")
def account_list():
    accounts = _fetch_all(
        "SELECT id, username, imagepath, admin_flg FROM users ORDER BY id DESC"
    )
    return render_template(
        "account/user_list.html",
        accounts=accounts,
        message=None if accounts else "アカウントがありません。",
    )


@admin_bp.route("/accounts/search")
def account_search():
    query = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]
    if not query:
        return render_template(
            "account/user_search.html", query="", results=[], searched=False, error_code=0
        )

    # ユーザーネームは半角英数字なので、空白区切りの単語の OR 検索で足りる
    words = list(dict.fromkeys(query.replace("\u3000", " ").split()))
    conditions = " OR ".join(["username LIKE %s"] * len(words))
    params = [f"%{escape_like(w)}%" for w in words]
    results = _fetch_all(
        f"SELECT id, username, imagepath, admin_flg FROM users WHERE {conditions} ORDER BY id DESC",
        params,
    )

    if not results:
        flash(MSG_NO_RESULT, "error")
        return render_template(
            "account/user_search.html", query="", results=[], searched=True, error_code=1
        )
    return render_template(
        "account/user_search.html", query=query, results=results, searched=True, error_code=0
    )


def _load_account(user_id):
    return _fetch_one(
        "SELECT id, username, imagepath, admin_flg FROM users WHERE id = %s", (user_id,)
    )


@admin_bp.route("/accounts/<int:user_id>")
def account_detail(user_id):
    account = _load_account(user_id)
    if account is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))

    events = _fetch_all(
        "SELECT id, title, created_at FROM event_post WHERE user_id = %s", (user_id,)
    )
    knowhows = _fetch_all(
        "SELECT id, title, created_at FROM knowhow WHERE user_id = %s", (user_id,)
    )
    posts = [dict(p, post_type="event") for p in events] + \
            [dict(p, post_type="knowhow") for p in knowhows]
    posts.sort(key=lambda p: str(p["created_at"] or ""), reverse=True)

    comments = _fetch_all(
        "SELECT id, post_type, post_id, comment, created_at FROM comment "
        "WHERE user_id = %s ORDER BY id DESC",
        (user_id,),
    )
    return render_template(
        "account/user_detail.html", account=account, posts=posts, comments=comments
    )


@admin_bp.route("/accounts/<int:user_id>/delete/confirm")
def account_delete_confirm(user_id):
    account = _load_account(user_id)
    if account is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))
    if account["admin_flg"]:
        flash(MSG_ADMIN_PROTECTED, "error")
        return redirect(url_for("admin.account_detail", user_id=user_id))
    return render_template("account/user_delete_confirm.html", account=account)


@admin_bp.route("/accounts/<int:user_id>/delete", methods=["POST"])
def account_delete(user_id):
    account = _load_account(user_id)
    if account is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("admin.account_list"))
    if account["admin_flg"]:
        flash(MSG_ADMIN_PROTECTED, "error")
        return redirect(url_for("admin.account_detail", user_id=user_id))

    image_files = [account["imagepath"]]

    def work(cur):
        cur.execute("SELECT imagepath FROM event_post WHERE user_id = %s", (user_id,))
        image_files.extend(r["imagepath"] for r in cur.fetchall())
        # 関連データ(通知・他人が付けたコメント・コメント・投稿)を先に消す
        cur.execute(
            "DELETE FROM notification WHERE senduser_id = %s OR receiver_id = %s",
            (user_id, user_id),
        )
        cur.execute(
            "DELETE FROM comment WHERE post_type = %s AND post_id IN "
            "(SELECT id FROM event_post WHERE user_id = %s)",
            (POST_TYPE_EVENT, user_id),
        )
        cur.execute(
            "DELETE FROM comment WHERE post_type = %s AND post_id IN "
            "(SELECT id FROM knowhow WHERE user_id = %s)",
            (POST_TYPE_KNOWHOW, user_id),
        )
        cur.execute("DELETE FROM comment WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM event_post WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM knowhow WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        # 削除できたか確認
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        return cur.fetchone() is None

    ok = _transaction(work)
    if ok:
        for f in image_files:
            _remove_upload(f)
    _flash_result(ok, CODE_USER_DELETE_FAILED)
    if ok:
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
    image = {}

    def work(cur):
        cur.execute("SELECT imagepath FROM event_post WHERE id = %s", (event_id,))
        row = cur.fetchone()
        image["file"] = row["imagepath"] if row else None
        cur.execute(
            "DELETE FROM comment WHERE post_type = %s AND post_id = %s",
            (POST_TYPE_EVENT, event_id),
        )
        cur.execute(
            "DELETE FROM notification WHERE post_type = %s AND post_id = %s",
            (POST_TYPE_EVENT, event_id),
        )
        cur.execute("DELETE FROM event_post WHERE id = %s", (event_id,))
        cur.execute("SELECT id FROM event_post WHERE id = %s", (event_id,))
        return cur.fetchone() is None  # まだ存在する → 失敗(ロールバック)

    ok = _transaction(work)
    if ok:
        _remove_upload(image.get("file"))
    _flash_result(ok, CODE_EVENT_DELETE_FAILED)
    if ok:
        return redirect(url_for("event_list.index"))
    return redirect(url_for("event_detail.show", event_id=event_id))


def _load_comment(comment_id, post_type):
    return _fetch_one(
        "SELECT c.id, c.user_id, c.post_type, c.post_id, c.comment, c.created_at, "
        "u.username, u.imagepath AS usericon "
        "FROM comment c JOIN users u ON u.id = c.user_id "
        "WHERE c.id = %s AND c.post_type = %s",
        (comment_id, post_type),
    )


def _delete_comment(comment_id, post_type):
    def work(cur):
        cur.execute(
            "DELETE FROM comment WHERE id = %s AND post_type = %s", (comment_id, post_type)
        )
        cur.execute("SELECT id FROM comment WHERE id = %s", (comment_id,))
        return cur.fetchone() is None

    return _transaction(work)


@admin_bp.route("/event-comments/<int:comment_id>/delete/confirm")
def event_comment_delete_confirm(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_EVENT)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("event_list.index"))
    return render_template("event/admin_event_comment_delete_confirm.html", comment=comment)


@admin_bp.route("/event-comments/<int:comment_id>/delete", methods=["POST"])
def event_comment_delete(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_EVENT)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("event_list.index"))
    ok = _delete_comment(comment_id, POST_TYPE_EVENT)
    _flash_result(ok, CODE_EVENT_DELETE_FAILED)
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
    def work(cur):
        cur.execute(
            "DELETE FROM comment WHERE post_type = %s AND post_id = %s",
            (POST_TYPE_KNOWHOW, knowhow_id),
        )
        cur.execute(
            "DELETE FROM notification WHERE post_type = %s AND post_id = %s",
            (POST_TYPE_KNOWHOW, knowhow_id),
        )
        cur.execute("DELETE FROM knowhow WHERE id = %s", (knowhow_id,))
        cur.execute("SELECT id FROM knowhow WHERE id = %s", (knowhow_id,))
        return cur.fetchone() is None

    ok = _transaction(work)
    _flash_result(ok, CODE_KH_DELETE_FAILED)
    if ok:
        return redirect(url_for("kh_list.index"))
    return redirect(url_for("kh_detail.show", knowhow_id=knowhow_id))


@admin_bp.route("/knowhow-comments/<int:comment_id>/delete/confirm")
def kh_comment_delete_confirm(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_KNOWHOW)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("kh_list.index"))
    return render_template("knowhow/admin_kh_comment_delete_confirm.html", comment=comment)


@admin_bp.route("/knowhow-comments/<int:comment_id>/delete", methods=["POST"])
def kh_comment_delete(comment_id):
    comment = _load_comment(comment_id, POST_TYPE_KNOWHOW)
    if comment is None:
        flash(MSG_NOT_FOUND, "error")
        return redirect(url_for("kh_list.index"))
    ok = _delete_comment(comment_id, POST_TYPE_KNOWHOW)
    _flash_result(ok, CODE_KH_DELETE_FAILED)
    return redirect(url_for("kh_detail.show", knowhow_id=comment["post_id"]))