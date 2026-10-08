"""テスト共通のフェイク (DB / Flask アプリ)。"""
import os
import sys
import types
from unittest import mock

from flask import Flask

# y-coco/ 直下のモジュールを import できるようにする
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:  # 実物の db.py が使えない環境 (pymysql 未導入など) ではスタブで代用
    import y_coco.db  # noqa: F401
except Exception:  # pragma: no cover
    _stub = types.ModuleType("db")
    _stub.get_connection = lambda: None
    sys.modules["db"] = _stub
    import y_coco.db as db  # noqa: F401


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.owner.executed.append((sql, params))

    def fetchone(self):
        return self.owner.ones.pop(0) if self.owner.ones else None

    def fetchall(self):
        return self.owner.alls.pop(0) if self.owner.alls else []


class FakeDB:
    """fetchone / fetchall の結果を順番に返す DB。get_connection に差し替えて使う。"""

    def __init__(self, ones=(), alls=()):
        self.ones = list(ones)
        self.alls = list(alls)
        self.executed = []
        self.connections = []

    def get_connection(self):
        conn = mock.MagicMock()
        conn.cursor.side_effect = lambda: FakeCursor(self)
        self.connections.append(conn)
        return conn


def make_client(module, blueprint, stub_endpoints=()):
    """blueprint を登録した Flask アプリを作り、(client, rendered) を返す。

    module.render_template はフェイクに差し替え、呼び出された
    (テンプレート名, コンテキスト) を rendered に溜める。
    """
    app = Flask(__name__)
    app.secret_key = "test"
    app.config["TESTING"] = True
    app.register_blueprint(blueprint)
    for rule, endpoint in stub_endpoints:
        app.add_url_rule(rule, endpoint=endpoint, view_func=lambda: "stub")

    rendered = []

    def fake_render(name, **ctx):
        rendered.append((name, ctx))
        return "rendered"

    patcher = mock.patch.object(module, "render_template", fake_render, create=True)
    patcher.start()
    return app.test_client(), rendered, patcher


def login_as(client, user_id=1, admin=False):
    with client.session_transaction() as sess:
        sess["user"] = {"id": user_id, "imagepath": "a.png", "admin_flg": admin}


def flashes(client):
    with client.session_transaction() as sess:
        return [m for _, m in sess.get("_flashes", [])]


# ---------------------------------------------------------------------------
# 画面テスト用: 全 Blueprint を登録した Flask アプリ
# ---------------------------------------------------------------------------
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# user_views.py (一般ユーザー向け機能) が公開する想定のエンドポイント。
# テンプレートの url_for はこれらを前提にしている (README 参照)。
USER_VIEW_ENDPOINTS = [
    ("account.register", "/register"),
    ("account.myaccount", "/account"),
    ("account.profile_edit", "/account/profile"),
    ("account.password_change", "/account/password"),
    ("account.myposts", "/account/posts"),
    ("account.notifications", "/notifications"),
    ("event.post", "/events/post"),
    ("event.comment", "/events/<int:event_id>/comment"),
    ("event.delete_confirm", "/events/<int:event_id>/delete/confirm"),
    ("event.delete", "/events/<int:event_id>/delete"),
    ("event.comment_delete_confirm", "/event-comments/<int:comment_id>/delete/confirm"),
    ("event.comment_delete", "/event-comments/<int:comment_id>/delete"),
    ("knowhow.post", "/knowhow/post"),
    ("knowhow.comment", "/knowhow/<int:knowhow_id>/comment"),
    ("knowhow.delete_confirm", "/knowhow/<int:knowhow_id>/delete/confirm"),
    ("knowhow.delete", "/knowhow/<int:knowhow_id>/delete"),
    ("knowhow.comment_delete_confirm", "/knowhow-comments/<int:comment_id>/delete/confirm"),
    ("knowhow.comment_delete", "/knowhow-comments/<int:comment_id>/delete"),
]


def make_full_app():
    """実テンプレートを使い、このリポジトリの Blueprint + user_views 相当のスタブを登録したアプリ。"""
    import importlib

    app = Flask("ycoco_test", root_path=ROOT, template_folder="templates",
                static_folder=os.path.join(ROOT, "static"))
    app.secret_key = "test"
    app.config["TESTING"] = True
    app.config["UPLOAD_FOLDER"] = os.path.join(ROOT, "static", "uploads")

    for mod_name, bp_name in [
        ("login", "login_bp"), ("logout", "logout_bp"), ("list", "list_bp"),
        ("detail", "detail_bp"), ("search", "search_bp"), ("kh_list", "kh_list_bp"),
        ("kh_detail", "kh_detail_bp"), ("kh_search", "kh_search_bp"),
        ("admin.admin_views", "admin_bp"),
    ]:
        app.register_blueprint(getattr(importlib.import_module(mod_name), bp_name))

    for endpoint, rule in USER_VIEW_ENDPOINTS:
        app.add_url_rule(rule, endpoint=endpoint, view_func=lambda **kw: "stub",
                         methods=["GET", "POST"])
    app.add_url_rule("/", endpoint="index", view_func=lambda: "stub")
    return app