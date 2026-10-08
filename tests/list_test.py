import unittest
from unittest import mock

import fakes
import list as event_list

STUBS = [("/login", "login.login")]


def row(i, desc="本文"):
    return {"id": i, "user_id": 1, "title": f"t{i}", "description": desc,
            "imagepath": None, "datetime": None, "username": "u", "usericon": None}


class TruncateTest(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(event_list.truncate_text("a" * 50), "a" * 50)

    def test_long_text_gets_ellipsis(self):
        self.assertEqual(event_list.truncate_text("a" * 51), "a" * 50 + "...")

    def test_none_is_empty(self):
        self.assertEqual(event_list.truncate_text(None), "")


class EventListTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(
            event_list, event_list.list_bp, STUBS)
        self.addCleanup(self.patcher.stop)

    def use_db(self, rows):
        fake = fakes.FakeDB(alls=[rows])
        p = mock.patch.object(event_list.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_requires_login(self):
        res = self.client.get("/events")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/login"))

    def test_sorted_desc_with_summary(self):
        self.use_db([row(1), row(3, "x" * 60), row(2)])
        fakes.login_as(self.client)
        self.client.get("/events")
        name, ctx = self.rendered[0]
        self.assertEqual(name, event_list.USER_TEMPLATE)
        self.assertEqual([e["id"] for e in ctx["events"]], [3, 2, 1])
        self.assertEqual(ctx["events"][0]["summary"], "x" * 50 + "...")
        self.assertTrue(ctx["result"])
        self.assertIsNone(ctx["message"])

    def test_empty_returns_false(self):
        self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/events")
        ctx = self.rendered[0][1]
        self.assertFalse(ctx["result"])
        self.assertEqual(ctx["message"], event_list.MSG_EMPTY)

    def test_admin_gets_admin_template(self):
        self.use_db([row(1)])
        fakes.login_as(self.client, admin=True)
        self.client.get("/events")
        self.assertEqual(self.rendered[0][0], event_list.ADMIN_TEMPLATE)

    def test_connection_closed(self):
        fake = self.use_db([row(1)])
        fakes.login_as(self.client)
        self.client.get("/events")
        fake.connections[0].close.assert_called_once()


if __name__ == "__main__":
    unittest.main()