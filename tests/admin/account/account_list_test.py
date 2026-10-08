"""account_list.py の単体テスト (M-FL3, M-FL4)"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeConnection, load_module  # noqa: E402

account_list = load_module("admin/account/account_list.py", "account_list")

ROWS = [
    {"id": 3, "username": "charlie", "imagepath": None, "admin_flg": 0},
    {"id": 1, "username": "alice", "imagepath": "a.png", "admin_flg": 1},
]


class GetAllAccountsTest(unittest.TestCase):
    def test_returns_rows_from_db(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        self.assertEqual(account_list.get_all_accounts(conn), ROWS)

    def test_sql_is_id_descending(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        account_list.get_all_accounts(conn)
        self.assertIn("ORDER BY id DESC", conn.sqls()[0])

    def test_passhash_is_not_selected(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        account_list.get_all_accounts(conn)
        self.assertNotIn("passhash", conn.sqls()[0])

    def test_empty_table_returns_empty_list(self):
        conn = FakeConnection(lambda sql, p: {"rows": []})
        self.assertEqual(account_list.get_all_accounts(conn), [])

    def test_passed_connection_is_not_closed(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        account_list.get_all_accounts(conn)
        self.assertFalse(conn.closed)

    def test_own_connection_is_closed(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        original = account_list._open_connection
        account_list._open_connection = lambda: conn
        try:
            account_list.get_all_accounts()
        finally:
            account_list._open_connection = original
        self.assertTrue(conn.closed)


class AccountListContextTest(unittest.TestCase):
    def test_with_accounts_has_no_message(self):
        conn = FakeConnection(lambda sql, p: {"rows": ROWS})
        ctx = account_list.get_account_list_context(conn)
        self.assertEqual(ctx["accounts"], ROWS)
        self.assertIsNone(ctx["display_msg"])

    def test_without_accounts_has_message(self):
        conn = FakeConnection(lambda sql, p: {"rows": []})
        ctx = account_list.get_account_list_context(conn)
        self.assertEqual(ctx["accounts"], [])
        self.assertEqual(ctx["display_msg"], account_list.NO_ACCOUNT_MESSAGE)


if __name__ == "__main__":
    unittest.main()