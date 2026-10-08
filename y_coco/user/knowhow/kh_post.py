"""ノウハウ投稿機能 (モジュール設計書: kh-post.py / 機能ID FL31)

トランザクションを使い、ノウハウデータを安全に登録する。

処理の流れ
    1. 画面から送信された knowhow_title / knowhow_detail を受け取る
    2. KhForm でバリデーションチェック (er)。FALSE ならエラーメッセージを表示
    3. session["user"] から userid を取得
    4. DBコネクションを取得しトランザクション開始
    5. knowhow テーブルへ INSERT
    6. WHERE句で投稿内容を検索して確認 (er3)
         er3 = FALSE -> ロールバック, code = 4
         er3 = TRUE  -> コミット,     code = 0 (knowhow_post_id を返す)

code の意味
    0: 登録成功
    4: ノウハウ投稿の登録失敗 (ロールバック済み)

注意: ファイル名にハイフンが含まれるため `import kh-post` とは書けません。
      user_views.py で importlib を使って読み込むか、kh_post.py へのリネームを検討してください。
"""
import logging

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.routing import BuildError

from y_coco.db import get_connection
from y_coco.validation import KhPostForm

logger = logging.getLogger(__name__)

knowhow_post_bp = Blueprint(
    "knowhow_post",
    __name__,
    url_prefix="/knowhow",
    template_folder="../templates",
)

# --- 定数 -------------------------------------------------------------
CODE_SUCCESS = 0
CODE_POST_FAILED = 4

TEMPLATE_POST = "knowhow/kh_post.html"
LOGIN_ENDPOINT = "login.login"  # login.py 側のエンドポイント名に合わせる
DETAIL_ENDPOINT = "kh_detail.show"  # kh_detail.py 側のエンドポイント名に合わせる

INSERT_SQL = (
    "INSERT INTO knowhow (user_id, title, detail, created_at) "
    "VALUES (%s, %s, %s, NOW())"
)
VERIFY_SQL = (
    "SELECT id FROM knowhow WHERE id = %s AND user_id = %s AND title = %s"
)


# --- 補助関数 ---------------------------------------------------------
def _url(endpoint, fallback, **values):
    """エンドポイントが未登録でも落ちないように URL を作る。"""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return fallback


def _detail_url(knowhow_post_id):
    return _url(DETAIL_ENDPOINT, f"/knowhow/{knowhow_post_id}",
                knowhow_id=knowhow_post_id)


def _first(row):
    """カーソルの種類 (タプル / 辞書) に関わらず id を取り出す。"""
    return row["id"] if isinstance(row, dict) else row[0]


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:
        logger.exception("ロールバックに失敗しました")


def _form_error_messages(form):
    messages = []
    for field_errors in getattr(form, "errors", {}).values():
        if isinstance(field_errors, (list, tuple)):
            messages.extend(str(e) for e in field_errors)
        else:
            messages.append(str(field_errors))
    return messages


# --- 登録処理 ---------------------------------------------------------
def save_knowhow_post(userid, title, detail):
    """トランザクションでノウハウを登録する。

    戻り値: (code, knowhow_post_id)
        成功時 (0, 登録した行のid) / 失敗時 (4, None)
    """
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.execute(INSERT_SQL, (userid, title, detail))
            new_id = cur.lastrowid

            cur.execute(VERIFY_SQL, (new_id, userid, title))
            row = cur.fetchone()

        er3 = row is not None
        if not er3:
            _safe_rollback(conn)
            return CODE_POST_FAILED, None

        conn.commit()
        return CODE_SUCCESS, _first(row)
    except Exception:
        logger.exception("ノウハウ投稿の登録に失敗しました")
        _safe_rollback(conn)
        return CODE_POST_FAILED, None
    finally:
        conn.close()


# --- ルート -----------------------------------------------------------
@knowhow_post_bp.route("/post", methods=["GET", "POST"])
def post_knowhow():
    user = session.get("user")
    if not user:
        return redirect(_url(LOGIN_ENDPOINT, "/login"))
    userid = user["id"]

    form = KhPostForm()
    if request.method == "GET":
        return render_template(TEMPLATE_POST, form=form)

    if not form.validate_on_submit():
        kh_er_message = "\n".join(_form_error_messages(form))
        return render_template(TEMPLATE_POST, form=form, kh_er_message=kh_er_message)

    code, knowhow_post_id = save_knowhow_post(
        userid, form.title.data, form.kh_post.data
    )
    if code != CODE_SUCCESS:
        return (
            render_template(
                TEMPLATE_POST,
                form=form,
                kh_er_message="ノウハウの投稿に失敗しました。時間をおいて再度お試しください。",
                code=code,
            ),
            500,
        )

    return redirect(_detail_url(knowhow_post_id))