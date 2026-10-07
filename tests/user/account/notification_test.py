import unittest
from unittest.mock import patch

import fake_db
from fake_db import FakeConnection

from y_coco.db import POST_TYPE_EVENT
from y_coco.user.account import notification


class NotifyCommentTest(unittest.TestCase):
    def test_他人のコメントなら通知を登録してコミット(self):
        conn = FakeConnection()
        code, msg = notification.notify_comment(1, 2, 10, POST_TYPE_EVENT, db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])
        (_, params), = conn.sqls("INSERT INTO notification")
        # (senduser_id=コメントした人, receiver_id=投稿者, post_type, post_id)
        self.assertEqual(params, (2, 1, POST_TYPE_EVENT, 10))

    def test_未読状態で登録される(self):
        conn = FakeConnection()
        notification.notify_comment(1, 2, 10, POST_TYPE_EVENT, db_conn=conn)
        sql, _ = conn.sqls("INSERT INTO notification")[0]
        self.assertIn("read_flg", sql)
        self.assertTrue(sql.rstrip().endswith("0)"))

    def test_自分の投稿への自分のコメントはスキップ(self):
        conn = FakeConnection()
        code, msg = notification.notify_comment(1, 1, 10, POST_TYPE_EVENT, db_conn=conn)
        self.assertEqual((code, msg), (2, None))
        self.assertEqual(conn.events, [])
        self.assertEqual(conn.executed, [])

    def test_スキップ時はDB接続も作らない(self):
        with patch("y_coco.db.get_connection") as get_conn:
            notification.notify_comment(1, 1, 10, POST_TYPE_EVENT)
        get_conn.assert_not_called()

    def test_IDの型が違っても同一人物として判定する(self):
        conn = FakeConnection()
        code, _ = notification.notify_comment(1, "1", 10, POST_TYPE_EVENT, db_conn=conn)
        self.assertEqual(code, 2)

    def test_登録に失敗したらロールバックしてcode1(self):
        conn = FakeConnection(rules=[("INSERT INTO notification", {"rowcount": 0})])
        code, msg = notification.notify_comment(1, 2, 10, POST_TYPE_EVENT, db_conn=conn)
        self.assertEqual((code, msg), (1, notification.MSG_NOTIFY_FAILED))
        self.assertEqual(conn.events, ["begin", "rollback"])

    def test_DB例外ならロールバックしてcode1(self):
        conn = FakeConnection(rules=[("INSERT INTO notification", RuntimeError("boom"))])
        code, _ = notification.notify_comment(1, 2, 10, POST_TYPE_EVENT, db_conn=conn)
        self.assertEqual(code, 1)
        self.assertIn("rollback", conn.events)
        self.assertNotIn("commit", conn.events)


if __name__ == "__main__":
    unittest.main()