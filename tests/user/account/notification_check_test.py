import unittest
from datetime import datetime

import fake_db
from fake_db import FakeConnection

from y_coco.user.account import notification_check


class GetNotificationsTest(unittest.TestCase):
    def test_通知が無ければ通知無しメッセージ(self):
        conn = FakeConnection(rules=[("FROM notification n", {"rows": []})])
        self.assertEqual(notification_check.get_notifications(1, db_conn=conn), ([], "通知無し"))

    def test_通知があればそのまま返す(self):
        rows = [{"notification_id": 2, "sender_name": "hanako", "post_title": "お祭り",
                 "created_at": datetime(2026, 5, 2), "read_flg": 0}]
        conn = FakeConnection(rules=[("FROM notification n", {"rows": rows})])
        notification_list, msg = notification_check.get_notifications(1, db_conn=conn)
        self.assertIsNone(msg)
        self.assertEqual(notification_list, rows)

    def test_自分宛てだけを新しい順に取得するSQL(self):
        conn = FakeConnection(rules=[("FROM notification n", {"rows": []})])
        notification_check.get_notifications(7, db_conn=conn)
        sql, params = conn.executed[0]
        self.assertIn("WHERE n.receiver_id = %s", sql)
        self.assertIn("ORDER BY n.created_at DESC", sql)
        self.assertEqual(params, (7,))

    def test_DB例外なら空配列とエラーメッセージ(self):
        conn = FakeConnection(rules=[("FROM notification n", RuntimeError("boom"))])
        self.assertEqual(notification_check.get_notifications(1, db_conn=conn),
                         ([], notification_check.MSG_FETCH_FAILED))


class MarkAsReadTest(unittest.TestCase):
    def test_確認した通知を既読に更新してコミット(self):
        conn = FakeConnection()
        code, msg = notification_check.mark_as_read([3, 1, 2], 7, db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])
        sql, params = conn.sqls("UPDATE notification SET read_flg = 1")[0]
        self.assertIn("receiver_id = %s", sql)       # 他人宛ての通知は更新しない
        self.assertEqual(params, (7, 1, 2, 3))
        self.assertEqual(sql.count("%s"), 4)

    def test_重複したIDは1つにまとめる(self):
        conn = FakeConnection()
        notification_check.mark_as_read([1, 1, "1"], 7, db_conn=conn)
        self.assertEqual(conn.sqls("UPDATE")[0][1], (7, 1))

    def test_空のリストなら何もしない(self):
        conn = FakeConnection()
        self.assertEqual(notification_check.mark_as_read([], 7, db_conn=conn), (0, None))
        self.assertEqual(conn.events, [])

    def test_IDが数値でなければSQLを実行せずcode1(self):
        conn = FakeConnection()
        code, _ = notification_check.mark_as_read(["1; DROP TABLE users"], 7, db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(conn.executed, [])

    def test_DB例外ならロールバックしてcode1(self):
        conn = FakeConnection(rules=[("UPDATE notification", RuntimeError("boom"))])
        code, msg = notification_check.mark_as_read([1], 7, db_conn=conn)
        self.assertEqual((code, msg), (1, notification_check.MSG_READ_FAILED))
        self.assertIn("rollback", conn.events)


if __name__ == "__main__":
    unittest.main()