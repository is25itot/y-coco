import unittest
from unittest import mock

import fakes  # noqa: F401  (sys.path / db スタブの準備。先に import する)
import detail

STUBS = [("/login", "login.login")]
EVENT = {"id": 5, "user_id": 10, "title": "祭り", "description": "d", "username": "u"}
COMMENTS = [{"id": 1, "user_id": 2, "comment": "いいね", "username": "a"}]


class EventDetailTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(
            detail, detail.detail_bp, STUBS)
        self.addCleanup(self.patcher.stop)

    def use_db(self, ones, alls):
        fake = fakes.FakeDB(ones=ones, alls=alls)
        p = mock.patch.object(detail.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_requires_login(self):
        res = self.client.get("/events/5")
        self.assertTrue(res.headers["Location"].endswith("/login"))

    def test_shows_event_and_comments(self):
        fake = self.use_db([EVENT], [COMMENTS])
        fakes.login_as(self.client, user_id=1)
        res = self.client.get("/events/5")
        self.assertEqual(res.status_code, 200)
        name, ctx = self.rendered[0]
        self.assertEqual(name, detail.USER_TEMPLATE)
        self.assertEqual(ctx["event"], EVENT)
        self.assertEqual(ctx["comment_list"], COMMENTS)
        self.assertIsNone(ctx["comment_message"])
        # コメント検索は post_type=イベント と event_id で行う
        self.assertEqual(fake.executed[1][1], (detail.POST_TYPE_EVENT, 5))

    def test_no_comment_message(self):
        self.use_db([EVENT], [[]])
        fakes.login_as(self.client, user_id=1)
        self.client.get("/events/5")
        ctx = self.rendered[0][1]
        self.assertEqual(ctx["comment_list"], [])
        self.assertEqual(ctx["comment_message"], detail.MSG_NO_COMMENT)

    def test_not_found(self):
        fake = self.use_db([None], [])
        fakes.login_as(self.client, user_id=1)
        res = self.client.get("/events/999")
        self.assertEqual(res.status_code, 404)
        ctx = self.rendered[0][1]
        self.assertIsNone(ctx["event"])
        self.assertEqual(ctx["message"], detail.MSG_NOT_FOUND)
        self.assertEqual(ctx["code"], detail.ERROR_EVENT_NOT_FOUND)
        self.assertEqual(len(fake.executed), 1)  # コメントは検索しない

    def test_organizer_template(self):
        self.use_db([EVENT], [[]])
        fakes.login_as(self.client, user_id=10)
        self.client.get("/events/5")
        self.assertEqual(self.rendered[0][0], detail.ORGANIZER_TEMPLATE)

    def test_admin_template(self):
        self.use_db([EVENT], [[]])
        fakes.login_as(self.client, user_id=99, admin=True)
        self.client.get("/events/5")
        self.assertEqual(self.rendered[0][0], detail.ADMIN_TEMPLATE)

    def test_non_integer_id_is_404(self):
        fakes.login_as(self.client)
        self.assertEqual(self.client.get("/events/abc").status_code, 404)


if __name__ == "__main__":
    unittest.main()