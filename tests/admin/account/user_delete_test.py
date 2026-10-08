"""user_delete.py の単体テスト (M-FL1, M-FL2)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeConnection, load_module  # noqa: E402

user_delete = load_module("admin/account/user_delete.py", "user_delete")


def make_responder(target=None, users_rowcount=1, fail_on=None):
    """target: SELECTで返すユーザー行(None なら存在しない)
    users_rowcount: DELETE FROM users の影響件数
    fail_on: このSQLで始まる文を実行したら例外を投げる
    """
    def responder(sql, params):
        if fail_on and sql.startswith(fail_on):
            raise RuntimeError("DB error")
        if sql.startswith("SELECT id, admin_flg FROM users"):
            return {"rows": [target] if target else []}
        if sql.startswith("DELETE FROM users"):
            return {"rowcount": users_rowcount}
        return {"rowcount": 2}
    return responder


NORMAL_USER = {"id": 5, "admin_flg": 0}
ADMIN_USER = {"id": 1, "admin_flg": 1}


class DeleteUserSuccessTest(unittest.TestCase):
    def test_commits_and_returns_code_0(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        result = user_delete.delete_user(5, conn)
        self.assertEqual(result["code"], 0)
        self.assertEqual(conn.events, ["commit"])

    def test_user_row_is_deleted_last(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        user_delete.delete_user(5, conn)
        deletes = [s for s in conn.sqls() if s.startswith("DELETE")]
        self.assertTrue(deletes[-1].startswith("DELETE FROM users"))

    def test_related_data_is_deleted_before_user(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        user_delete.delete_user(5, conn)
        sqls = conn.sqls()
        for table in ("comment", "notification", "event_post", "knowhow"):
            self.assertTrue(
                any(s.startswith("DELETE FROM " + table) for s in sqls),
                table + " の削除が実行されていない",
            )

    def test_string_id_is_accepted(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        self.assertEqual(user_delete.delete_user("5", conn)["code"], 0)

    def test_passed_connection_is_not_closed(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        user_delete.delete_user(5, conn)
        self.assertFalse(conn.closed)


class DeleteUserFailureTest(unittest.TestCase):
    def assert_failed_with_rollback(self, conn, result):
        self.assertEqual(result["code"], 7)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_user_not_found(self):
        conn = FakeConnection(make_responder(target=None))
        result = user_delete.delete_user(999, conn)
        self.assert_failed_with_rollback(conn, result)
        self.assertEqual(conn.executed_starting_with("DELETE"), [])

    def test_admin_account_cannot_be_deleted(self):
        conn = FakeConnection(make_responder(ADMIN_USER))
        result = user_delete.delete_user(1, conn)
        self.assert_failed_with_rollback(conn, result)
        self.assertEqual(conn.executed_starting_with("DELETE"), [])

    def test_user_delete_affects_no_rows(self):
        conn = FakeConnection(make_responder(NORMAL_USER, users_rowcount=0))
        result = user_delete.delete_user(5, conn)
        self.assert_failed_with_rollback(conn, result)

    def test_exception_in_related_delete(self):
        conn = FakeConnection(make_responder(NORMAL_USER, fail_on="DELETE FROM knowhow"))
        result = user_delete.delete_user(5, conn)
        self.assert_failed_with_rollback(conn, result)

    def test_exception_in_user_delete(self):
        conn = FakeConnection(make_responder(NORMAL_USER, fail_on="DELETE FROM users"))
        result = user_delete.delete_user(5, conn)
        self.assert_failed_with_rollback(conn, result)

    def test_invalid_id_does_not_touch_db(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        for bad in (None, "", "abc"):
            self.assertEqual(user_delete.delete_user(bad, conn)["code"], 7)
        self.assertEqual(conn.executed, [])

    def test_failure_message_is_set(self):
        conn = FakeConnection(make_responder(target=None))
        result = user_delete.delete_user(999, conn)
        self.assertEqual(result["message"], user_delete.MSG_FAILURE)


class ForceLogoutTest(unittest.TestCase):
    def test_session_cleared_when_deleted_user_is_logged_in(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        session = {"user": {"id": 5, "imagepath": None, "admin_flg": 0}}
        result = user_delete.delete_user(5, conn, session_obj=session)
        self.assertTrue(result["is_logged_out"])
        self.assertEqual(session, {})

    def test_session_kept_when_other_user_deleted(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        session = {"user": {"id": 1, "imagepath": None, "admin_flg": 1}}
        result = user_delete.delete_user(5, conn, session_obj=session)
        self.assertFalse(result["is_logged_out"])
        self.assertIn("user", session)

    def test_session_kept_when_delete_fails(self):
        conn = FakeConnection(make_responder(NORMAL_USER, users_rowcount=0))
        session = {"user": {"id": 5}}
        result = user_delete.delete_user(5, conn, session_obj=session)
        self.assertFalse(result["is_logged_out"])
        self.assertIn("user", session)

    def test_no_session_object(self):
        conn = FakeConnection(make_responder(NORMAL_USER))
        self.assertFalse(user_delete.delete_user(5, conn)["is_logged_out"])


if __name__ == "__main__":
    unittest.main()