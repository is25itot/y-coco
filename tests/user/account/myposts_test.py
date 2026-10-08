import unittest
from datetime import datetime

import fake_db
from fake_db import FakeConnection

from y_coco.db import POST_TYPE_EVENT, POST_TYPE_KNOWHOW
from y_coco.user.account import myposts


def _rules(events=(), knowhows=(), comments=()):
    # コメント用SQLの中にも event_post / knowhow が出てくるので、先にコメントを判定する
    return [
        ("FROM `comment` c", {"rows": [dict(c) for c in comments]}),
        ("FROM event_post e", {"rows": [dict(e) for e in events]}),
        ("FROM knowhow k", {"rows": [dict(k) for k in knowhows]}),
    ]


class GetMyPostsTest(unittest.TestCase):
    def test_投稿が無ければ投稿なしメッセージ(self):
        conn = FakeConnection(rules=_rules())
        post_list, comment_list, msg = myposts.get_my_posts(1, db_conn=conn)
        self.assertEqual((post_list, comment_list, msg), ([], [], "投稿なし"))

    def test_イベントとノウハウを新しい順にまとめる(self):
        events = [
            {"post_id": 1, "post_type": POST_TYPE_EVENT, "title": "古いイベント", "body": "a",
             "created_at": datetime(2026, 1, 1), "username": "taro"},
            {"post_id": 2, "post_type": POST_TYPE_EVENT, "title": "新しいイベント", "body": "b",
             "created_at": datetime(2026, 3, 1), "username": "taro"},
        ]
        knowhows = [
            {"post_id": 1, "post_type": POST_TYPE_KNOWHOW, "title": "間のノウハウ", "body": "c",
             "created_at": datetime(2026, 2, 1), "username": "taro"},
        ]
        conn = FakeConnection(rules=_rules(events=events, knowhows=knowhows))
        post_list, _, msg = myposts.get_my_posts(1, db_conn=conn)
        self.assertIsNone(msg)
        self.assertEqual([p["title"] for p in post_list],
                         ["新しいイベント", "間のノウハウ", "古いイベント"])

    def test_本文は50文字を超えたら後ろに三点を付ける(self):
        events = [
            {"post_id": 1, "post_type": 1, "title": "t", "body": "あ" * 51,
             "created_at": datetime(2026, 1, 1), "username": "taro"},
            {"post_id": 2, "post_type": 1, "title": "t", "body": "い" * 50,
             "created_at": datetime(2026, 1, 2), "username": "taro"},
        ]
        conn = FakeConnection(rules=_rules(events=events))
        post_list, _, _ = myposts.get_my_posts(1, db_conn=conn)
        by_id = {p["post_id"]: p for p in post_list}
        self.assertEqual(by_id[1]["body_preview"], "あ" * 50 + "...")
        self.assertEqual(by_id[2]["body_preview"], "い" * 50)
        self.assertEqual(by_id[1]["body"], "あ" * 51)   # 元の本文は変えない

    def test_自分の投稿に付いたコメントも返す(self):
        comments = [{"comment_id": 9, "user_id": 2, "username": "hanako", "post_type": 1,
                     "post_id": 1, "comment": "いいですね", "created_at": datetime(2026, 1, 3)}]
        events = [{"post_id": 1, "post_type": 1, "title": "t", "body": "b",
                   "created_at": datetime(2026, 1, 1), "username": "taro"}]
        conn = FakeConnection(rules=_rules(events=events, comments=comments))
        _, comment_list, _ = myposts.get_my_posts(1, db_conn=conn)
        self.assertEqual(comment_list[0]["comment"], "いいですね")

    def test_SQLにはユーザーIDを渡して他人の投稿を取らない(self):
        conn = FakeConnection(rules=_rules())
        myposts.get_my_posts(42, db_conn=conn)
        for _, params in conn.executed:
            self.assertIn(42, params)

    def test_DB例外なら空配列とエラーメッセージ(self):
        conn = FakeConnection(rules=[("FROM event_post e", RuntimeError("boom"))])
        self.assertEqual(myposts.get_my_posts(1, db_conn=conn),
                         ([], [], myposts.MSG_FETCH_FAILED))


class MakePreviewTest(unittest.TestCase):
    def test_Noneは空文字(self):
        self.assertEqual(myposts.make_preview(None), "")


if __name__ == "__main__":
    unittest.main()