import unittest
from unittest import mock

import fakes
import kh_search

STUBS = [("/login", "login.login")]


class KhSearchTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(
            kh_search, kh_search.kh_search_bp, STUBS)
        self.addCleanup(self.patcher.stop)
        t = mock.patch.object(kh_search, "_get_tokenizer", return_value=None)
        t.start()
        self.addCleanup(t.stop)

    def use_db(self, rows):
        fake = fakes.FakeDB(alls=[rows])
        p = mock.patch.object(kh_search.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_split_words_fallback(self):
        self.assertEqual(kh_search.split_words("畑 土づくり 畑"), ["畑", "土づくり"])
        self.assertEqual(kh_search.split_words(""), [])

    def test_escape_like(self):
        self.assertEqual(kh_search.escape_like("a%b_c"), "a\\%b\\_c")

    def test_requires_login(self):
        res = self.client.get("/knowhow/search?q=a")
        self.assertTrue(res.headers["Location"].endswith("/login"))

    def test_blank_query_shows_form_only(self):
        fake = self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/knowhow/search")
        self.assertFalse(self.rendered[0][1]["searched"])
        self.assertEqual(fake.executed, [])

    def test_or_search_with_results(self):
        fake = self.use_db([{"id": 1, "detail": "x" * 60}])
        fakes.login_as(self.client)
        self.client.get("/knowhow/search?q=畑 土")
        sql, params = fake.executed[0]
        self.assertEqual(sql.count("LIKE"), 4)
        self.assertEqual(params, ["%畑%", "%畑%", "%土%", "%土%"])
        ctx = self.rendered[0][1]
        self.assertEqual(ctx["error_code"], 0)
        self.assertEqual(ctx["query"], "畑 土")
        self.assertEqual(ctx["results"][0]["summary"], "x" * 50 + "...")
        self.assertEqual(fakes.flashes(self.client), [])

    def test_no_result_sets_error_code_and_clears_input(self):
        self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/knowhow/search?q=zzz")
        ctx = self.rendered[0][1]
        self.assertEqual(ctx["error_code"], kh_search.ERROR_NO_RESULT)
        self.assertEqual(ctx["query"], "")
        self.assertEqual(ctx["results"], [])
        self.assertEqual(fakes.flashes(self.client), [kh_search.MSG_NO_RESULT])

    def test_admin_template(self):
        self.use_db([{"id": 1, "detail": "d"}])
        fakes.login_as(self.client, admin=True)
        self.client.get("/knowhow/search?q=a")
        self.assertEqual(self.rendered[0][0], kh_search.ADMIN_TEMPLATE)


if __name__ == "__main__":
    unittest.main()