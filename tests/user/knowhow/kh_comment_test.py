"""user/knowhow/kh-comment.py の単体テスト

実行 (y-coco ディレクトリで):
    python -m unittest tests.test_kh_comment -v
    python -m pytest tests/test_kh_comment.py
"""
import os
import sys
import unittest
from unittest import mock

from flask import Flask

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeConnection, FakeForm, load_module  # noqa: E402

mod = load_module("user/knowhow/kh-comment.py", "y_coco_kh_comment", ["CommentForm"])

COMMENT = "参考になりました、ありがとうございます"


class SaveCommentTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.received = []

        def receiver(sender, **kwargs):
            self.received.append(kwargs)

        self._receiver = receiver  # blinker は弱参照なので保持しておく
        mod.comment_posted.connect(self._receiver)
        self.addCleanup(mod.comment_posted.disconnect, self._receiver)

    def run_save(self, conn, user_id=2, post_id=5, text=COMMENT):
        with self.app.app_context(), mock.patch.object(
            mod, "get_connection", return_value=conn
        ):
            return mod.save_comment(user_id, post_id, text)

    def test_success_commits_and_returns_comment_id(self):
        conn = FakeConnection(select_rows=[(1,)], lastrowid=33)
        code, comment_id = self.run_save(conn)

        self.assertEqual((code, comment_id), (0, 33))
        self.assertEqual(conn.calls, ["begin", "commit", "close"])

    def test_post_owner_is_looked_up_in_knowhow_table(self):
        conn = FakeConnection(select_rows=[(1,)])
        self.run_save(conn)

        (sql, params), = conn.statements("SELECT")
        self.assertIn("FROM knowhow", sql)
        self.assertEqual(params, (5,))

    def test_insert_uses_knowhow_post_type(self):
        conn = FakeConnection(select_rows=[(1,)])
        self.run_save(conn, user_id=2, post_id=5)

        (_, params), = conn.statements("INSERT")
        self.assertEqual(params, (2, mod.POST_TYPE_KNOWHOW, 5, COMMENT))

    def test_post_type_differs_from_event(self):
        self.assertEqual(mod.POST_TYPE_KNOWHOW, 2)

    def test_success_sends_notification_event_to_post_owner(self):
        conn = FakeConnection(select_rows=[(1,)], lastrowid=33)
        self.run_save(conn, user_id=2, post_id=5)

        self.assertEqual(
            self.received,
            [
                {
                    "sender_id": 2,
                    "receiver_id": 1,
                    "post_type": mod.POST_TYPE_KNOWHOW,
                    "post_id": 5,
                    "comment_id": 33,
                }
            ],
        )

    def test_receiver_error_does_not_fail_the_comment(self):
        def broken(sender, **kwargs):
            raise RuntimeError("notification down")

        self._broken = broken
        mod.comment_posted.connect(self._broken)
        self.addCleanup(mod.comment_posted.disconnect, self._broken)

        conn = FakeConnection(select_rows=[(1,)], lastrowid=33)
        code, comment_id = self.run_save(conn)

        self.assertEqual((code, comment_id), (0, 33))

    def test_missing_post_rolls_back_with_code_6(self):
        conn = FakeConnection(select_rows=[None])
        code, comment_id = self.run_save(conn)

        self.assertEqual((code, comment_id), (6, None))
        self.assertEqual(conn.calls, ["begin", "rollback", "close"])
        self.assertEqual(conn.statements("INSERT"), [])
        self.assertEqual(self.received, [])

    def test_insert_affecting_no_row_rolls_back_with_code_6(self):
        conn = FakeConnection(select_rows=[(1,)], insert_rowcount=0)
        code, _ = self.run_save(conn)

        self.assertEqual(code, 6)
        self.assertIn("rollback", conn.calls)
        self.assertNotIn("commit", conn.calls)
        self.assertEqual(self.received, [])

    def test_insert_error_rolls_back_with_code_6(self):
        conn = FakeConnection(select_rows=[(1,)], insert_error=RuntimeError("db down"))
        code, _ = self.run_save(conn)

        self.assertEqual(code, 6)
        self.assertIn("rollback", conn.calls)
        self.assertEqual(conn.calls[-1], "close")
        self.assertEqual(self.received, [])

    def test_commit_error_returns_code_6_without_notification(self):
        conn = FakeConnection(select_rows=[(1,)], commit_error=RuntimeError("boom"))
        code, _ = self.run_save(conn)

        self.assertEqual(code, 6)
        self.assertEqual(self.received, [])


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        self.app.register_blueprint(mod.knowhow_comment_bp)
        self.client = self.app.test_client()
        self.addCleanup(mock.patch.stopall)

    def login(self, user_id=2):
        with self.client.session_transaction() as sess:
            sess["user"] = user_id

    def use_form(self, valid=True, errors=None):
        mock.patch.object(
            mod, "CommentForm", return_value=FakeForm(valid=valid, errors=errors)
        ).start()

    def use_db(self, conn):
        mock.patch.object(mod, "get_connection", return_value=conn).start()
        return conn

    def test_not_logged_in_redirects_to_login(self):
        resp = self.client.post("/knowhow/5/comment", data={"comment": COMMENT})

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/login"))

    def test_validation_error_shows_message_and_back_button(self):
        self.login()
        self.use_form(valid=False, errors={"comment": ["コメントは5文字以上です"]})
        get_conn = mock.patch.object(mod, "get_connection").start()

        resp = self.client.post("/knowhow/5/comment", data={"comment": "短い"})
        body = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 400)
        self.assertIn("コメントは5文字以上です", body)
        self.assertIn('href="/knowhow/5"', body)
        get_conn.assert_not_called()

    def test_success_redirects_back_to_detail(self):
        self.login()
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(1,)], lastrowid=33))

        resp = self.client.post("/knowhow/5/comment", data={"comment": COMMENT})

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/knowhow/5"))
        self.assertIn("commit", conn.calls)

    def test_user_id_comes_from_session_not_from_form(self):
        self.login(user_id=7)
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(1,)]))

        self.client.post(
            "/knowhow/5/comment", data={"comment": COMMENT, "user_id": "999"}
        )

        (_, params), = conn.statements("INSERT")
        self.assertEqual(params[0], 7)

    def test_save_failure_shows_error_and_back_button(self):
        self.login()
        self.use_form()
        self.use_db(FakeConnection(select_rows=[None]))

        resp = self.client.post("/knowhow/5/comment", data={"comment": COMMENT})
        body = resp.get_data(as_text=True)

        self.assertEqual(resp.status_code, 500)
        self.assertIn("コメントの保存に失敗しました", body)
        self.assertIn('href="/knowhow/5"', body)


if __name__ == "__main__":
    unittest.main()