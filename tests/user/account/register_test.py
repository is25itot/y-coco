import unittest
from unittest.mock import patch

import fake_db
from fake_db import FakeConnection
from werkzeug.security import check_password_hash

from y_coco.user.account import register


class RegisterUserTest(unittest.TestCase):
    def test_成功するとコミットしてcode0(self):
        conn = FakeConnection(rules=[("SELECT id FROM users", {"rows": []})])
        code, msg = register.register_user("taro123", "password123", db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])

    def test_パスワードはハッシュ化して保存される(self):
        conn = FakeConnection()
        register.register_user("taro123", "password123", db_conn=conn)
        (_, params), = conn.sqls("INSERT INTO users")
        self.assertEqual(params[0], "taro123")
        self.assertNotEqual(params[1], "password123")
        self.assertTrue(check_password_hash(params[1], "password123"))

    def test_ユーザーネーム重複ならロールバックしてcode1(self):
        conn = FakeConnection(rules=[("SELECT id FROM users", {"rows": [{"id": 1}]})])
        code, msg = register.register_user("taro123", "password123", db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(msg, register.MSG_DUPLICATE)
        self.assertEqual(conn.events, ["begin", "rollback"])
        self.assertEqual(conn.sqls("INSERT INTO users"), [])

    def test_INSERTの件数が1でなければロールバックしてcode1(self):
        conn = FakeConnection(rules=[("INSERT INTO users", {"rowcount": 0})])
        code, msg = register.register_user("taro123", "password123", db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(msg, register.MSG_REGISTER_FAILED)
        self.assertEqual(conn.events, ["begin", "rollback"])

    def test_DB例外ならロールバックしてcode1(self):
        conn = FakeConnection(rules=[("INSERT INTO users", RuntimeError("boom"))])
        code, msg = register.register_user("taro123", "password123", db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(msg, register.MSG_REGISTER_FAILED)
        self.assertIn("rollback", conn.events)
        self.assertNotIn("commit", conn.events)

    def test_接続を内部で作った場合は閉じる(self):
        conn = FakeConnection()
        with patch("y_coco.db.get_connection", return_value=conn):
            code, _ = register.register_user("taro123", "password123")
        self.assertEqual(code, 0)
        self.assertTrue(conn.closed)

    def test_渡された接続は閉じない(self):
        conn = FakeConnection()
        register.register_user("taro123", "password123", db_conn=conn)
        self.assertFalse(conn.closed)

    def test_DBに接続できなければcode1(self):
        with patch("y_coco.db.get_connection", side_effect=RuntimeError("接続できない")):
            code, msg = register.register_user("taro123", "password123")
        self.assertEqual((code, msg), (1, register.MSG_REGISTER_FAILED))


if __name__ == "__main__":
    unittest.main()