import unittest
from unittest import mock

import fakes
import kh_detail

STUBS = [("/login", "login.login")]
KH = {"id": 3, "user_id": 10, "title": "コツ", "detail": "d", "username": "u"}
COMMENTS = [{"id": 1, "user_id": 2, "comment": "ありがとう", "username": "a"}]


class KhDetailTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(
            kh_detail, kh_detail.kh_detail_bp, STUBS)
        self.addCleanup(self.patcher.stop)

    def use_db(self, ones, alls):
        fake = fakes.FakeDB(ones=ones, alls=alls)
        p = mock.patch.object(kh_detail.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_requires_login(self):
        res = self.client.get("/knowhow/3")
        self.assertTrue(res.headers["Location"].endswith("/login"))

    def test_shows_knowhow_and_comments(self):
        fake = self.use_db([KH], [COMMENTS])
        fakes.login_as(self.client, user_id=1)
        self.client.get("/knowhow/3")
        name, ctx = self.rendered[0]
        self.assertEqual(name, kh_detail.USER_TEMPLATE)
        self.assertEqual(ctx["knowhow"], KH)
        self.assertEqual(ctx["comment_list"], COMMENTS)
        self.assertEqual(fake.executed[1][1], (kh_detail.POST_TYPE_KNOWHOW, 3))

    def test_no_comment_message(self):
        self.use_db([KH], [[]])
        fakes.login_as(self.client, user_id=1)
        self.client.get("/knowhow/3")
        self.assertEqual(self.rendered[0][1]["comment_message"], kh_detail.MSG_NO_COMMENT)

    def test_not_found(self):
        self.use_db([None], [])
        fakes.login_as(self.client, user_id=1)
        res = self.client.get("/knowhow/999")
        self.assertEqual(res.status_code, 404)
        ctx = self.rendered[0][1]
        self.assertEqual(ctx["message"], "ノウハウが存在しません。")
        self.assertEqual(ctx["code"], kh_detail.ERROR_KH_NOT_FOUND)

    def test_poster_and_admin_templates(self):
        self.use_db([KH], [[]])
        fakes.login_as(self.client, user_id=10)
        self.client.get("/knowhow/3")
        self.assertEqual(self.rendered[0][0], kh_detail.ORGANIZER_TEMPLATE)

        self.use_db([KH], [[]])
        fakes.login_as(self.client, user_id=99, admin=True)
        self.client.get("/knowhow/3")
        self.assertEqual(self.rendered[1][0], kh_detail.ADMIN_TEMPLATE)


if __name__ == "__main__":
    unittest.main()