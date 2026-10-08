import unittest
from unittest import mock

import fakes
import search

STUBS = [("/login", "login.login")]


class FakeToken:
    def __init__(self, surface, pos):
        self.surface = surface
        self.part_of_speech = pos + ",*,*,*"


class FakeTokenizer:
    def tokenize(self, text):
        return [FakeToken("祭り", "名詞"), FakeToken("の", "助詞"),
                FakeToken("準備", "名詞"), FakeToken("祭り", "名詞"), FakeToken("。", "記号")]


class SplitWordsTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(search.split_words(""), [])
        self.assertEqual(search.split_words("   "), [])
        self.assertEqual(search.split_words(None), [])

    def test_morphological_filters_particles_and_dedupes(self):
        with mock.patch.object(search, "_get_tokenizer", return_value=FakeTokenizer()):
            self.assertEqual(search.split_words("祭りの準備。祭り"), ["祭り", "準備"])

    def test_fallback_splits_on_spaces(self):
        with mock.patch.object(search, "_get_tokenizer", return_value=None):
            self.assertEqual(search.split_words("夏祭り\u3000花火 夏祭り"), ["夏祭り", "花火"])

    def test_only_particles_falls_back_to_whole_text(self):
        class OnlyParticles:
            def tokenize(self, text):
                return [FakeToken("の", "助詞")]
        with mock.patch.object(search, "_get_tokenizer", return_value=OnlyParticles()):
            self.assertEqual(search.split_words("の"), ["の"])


class EscapeLikeTest(unittest.TestCase):
    def test_escapes_wildcards(self):
        self.assertEqual(search.escape_like("100%_a\\"), "100\\%\\_a\\\\")


class SearchRouteTest(unittest.TestCase):
    def setUp(self):
        self.client, self.rendered, self.patcher = fakes.make_client(
            search, search.search_bp, STUBS)
        self.addCleanup(self.patcher.stop)
        t = mock.patch.object(search, "_get_tokenizer", return_value=None)
        t.start()
        self.addCleanup(t.stop)

    def use_db(self, rows):
        fake = fakes.FakeDB(alls=[rows])
        p = mock.patch.object(search.db, "get_connection", fake.get_connection, create=True)
        p.start()
        self.addCleanup(p.stop)
        return fake

    def test_requires_login(self):
        res = self.client.get("/events/search?q=a")
        self.assertTrue(res.headers["Location"].endswith("/login"))

    def test_blank_query_shows_form_only(self):
        fake = self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/events/search")
        ctx = self.rendered[0][1]
        self.assertFalse(ctx["searched"])
        self.assertEqual(fake.executed, [])

    def test_or_search_builds_params(self):
        fake = self.use_db([{"id": 2, "description": "x" * 60}, {"id": 1, "description": "b"}])
        fakes.login_as(self.client)
        self.client.get("/events/search?q=夏 100%")
        sql, params = fake.executed[0]
        self.assertEqual(sql.count("LIKE"), 4)
        self.assertIn(" OR ", sql)
        self.assertEqual(params, ["%夏%", "%夏%", "%100\\%%", "%100\\%%"])
        ctx = self.rendered[0][1]
        self.assertTrue(ctx["has_result"])
        self.assertEqual(ctx["results"][0]["summary"], "x" * 50 + "...")
        self.assertIsNone(ctx["message"])

    def test_no_result_message(self):
        self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/events/search?q=zzz")
        ctx = self.rendered[0][1]
        self.assertFalse(ctx["has_result"])
        self.assertEqual(ctx["message"], search.MSG_NO_RESULT)

    def test_admin_template(self):
        self.use_db([])
        fakes.login_as(self.client, admin=True)
        self.client.get("/events/search?q=a")
        self.assertEqual(self.rendered[0][0], search.ADMIN_TEMPLATE)

    def test_query_length_capped(self):
        self.use_db([])
        fakes.login_as(self.client)
        self.client.get("/events/search?q=" + "a" * 500)
        self.assertEqual(len(self.rendered[0][1]["query"]), search.MAX_QUERY_LENGTH)


if __name__ == "__main__":
    unittest.main()