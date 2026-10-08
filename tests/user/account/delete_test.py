import unittest

import fake_db
from fake_db import FakeConnection

from y_coco.db import POST_TYPE_EVENT, POST_TYPE_KNOWHOW
from y_coco.user.account import delete


class DeletePostTest(unittest.TestCase):
    def test_イベント削除に成功するとコミットしてcode0(self):
        conn = FakeConnection(rules=[("DELETE FROM event_post", {"rowcount": 1})])
        code, msg = delete.delete_post(10, 5, delete.TARGET_EVENT, db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])

    def test_user_idも条件に含めて本人以外の削除を防ぐ(self):
        conn = FakeConnection()
        delete.delete_post(10, 5, delete.TARGET_EVENT, db_conn=conn)
        sql, params = conn.sqls("DELETE FROM event_post")[0]
        self.assertIn("user_id = %s", sql)
        self.assertEqual(params, (10, 5))

    def test_本人の投稿でなければロールバックしてcode3(self):
        conn = FakeConnection(rules=[("DELETE FROM event_post", {"rowcount": 0})])
        code, msg = delete.delete_post(10, 99, delete.TARGET_EVENT, db_conn=conn)
        self.assertEqual(code, 3)
        self.assertEqual(msg, delete.MSG_DELETE_FAILED)
        self.assertEqual(conn.events, ["begin", "rollback"])
        # 削除できなかったときは関連データも消さない
        self.assertEqual(conn.sqls("DELETE FROM `comment`"), [])
        self.assertEqual(conn.sqls("DELETE FROM notification"), [])

    def test_イベント削除時はコメントと通知も同じトランザクションで消す(self):
        conn = FakeConnection()
        delete.delete_post(10, 5, delete.TARGET_EVENT, db_conn=conn)
        self.assertEqual(conn.sqls("DELETE FROM `comment`")[0][1], (POST_TYPE_EVENT, 10))
        self.assertEqual(conn.sqls("DELETE FROM notification")[0][1], (POST_TYPE_EVENT, 10))
        self.assertEqual(conn.events, ["begin", "commit"])

    def test_ノウハウ削除はknowhowテーブルを対象にする(self):
        conn = FakeConnection()
        code, _ = delete.delete_post(3, 5, delete.TARGET_KNOWHOW, db_conn=conn)
        self.assertEqual(code, 0)
        self.assertEqual(len(conn.sqls("DELETE FROM knowhow")), 1)
        self.assertEqual(conn.sqls("DELETE FROM `comment`")[0][1], (POST_TYPE_KNOWHOW, 3))

    def test_コメント削除は関連データを消さない(self):
        conn = FakeConnection()
        code, _ = delete.delete_post(7, 5, delete.TARGET_COMMENT, db_conn=conn)
        self.assertEqual(code, 0)
        self.assertEqual(len(conn.executed), 1)
        self.assertIn("DELETE FROM `comment`", conn.executed[0][0])

    def test_不正な削除対象はDBに触れずcode3(self):
        conn = FakeConnection()
        code, _ = delete.delete_post(1, 5, "users; DROP TABLE users", db_conn=conn)
        self.assertEqual(code, 3)
        self.assertEqual(conn.events, [])
        self.assertEqual(conn.executed, [])

    def test_DB例外ならロールバックしてcode3(self):
        conn = FakeConnection(rules=[("DELETE FROM event_post", RuntimeError("boom"))])
        code, msg = delete.delete_post(10, 5, delete.TARGET_EVENT, db_conn=conn)
        self.assertEqual((code, msg), (3, delete.MSG_DELETE_FAILED))
        self.assertIn("rollback", conn.events)
        self.assertNotIn("commit", conn.events)


if __name__ == "__main__":
    unittest.main()