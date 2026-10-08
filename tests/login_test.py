import unittest
from unittest import mock

from werkzeug.security import generate_password_hash

import fakes
import y_coco.login as login

STUBS = [("/events", "event_list.index")]


def user_row(uid=1, admin=0):
    return {"id": uid, "username": "taro", "passhash": generate_password_hash("password1"),
            "imagepath": "a.png", "admin_flg": admin}


class LoginTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(login, login.login_bp, STUBS)
        self.addCleanup(self.patcher.stop)

    def use_db(self, ones):
        fake = fakes.FakeDB(ones=ones)
        p = mock.patch.object(login.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_get_shows_login_page(self):
        self.client.get("/login")
        self.assertEqual(self.rendered[0][0], "login.html")
        self.assertFalse(self.rendered[0][1]["login_flg"])

    def test_get_when_logged_in_sets_login_flg(self):
        fakes.login_as(self.client)
        self.client.get("/login")
        self.assertTrue(self.rendered[0][1]["login_flg"])

    def test_empty_input_is_error(self):
        self.client.post("/login", data={"username": "", "password": ""})
        self.assertIn(login.MSG_EMPTY, fakes.flashes(self.client))

    def test_unknown_account_is_error(self):
        self.use_db([None])
        self.client.post("/login", data={"username": "taro", "password": "password1"})
        self.assertEqual(fakes.flashes(self.client), [login.MSG_INVALID])

    def test_wrong_password_uses_same_message(self):
        self.use_db([user_row()])
        self.client.post("/login", data={"username": "taro", "password": "wrongpass1"})
        self.assertEqual(fakes.flashes(self.client), [login.MSG_INVALID])
        with self.client.session_transaction() as s:
            self.assertNotIn("user", s)

    def test_success_stores_session_and_redirects(self):
        self.use_db([user_row(uid=7, admin=0)])
        res = self.client.post("/login", data={"username": "taro", "password": "password1"})
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/events"))
        with self.client.session_transaction() as s:
            self.assertEqual(s["user"], {"id": 7, "imagepath": "a.png", "admin_flg": False})

    def test_admin_flag_stored(self):
        self.use_db([user_row(uid=2, admin=1)])
        self.client.post("/login", data={"username": "taro", "password": "password1"})
        with self.client.session_transaction() as s:
            self.assertTrue(s["user"]["admin_flg"])

    def test_same_account_while_logged_in_skips(self):
        fakes.login_as(self.client, user_id=7)
        self.use_db([user_row(uid=7)])
        res = self.client.post("/login", data={"username": "taro", "password": "x"})
        self.assertEqual(res.status_code, 302)

    def test_other_account_while_logged_in_is_error(self):
        fakes.login_as(self.client, user_id=1)
        self.use_db([user_row(uid=7)])
        self.client.post("/login", data={"username": "taro", "password": "password1"})
        self.assertEqual(fakes.flashes(self.client), [login.MSG_OTHER_ACCOUNT])
        with self.client.session_transaction() as s:
            self.assertEqual(s["user"]["id"], 1)

    def test_overlong_input_rejected_without_db(self):
        fake = self.use_db([])
        self.client.post("/login", data={"username": "a" * 11, "password": "password1"})
        self.assertEqual(fake.executed, [])
        self.assertEqual(fakes.flashes(self.client), [login.MSG_INVALID])


if __name__ == "__main__":
    unittest.main()