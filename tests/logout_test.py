import unittest

import fakes
import logout

STUBS = [("/login", "login.login")]


class LogoutTest(unittest.TestCase):
    def setUp(self):
        self.client, _, self.patcher = fakes.make_client(logout, logout.logout_bp, STUBS)
        self.addCleanup(self.patcher.stop)

    def test_logged_in_destroys_session_and_redirects(self):
        fakes.login_as(self.client)
        res = self.client.get("/logout")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/login"))
        with self.client.session_transaction() as s:
            self.assertNotIn("user", s)

    def test_post_also_works(self):
        fakes.login_as(self.client)
        self.client.post("/logout")
        with self.client.session_transaction() as s:
            self.assertNotIn("user", s)

    def test_not_logged_in_returns_error(self):
        res = self.client.get("/logout")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(fakes.flashes(self.client), [logout.MSG_NOT_LOGGED_IN])

    def test_logout_user_codes(self):
        with self.client.application.test_request_context():
            self.assertEqual(logout.logout_user(), logout.CODE_NOT_LOGGED_IN)


if __name__ == "__main__":
    unittest.main() 