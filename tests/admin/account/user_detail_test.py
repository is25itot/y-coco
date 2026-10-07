"""user_detail.py の単体テスト (M-FL5, M-FL6)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeConnection, load_module  # noqa: E402

user_detail = load_module("admin/account/user_detail.py", "user_detail")

USER = {"id": 5, "username": "taro", "imagepath": "t.png", "admin_flg": 0}


def make_responder(user=USER):
    def responder(sql, params):
        if sql.startswith("SELECT id, username, imagepath, admin_flg FROM users"):
            return {"rows": [user] if user else []}
        if "FROM event_post" in sql:
            return {"rows": [{"id": 10, "title": "祭り", "created_at": None}]}
        if "FROM knowhow" in sql:
            return {"rows": [{"id": 20, "title": "畑仕事", "created_at": None}]}
        if "FROM comment" in sql:
            return {"rows": [{"id": 30, "post_type": 1, "post_id": 10,
                              "comment": "いいね", "created_at": None}]}
        return {}
    return responder


class GetUserDetailTest(unittest.TestCase):
    def test_returns_user_and_posts(self):
        conn = FakeConnection(make_responder())
        detail = user_detail.get_user_detail(5, conn)
        self.assertEqual(detail["user"], USER)
        self.assertEqual(detail["events"][0]["id"], 10)
        self.assertEqual(detail["knowhows"][0]["id"], 20)
        self.assertEqual(detail["comments"][0]["id"], 30)

    def test_string_id_is_accepted(self):
        conn = FakeConnection(make_responder())
        self.assertIsNotNone(user_detail.get_user_detail("5", conn))
        self.assertEqual(conn.executed[0][1], (5,))

    def test_invalid_id_returns_none_without_query(self):
        conn = FakeConnection(make_responder())
        for bad in (None, "", "abc"):
            self.assertIsNone(user_detail.get_user_detail(bad, conn))
        self.assertEqual(conn.executed, [])

    def test_unknown_user_returns_none(self):
        conn = FakeConnection(make_responder(user=None))
        self.assertIsNone(user_detail.get_user_detail(999, conn))
        self.assertEqual(len(conn.executed), 1)  # 投稿等は検索しない

    def test_passhash_is_never_selected(self):
        conn = FakeConnection(make_responder())
        user_detail.get_user_detail(5, conn)
        self.assertTrue(all("passhash" not in s for s in conn.sqls()))

    def test_only_select_statements_are_used(self):
        conn = FakeConnection(make_responder())
        user_detail.get_user_detail(5, conn)
        self.assertTrue(all(s.startswith("SELECT") for s in conn.sqls()))
        self.assertFalse(conn.committed or conn.rolled_back)


if __name__ == "__main__":
    unittest.main()