"""イベント投稿機能 (モジュール設計書: post.py / 機能ID FL22)

トランザクションを使い、イベントデータを安全に登録する。

処理の流れ
    1. 画面から送信された各入力項目を受け取る
    2. PostForm でバリデーションチェック (er)。FALSE ならエラーメッセージを表示
    3. session["user"] から userid を取得
    4. DBコネクションを取得しトランザクション開始
    5. 画像が選ばれていれば新しいUUIDを発行し、ファイル名をUUIDに変更 (image_path)
    6. event_post テーブルへ INSERT
    7. WHERE句で投稿内容を検索して確認 (er2)
         er2 = FALSE -> ロールバック, code = 3
         er2 = TRUE  -> コミット,     code = 0 (event_post_id を返す)

code の意味
    0: 登録成功
    3: イベント投稿の登録失敗 (ロールバック済み)
"""
import logging
import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.routing import BuildError

from y_coco.db import get_connection
from y_coco.validation import PostForm

logger = logging.getLogger(__name__)

event_post_bp = Blueprint(
    "event_post",
    __name__,
    url_prefix="/event",
    template_folder="../templates",
)

# --- 定数 -------------------------------------------------------------
CODE_SUCCESS = 0
CODE_POST_FAILED = 3

TEMPLATE_POST = "event/post.html"
LOGIN_ENDPOINT = "login.login"  # login.py 側のエンドポイント名に合わせる
DETAIL_ENDPOINT = "event_detail.show"  # detail.py 側のエンドポイント名に合わせる

MAX_LOCATION = 100
MAX_ADDRESS = 100

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

MAX_FEE = 2147483647  # INT の上限
MAX_PARKING_INFO = 100
MAX_CONTACT_INFO = 255

INSERT_SQL = (
    "INSERT INTO event_post "
    "(user_id, title, description, imagepath, `datetime`, fee, "
    "location, address, parking_info, contact_info, created_at) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
)
VERIFY_SQL = (
    "SELECT id FROM event_post "
    "WHERE id = %s AND user_id = %s AND title = %s AND address = %s"
)


# --- 補助関数 ---------------------------------------------------------
def _url(endpoint, fallback, **values):
    """エンドポイントが未登録でも落ちないように URL を作る。"""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return fallback


def _detail_url(event_post_id):
    return _url(DETAIL_ENDPOINT, f"/events/{event_post_id}", event_id=event_post_id)


def _first(row):
    """カーソルの種類 (タプル / 辞書) に関わらず id を取り出す。"""
    return row["id"] if isinstance(row, dict) else row[0]


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:  # 接続断などでロールバック自体が失敗しても処理を続ける
        logger.exception("ロールバックに失敗しました")


def _form_error_messages(form):
    """バリデーションフォームのエラーを文字列のリストにする。"""
    messages = []
    for field_errors in getattr(form, "errors", {}).values():
        if isinstance(field_errors, (list, tuple)):
            messages.extend(str(e) for e in field_errors)
        else:
            messages.append(str(field_errors))
    return messages


def _build_data(form):
    """PostForm の検証済み値と、PostForm に無い項目から登録用データを作る。"""
    src = request.form
    errors = []

    fee_text = (src.get("fee") or "").strip()
    fee = 0  # 未入力は 0 (無料)
    if fee_text:
        try:
            fee = int(fee_text)
        except ValueError:
            errors.append("料金は整数で入力してください。")
        else:
            if fee < 0 or fee > MAX_FEE:
                errors.append("料金は0以上の整数で入力してください。")

    location = form.location.data or ""
    address = src.get("address") or ""
    parking_info = src.get("parking_info") or ""
    contact_info = src.get("contact_info") or ""
    if len(location) > MAX_LOCATION:
        errors.append(f"開催場所は{MAX_LOCATION}文字以内で入力してください。")
    if len(address) > MAX_ADDRESS:
        errors.append(f"住所は{MAX_ADDRESS}文字以内で入力してください。")
    if len(parking_info) > MAX_PARKING_INFO:
        errors.append(f"駐車場は{MAX_PARKING_INFO}文字以内で入力してください。")
    if len(contact_info) > MAX_CONTACT_INFO:
        errors.append(f"連絡先は{MAX_CONTACT_INFO}文字以内で入力してください。")

    data = {
        "title": form.title.data,
        "description": form.desc.data,
        "datetime": form.dt.data,   # YYYY-MM-DD (DBの列は DATE)
        "fee": fee,
        "location": location,
        "address": address,
        "parking_info": parking_info,
        "contact_info": contact_info,
    }
    return data, errors


def _has_image(image_file):
    return image_file is not None and bool(image_file.filename)


def _issue_image_name(original_filename):
    """選んだ画像に新しいUUIDを発行し、ファイル名をUUID + 拡張子にする。"""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"対応していない画像形式です: {ext}")
    return f"{uuid.uuid4().hex}{ext}"


def _upload_dir():
    # DBには「ファイル名だけ」入れ、static/uploads/ 直下に保存する
    return current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.static_folder or "static", "uploads"
    )


def _save_image(image_file, image_name):
    directory = _upload_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, image_name)
    image_file.stream.seek(0)  # バリデーションで読まれていても先頭から保存する
    image_file.save(path)
    return path


def _remove_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.exception("画像ファイルの削除に失敗しました: %s", path)


# --- 登録処理 ---------------------------------------------------------
def save_event_post(userid, data, image_file=None):
    """トランザクションでイベントを登録する。

    戻り値: (code, event_post_id)
        成功時 (0, 登録した行のid) / 失敗時 (3, None)
    """
    saved_path = None
    conn = get_connection()
    try:
        conn.begin()

        image_path = None
        if _has_image(image_file):
            image_path = _issue_image_name(image_file.filename)

        with conn.cursor() as cur:
            cur.execute(
                INSERT_SQL,
                (
                    userid,
                    data["title"],
                    data["description"],
                    image_path,
                    data["datetime"],
                    data["fee"],
                    data["location"],
                    data["address"],
                    data["parking_info"],
                    data["contact_info"],
                ),
            )
            new_id = cur.lastrowid

            cur.execute(
                VERIFY_SQL,
                (new_id, userid, data["title"], data["address"]),
            )
            row = cur.fetchone()

        er2 = row is not None
        if not er2:
            _safe_rollback(conn)
            return CODE_POST_FAILED, None

        # 画像はコミット直前に保存する (保存に失敗したらロールバックされる)
        if image_path:
            saved_path = _save_image(image_file, image_path)

        conn.commit()
        return CODE_SUCCESS, _first(row)
    except Exception:
        logger.exception("イベント投稿の登録に失敗しました")
        _safe_rollback(conn)
        _remove_file(saved_path)
        return CODE_POST_FAILED, None
    finally:
        conn.close()


# --- ルート -----------------------------------------------------------
@event_post_bp.route("/post", methods=["GET", "POST"])
@event_post_bp.route("/post", methods=["GET", "POST"])
def post_event():
    user = session.get("user")
    if not user:
        return redirect(_url(LOGIN_ENDPOINT, "/login"))
    userid = user["id"]

    form = PostForm()
    if request.method == "GET":
        return render_template(TEMPLATE_POST, form=form)

    if not form.validate_on_submit():
        ev_er_message = "\n".join(_form_error_messages(form))
        return render_template(TEMPLATE_POST, form=form, ev_er_message=ev_er_message)

    data, errors = _build_data(form)
    if errors:
        return render_template(
            TEMPLATE_POST, form=form, ev_er_message="\n".join(errors)
        )

    code, event_post_id = save_event_post(userid, data, request.files.get("image"))
    if code != CODE_SUCCESS:
        return (
            render_template(
                TEMPLATE_POST,
                form=form,
                ev_er_message="イベントの投稿に失敗しました。時間をおいて再度お試しください。",
                code=code,
            ),
            500,
        )

    return redirect(_detail_url(event_post_id))