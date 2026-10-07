"""user_views.py の単体テスト(pytest)

DBや各モジュールの実処理には依存しないよう、user_views 内で参照している
モジュールの関数を monkeypatch で差し替えてテストする。
テンプレートも実ファイルに依存しないよう render_template を差し替える。

実行方法(y-coco/ 直下で):
    python -m pytest tests/test_user_views.py -v
"""
import os
import sys
from types import SimpleNamespace

import pytest
from flask import Flask

# y-coco/ を import パスに追加(user パッケージを読み込むため)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from user import user_views  # noqa: E402


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def calls():
    """各モジュール関数の呼び出し記録。"""
    return SimpleNamespace(rendered=[], log=[])


@pytest.fixture
def app(monkeypatch, calls):
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(user_views.user_bp)

    # テンプレートの代わりに「テンプレート名」を返す
    def fake_render(template_name, **context):
        calls.rendered.append((template_name, context))
        return f"rendered:{template_name}"

    monkeypatch.setattr(user_views, "render_template", fake_render)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login_client(client):
    """ログイン済み(session["user"]="user01")のクライアント。"""
    with client.session_transaction() as sess:
        sess["user"] = "user01"
    return client


def patch(monkeypatch, calls, module, name, result):
    """module.name を差し替え、呼び出し引数を calls.log に記録する。"""

    def fake(*args, **kwargs):
        calls.log.append((name, args, kwargs))
        return result

    monkeypatch.setattr(module, name, fake)


# ---------------------------------------------------------------------------
# ログイン必須(login_required)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/myaccount"),
        ("get", "/profile/edit"),
        ("get", "/password/change"),
        ("get", "/myposts"),
        ("get", "/notifications"),
        ("get", "/event/post"),
        ("get", "/knowhow/post"),
        ("post", "/delete/event/1"),
        ("post", "/notifications/read"),
        ("post", "/event/1/comment"),
        ("post", "/knowhow/1/comment"),
    ],
)
def test_未ログインはログイン画面へリダイレクト(client, method, path):
    res = getattr(client, method)(path)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")


def test_register_は未ログインでも表示できる(client):
    res = client.get("/register")
    assert res.status_code == 200


def test_セッションがdictでもuser_idを取得できる(app):
    with app.test_request_context():
        from flask import session

        session["user"] = {"user_id": "abc"}
        assert user_views._current_user_id() == "abc"
        session["user"] = "xyz"
        assert user_views._current_user_id() == "xyz"
        session.clear()
        assert user_views._current_user_id() is None


# ---------------------------------------------------------------------------
# 新規登録
# ---------------------------------------------------------------------------
def test_register_GETで登録画面を表示(client, calls):
    res = client.get("/register")
    assert res.status_code == 200
    assert calls.rendered[0][0] == "account/register.html"


def test_register_成功でログイン画面へ(client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.register, "register_user", 0)
    res = client.post("/register", data={"user_id": "u1", "password": "pw"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")
    assert calls.log == [("register_user", ("u1", "pw"), {})]


def test_register_失敗で登録画面を再表示(client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.register, "register_user", 1)
    res = client.post("/register", data={"user_id": "u1", "password": "pw"})
    assert res.status_code == 400
    assert calls.rendered[-1][0] == "account/register.html"
    with client.session_transaction() as sess:
        flashed = [m for _, m in sess["_flashes"]]
    assert user_views.MSG_REGISTER_FAILED in flashed


# ---------------------------------------------------------------------------
# マイアカウント / プロフィール変更 / パスワード変更
# ---------------------------------------------------------------------------
def test_myaccount_表示(login_client, calls):
    res = login_client.get("/myaccount")
    assert res.status_code == 200
    name, ctx = calls.rendered[0]
    assert name == "account/myaccount.html"
    assert ctx["user_id"] == "user01"


def test_profile_edit_GETで現在のユーザーネームを表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.edit, "get_username", "たろう")
    res = login_client.get("/profile/edit")
    assert res.status_code == 200
    name, ctx = calls.rendered[0]
    assert name == "account/prof_edit.html"
    assert ctx["username"] == "たろう"
    assert calls.log[0] == ("get_username", ("user01",), {})


def test_profile_edit_POST成功でマイアカウントへ(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.edit, "update_profile", 0)
    res = login_client.post("/profile/edit", data={"newusername": "はなこ"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/myaccount")
    name, args, _ = calls.log[0]
    assert name == "update_profile"
    assert args[0] == "user01"
    assert args[1] == "はなこ"
    assert args[2] is None  # 画像未選択


def test_profile_edit_POST失敗で再表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.edit, "update_profile", 1)
    patch(monkeypatch, calls, user_views.edit, "get_username", "たろう")
    res = login_client.post("/profile/edit", data={"newusername": "はなこ"})
    assert res.status_code == 400
    assert calls.rendered[-1][0] == "account/prof_edit.html"


def test_password_change_GET(login_client, calls):
    res = login_client.get("/password/change")
    assert res.status_code == 200
    assert calls.rendered[0][0] == "account/pass_change.html"


def test_password_change_成功でマイアカウントへ(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.edit, "change_password", 0)
    res = login_client.post(
        "/password/change",
        data={"nowpass": "old", "newpass": "new", "repass": "new"},
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/myaccount")
    assert calls.log == [("change_password", ("user01", "old", "new", "new"), {})]


def test_password_change_失敗で再表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.edit, "change_password", 2)
    res = login_client.post(
        "/password/change",
        data={"nowpass": "old", "newpass": "new", "repass": "x"},
    )
    assert res.status_code == 400
    assert calls.rendered[-1][0] == "account/pass_change.html"


# ---------------------------------------------------------------------------
# 過去投稿の閲覧
# ---------------------------------------------------------------------------
def test_myposts_投稿ありの表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.myposts, "get_my_posts", ([{"id": 1}], [], None))
    res = login_client.get("/myposts")
    assert res.status_code == 200
    name, ctx = calls.rendered[0]
    assert name == "account/myposts.html"
    assert ctx["post_list"] == [{"id": 1}]
    assert ctx["display_msg"] is None
    assert calls.log[0] == ("get_my_posts", ("user01",), {})


def test_myposts_投稿なしのメッセージを渡す(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.myposts, "get_my_posts", ([], [], "投稿なし"))
    login_client.get("/myposts")
    assert calls.rendered[0][1]["display_msg"] == "投稿なし"


# ---------------------------------------------------------------------------
# 投稿削除
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["event", "knowhow", "comment"])
def test_delete_成功(login_client, calls, monkeypatch, kind):
    patch(monkeypatch, calls, user_views.delete, "delete_post", 0)
    res = login_client.post(f"/delete/{kind}/7")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/myposts")
    assert calls.log == [("delete_post", (7, "user01", kind), {})]
    with login_client.session_transaction() as sess:
        assert user_views.MSG_DELETE_OK in [m for _, m in sess["_flashes"]]


def test_delete_失敗(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.delete, "delete_post", 3)
    res = login_client.post("/delete/event/7")
    assert res.status_code == 302
    with login_client.session_transaction() as sess:
        assert user_views.MSG_DELETE_FAILED in [m for _, m in sess["_flashes"]]


def test_delete_不正な種別は404(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.delete, "delete_post", 0)
    res = login_client.post("/delete/account/1")
    assert res.status_code == 404
    assert calls.log == []  # 削除処理は呼ばれない


def test_delete_GETは許可しない(login_client):
    assert login_client.get("/delete/event/1").status_code == 405


# ---------------------------------------------------------------------------
# 通知確認
# ---------------------------------------------------------------------------
def test_notifications_一覧表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.notification_check, "get_notifications",
          ([{"id": 1}], None))
    res = login_client.get("/notifications")
    assert res.status_code == 200
    name, ctx = calls.rendered[0]
    assert name == "account/notifications.html"
    assert ctx["notification_list"] == [{"id": 1}]


def test_notifications_通知なしメッセージ(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.notification_check, "get_notifications",
          ([], "通知無し"))
    login_client.get("/notifications")
    assert calls.rendered[0][1]["display_msg"] == "通知無し"


def test_notifications_read_JSONで既読化(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.notification_check, "mark_as_read", 0)
    res = login_client.post("/notifications/read",
                            json={"read_notification_ids": [1, 2]})
    assert res.status_code == 200
    assert res.get_json() == {"code": 0}
    assert calls.log == [("mark_as_read", ([1, 2],), {})]


def test_notifications_read_フォームでも受け取れる(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.notification_check, "mark_as_read", 0)
    res = login_client.post("/notifications/read",
                            data={"read_notification_ids": ["3", "4"]})
    assert res.status_code == 200
    assert calls.log == [("mark_as_read", (["3", "4"],), {})]


def test_notifications_read_失敗は500(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.notification_check, "mark_as_read", 1)
    res = login_client.post("/notifications/read", json={"read_notification_ids": [1]})
    assert res.status_code == 500
    assert res.get_json() == {"code": 1}


# ---------------------------------------------------------------------------
# イベント投稿 / コメント
# ---------------------------------------------------------------------------
def test_event_post_GETで投稿画面(login_client, calls):
    res = login_client.get("/event/post")
    assert res.status_code == 200
    assert calls.rendered[0][0] == "event/post.html"


def test_event_post_成功(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.event_post, "post_event", (0, 10))
    res = login_client.post("/event/post", data={"event_title": "お祭り"})
    # 詳細画面のエンドポイント(event_detail)が未登録なのでフォールバック先へ
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/event")
    name, args, _ = calls.log[0]
    assert name == "post_event"
    assert args[0]["event_title"] == "お祭り"
    assert args[2] == "user01"


def test_event_post_失敗で再表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.event_post, "post_event", (3, None))
    res = login_client.post("/event/post", data={"event_title": "お祭り"})
    assert res.status_code == 400
    assert calls.rendered[-1][0] == "event/post.html"


def test_event_comment_成功(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.event_comment, "add_comment", 0)
    res = login_client.post("/event/5/comment", data={"comment": "行きます"})
    assert res.status_code == 302
    assert calls.log == [("add_comment", (5, "user01", "行きます"), {})]
    with login_client.session_transaction() as sess:
        assert "_flashes" not in sess


def test_event_comment_失敗でflash(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.event_comment, "add_comment", 5)
    res = login_client.post("/event/5/comment", data={"comment": "行きます"})
    assert res.status_code == 302
    with login_client.session_transaction() as sess:
        assert user_views.MSG_COMMENT_FAILED in [m for _, m in sess["_flashes"]]


# ---------------------------------------------------------------------------
# ノウハウ投稿 / コメント
# ---------------------------------------------------------------------------
def test_knowhow_post_GETで投稿画面(login_client, calls):
    res = login_client.get("/knowhow/post")
    assert res.status_code == 200
    assert calls.rendered[0][0] == "knowhow/kh_post.html"


def test_knowhow_post_成功(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.kh_post, "post_knowhow", (0, 20))
    res = login_client.post("/knowhow/post",
                            data={"knowhow_title": "t", "knowhow_detail": "d"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/knowhow")
    name, args, _ = calls.log[0]
    assert name == "post_knowhow"
    assert args[0]["knowhow_title"] == "t"
    assert args[1] == "user01"


def test_knowhow_post_失敗で再表示(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.kh_post, "post_knowhow", (4, None))
    res = login_client.post("/knowhow/post",
                            data={"knowhow_title": "t", "knowhow_detail": "d"})
    assert res.status_code == 400
    assert calls.rendered[-1][0] == "knowhow/kh_post.html"


def test_knowhow_comment_成功(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.kh_comment, "add_comment", 0)
    res = login_client.post("/knowhow/9/comment", data={"comment": "参考になる"})
    assert res.status_code == 302
    assert calls.log == [("add_comment", (9, "user01", "参考になる"), {})]


def test_knowhow_comment_失敗でflash(login_client, calls, monkeypatch):
    patch(monkeypatch, calls, user_views.kh_comment, "add_comment", 6)
    res = login_client.post("/knowhow/9/comment", data={"comment": "参考になる"})
    assert res.status_code == 302
    with login_client.session_transaction() as sess:
        assert user_views.MSG_COMMENT_FAILED in [m for _, m in sess["_flashes"]]


# ---------------------------------------------------------------------------
# リダイレクト先エンドポイントが存在する場合
# ---------------------------------------------------------------------------
def test_エンドポイントが登録されていればそこへ遷移(app, login_client, calls, monkeypatch):
    app.add_url_rule("/event/<int:event_id>", "event_detail", lambda event_id: "ok")
    patch(monkeypatch, calls, user_views.event_comment, "add_comment", 0)
    res = login_client.post("/event/5/comment", data={"comment": "hi"})
    assert res.headers["Location"].endswith("/event/5")