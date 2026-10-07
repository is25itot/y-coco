"""user/knowhow/kh-post.py の単体テスト

実行 (y-coco ディレクトリで):
    python -m unittest tests.test_kh_post -v
    python -m pytest tests/test_kh_post.py
"""
import os
import sys
import unittest
from unittest import mock

from flask import Flask

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeConnection, FakeForm, load_module  # noqa: E402

mod = load_module("user/knowhow/kh-post.py", "y_coco_kh_post", ["KhForm"])

TITLE = "雪道の運転のコツ"
DETAIL = "スピードを出しすぎず、車間距離を十分にとりましょう。"


def sample_form(**overrides):
    form = {"knowhow_title": TITLE, "knowhow_detail": DETAIL}
    form.update(overrides)
    return form


class SaveKnowhowPostTest(unittest.TestCase):
    def run_save(self, conn, userid=1, title=TITLE, detail=DETAIL):
        with mock.patch.object(mod, "get_connection", return_value=conn):
            return mod.save_knowhow_post(userid, title, detail)

    def test_success_commits_and_returns_id(self):
        conn = FakeConnection(select_rows=[(10,)], lastrowid=10)
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (0, 10))
        self.assertEqual(conn.calls, ["begin", "commit", "close"])

    def test_insert_receives_user_title_and_detail(self):
        conn = FakeConnection(select_rows=[(10,)])
        self.run_save(conn, userid=3)

        (sql, params), = conn.statements("INSERT")
        self.assertIn("knowhow", sql)
        self.assertEqual(params, (3, TITLE, DETAIL))

    def test_verify_miss_rolls_back_with_code_4(self):
        conn = FakeConnection(select_rows=[None])
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (4, None))
        self.assertEqual(conn.calls, ["begin", "rollback", "close"])

    def test_insert_error_rolls_back_with_code_4(self):
        conn = FakeConnection(insert_error=RuntimeError("db down"))
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (4, None))
        self.assertIn("rollback", conn.calls)
        self.assertNotIn("commit", conn.calls)
        self.assertEqual(conn.calls[-1], "close")

    def test_commit_error_rolls_back_with_code_4(self):
        conn = FakeConnection(select_rows=[(10,)], commit_error=RuntimeError("boom"))
        code, _ = self.run_save(conn)

        self.assertEqual(code, 4)
        self.assertIn("rollback", conn.calls)

    def test_dict_cursor_row_is_supported(self):
        conn = FakeConnection(select_rows=[{"id": 42}])
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (0, 42))


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        self.app.register_blueprint(mod.knowhow_post_bp)
        self.client = self.app.test_client()

        self.render = mock.patch.object(
            mod, "render_template", return_value="rendered"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def login(self, user_id=1):
        with self.client.session_transaction() as sess:
            sess["user"] = user_id

    def use_form(self, valid=True, errors=None):
        mock.patch.object(
            mod, "KhForm", return_value=FakeForm(valid=valid, errors=errors)
        ).start()

    def use_db(self, conn):
        mock.patch.object(mod, "get_connection", return_value=conn).start()
        return conn

    def test_not_logged_in_redirects_to_login(self):
        resp = self.client.get("/knowhow/post")

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/login"))

    def test_get_renders_post_form(self):
        self.login()
        self.use_form()
        resp = self.client.get("/knowhow/post")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.render.call_args.args[0], "knowhow/kh_post.html")

    def test_validation_error_shows_message_and_skips_db(self):
        self.login()
        self.use_form(valid=False, errors={"knowhow_title": ["題名は5文字以上です"]})
        get_conn = mock.patch.object(mod, "get_connection").start()

        resp = self.client.post("/knowhow/post", data=sample_form())

        self.assertEqual(resp.status_code, 200)
        self.assertIn("題名は5文字以上です", self.render.call_args.kwargs["kh_er_message"])
        get_conn.assert_not_called()

    def test_success_redirects_to_detail(self):
        self.login()
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(10,)], lastrowid=10))

        resp = self.client.post("/knowhow/post", data=sample_form())

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/knowhow/10"))
        self.assertIn("commit", conn.calls)

    def test_user_id_comes_from_session_not_from_form(self):
        self.login(user_id=7)
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(10,)]))

        self.client.post("/knowhow/post", data=sample_form(user_id="999"))

        (_, params), = conn.statements("INSERT")
        self.assertEqual(params[0], 7)

    def test_db_failure_returns_500_with_message(self):
        self.login()
        self.use_form()
        self.use_db(FakeConnection(select_rows=[None]))

        resp = self.client.post("/knowhow/post", data=sample_form())

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.render.call_args.kwargs["code"], 4)
        self.assertIn("失敗", self.render.call_args.kwargs["kh_er_message"])


if __name__ == "__main__":
    unittest.main()