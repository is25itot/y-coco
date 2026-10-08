"""admin-kh-delete.py の単体テスト (M-FL11)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeConnection, load_module  # noqa: E402

mod = load_module("admin/knowhow/admin-kh-delete.py", "admin_kh_delete")

FAIL = 9
POST_TYPE = 2


def make_responder(delete_rowcount=1, still_exists=False, fail_on=None):
    """delete_rowcount: 本体(knowhow/コメント)のDELETE影響件数
    still_exists: 削除後の存在確認SELECTで行を返すか
    fail_on: このSQLで始まる文を実行したら例外を投げる
    """
    def responder(sql, params):
        if fail_on and sql.startswith(fail_on):
            raise RuntimeError("DB error")
        if sql.startswith("SELECT"):
            return {"rows": [{"id": 1}] if still_exists else []}
        if sql.startswith("DELETE FROM knowhow ") or (
            sql.startswith("DELETE FROM comment WHERE id")
        ):
            return {"rowcount": delete_rowcount}
        return {"rowcount": 3}  # 紐づくコメント・通知の削除
    return responder


class DeleteKnowhowTest(unittest.TestCase):
    def test_success_commits_and_returns_code_0(self):
        conn = FakeConnection(make_responder())
        result = mod.delete_knowhow(10, conn)
        self.assertEqual(result["code"], 0)
        self.assertEqual(conn.events, ["commit"])

    def test_related_comments_and_notifications_are_deleted_first(self):
        conn = FakeConnection(make_responder())
        mod.delete_knowhow(10, conn)
        deletes = [s for s in conn.sqls() if s.startswith("DELETE")]
        self.assertTrue(deletes[0].startswith("DELETE FROM comment"))
        self.assertTrue(deletes[1].startswith("DELETE FROM notification"))
        self.assertTrue(deletes[2].startswith("DELETE FROM knowhow"))

    def test_related_delete_is_limited_to_this_post_type(self):
        conn = FakeConnection(make_responder())
        mod.delete_knowhow(10, conn)
        for sql, params in conn.executed_starting_with("DELETE FROM comment"):
            self.assertEqual(params, (POST_TYPE, 10))

    def test_still_exists_after_delete_rolls_back(self):
        conn = FakeConnection(make_responder(still_exists=True))
        result = mod.delete_knowhow(10, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_nothing_deleted_is_failure(self):
        conn = FakeConnection(make_responder(delete_rowcount=0))
        result = mod.delete_knowhow(999, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_exception_rolls_back(self):
        conn = FakeConnection(make_responder(fail_on="DELETE FROM knowhow "))
        result = mod.delete_knowhow(10, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_invalid_id_does_not_touch_db(self):
        conn = FakeConnection(make_responder())
        for bad in (None, "", "abc"):
            self.assertEqual(mod.delete_knowhow(bad, conn)["code"], FAIL)
        self.assertEqual(conn.executed, [])

    def test_string_id_is_accepted(self):
        conn = FakeConnection(make_responder())
        self.assertEqual(mod.delete_knowhow("10", conn)["code"], 0)

    def test_passed_connection_is_not_closed(self):
        conn = FakeConnection(make_responder())
        mod.delete_knowhow(10, conn)
        self.assertFalse(conn.closed)

    def test_own_connection_is_closed(self):
        conn = FakeConnection(make_responder())
        original = mod._open_connection
        mod._open_connection = lambda: conn
        try:
            mod.delete_knowhow(10)
        finally:
            mod._open_connection = original
        self.assertTrue(conn.closed)


class DeleteKnowhowCommentTest(unittest.TestCase):
    def test_success_commits_and_returns_code_0(self):
        conn = FakeConnection(make_responder())
        result = mod.delete_knowhow_comment(30, conn)
        self.assertEqual(result["code"], 0)
        self.assertEqual(conn.events, ["commit"])

    def test_only_the_comment_is_deleted(self):
        conn = FakeConnection(make_responder())
        mod.delete_knowhow_comment(30, conn)
        deletes = conn.executed_starting_with("DELETE")
        self.assertEqual(len(deletes), 1)
        sql, params = deletes[0]
        self.assertTrue(sql.startswith("DELETE FROM comment WHERE id"))
        self.assertEqual(params, (30, POST_TYPE))

    def test_other_post_type_comment_is_not_deleted(self):
        # post_type が違うコメントは0件削除になり、失敗扱いになる
        conn = FakeConnection(make_responder(delete_rowcount=0))
        result = mod.delete_knowhow_comment(30, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)

    def test_still_exists_rolls_back(self):
        conn = FakeConnection(make_responder(still_exists=True))
        result = mod.delete_knowhow_comment(30, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_exception_rolls_back(self):
        conn = FakeConnection(make_responder(fail_on="DELETE FROM comment"))
        result = mod.delete_knowhow_comment(30, conn)
        self.assertEqual(result["code"], FAIL)
        self.assertTrue(conn.rolled_back)

    def test_invalid_id_does_not_touch_db(self):
        conn = FakeConnection(make_responder())
        self.assertEqual(mod.delete_knowhow_comment("abc", conn)["code"], FAIL)
        self.assertEqual(conn.executed, [])


class DispatchTest(unittest.TestCase):
    def test_main_id_only_deletes_the_post(self):
        conn = FakeConnection(make_responder())
        result = mod.admin_kh_delete(knowhow_id=10, db_conn=conn)
        self.assertEqual(result["code"], 0)
        self.assertTrue(
            any(s.startswith("DELETE FROM knowhow ") for s in conn.sqls())
        )

    def test_comment_id_deletes_only_the_comment(self):
        conn = FakeConnection(make_responder())
        result = mod.admin_kh_delete(knowhow_id=10, comment_id=30, db_conn=conn)
        self.assertEqual(result["code"], 0)
        self.assertFalse(
            any(s.startswith("DELETE FROM knowhow ") for s in conn.sqls())
        )
        self.assertEqual(len(conn.executed_starting_with("DELETE")), 1)

    def test_comment_id_only(self):
        conn = FakeConnection(make_responder())
        self.assertEqual(mod.admin_kh_delete(comment_id=30, db_conn=conn)["code"], 0)

    def test_no_ids_is_failure(self):
        conn = FakeConnection(make_responder())
        result = mod.admin_kh_delete(db_conn=conn)
        self.assertEqual(result["code"], FAIL)
        self.assertEqual(conn.executed, [])


if __name__ == "__main__":
    unittest.main()