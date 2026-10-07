import os
import shutil
import tempfile
import unittest

import fake_db
from fake_db import FakeConnection
from werkzeug.security import check_password_hash, generate_password_hash

from y_coco.user.account import edit


class FakeUpload:
    """FileStorage の代わり (filename と save だけ持つ)。"""

    def __init__(self, filename, data=b"img"):
        self.filename = filename
        self._data = data

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self._data)


def _profile_rules(username="old", imagepath=None, name_taken=False,
                   name_verified=True, image_verified=True):
    return [
        ("SELECT username, imagepath FROM users",
         {"rows": [{"username": username, "imagepath": imagepath}]}),
        ("AND id <> %s", {"rows": [{"id": 2}] if name_taken else []}),
        ("AND username = %s", {"rows": [{"id": 1}] if name_verified else []}),
        ("AND imagepath = %s", {"rows": [{"id": 1}] if image_verified else []}),
    ]


class GetUsernameTest(unittest.TestCase):
    def test_ユーザーネームを返す(self):
        conn = FakeConnection(rules=[("SELECT username FROM users", {"rows": [{"username": "taro"}]})])
        self.assertEqual(edit.get_username(1, db_conn=conn), "taro")

    def test_存在しなければNone(self):
        conn = FakeConnection(rules=[("SELECT username FROM users", {"rows": []})])
        self.assertIsNone(edit.get_username(1, db_conn=conn))


class UpdateProfileTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _uploads(self):
        d = os.path.join(self.root, "uploads")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def test_ユーザーネームだけ変更できる(self):
        conn = FakeConnection(rules=_profile_rules())
        code, msg = edit.update_profile(1, "newname", None, self.root, db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])
        self.assertEqual(conn.sqls("UPDATE users SET username")[0][1], ("newname", 1))
        self.assertEqual(conn.sqls("UPDATE users SET imagepath"), [])

    def test_自分のユーザーネームのままなら重複扱いにしない(self):
        conn = FakeConnection(rules=_profile_rules(username="same"))
        code, _ = edit.update_profile(1, "same", None, self.root, db_conn=conn)
        self.assertEqual(code, 0)
        self.assertEqual(conn.sqls("UPDATE users SET username"), [])

    def test_ユーザーネーム重複ならロールバックしてcode1(self):
        conn = FakeConnection(rules=_profile_rules(name_taken=True))
        code, msg = edit.update_profile(1, "taken", None, self.root, db_conn=conn)
        self.assertEqual((code, msg), (1, edit.MSG_NAME_DUPLICATE))
        self.assertEqual(conn.events, ["begin", "rollback"])
        self.assertEqual(conn.sqls("UPDATE users SET username"), [])

    def test_更新後の確認に失敗したらロールバック(self):
        conn = FakeConnection(rules=_profile_rules(name_verified=False))
        code, _ = edit.update_profile(1, "newname", None, self.root, db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(conn.events, ["begin", "rollback"])

    def test_画像変更はUUIDのファイル名で保存し古い画像を消す(self):
        os.makedirs(os.path.join(self.root, "uploads"))
        old_file = os.path.join(self.root, "uploads", "old.png")
        open(old_file, "wb").close()
        conn = FakeConnection(rules=_profile_rules(imagepath="uploads/old.png"))

        code, _ = edit.update_profile(1, None, FakeUpload("My Photo.JPG"), self.root, db_conn=conn)

        self.assertEqual(code, 0)
        self.assertEqual(conn.events, ["begin", "commit"])
        saved = self._uploads()
        self.assertEqual(len(saved), 1)                  # 新しい画像だけが残る
        self.assertTrue(saved[0].endswith(".jpg"))
        self.assertNotIn("Photo", saved[0])              # 元のファイル名は使わない
        self.assertFalse(os.path.exists(old_file))
        self.assertEqual(conn.sqls("UPDATE users SET imagepath")[0][1],
                         (f"uploads/{saved[0]}", 1))
        self.assertLessEqual(len(f"uploads/{saved[0]}"), 50)   # users.imagepath は VARCHAR(50)

    def test_画像の更新確認に失敗したらロールバックし新画像を消して元画像は残す(self):
        os.makedirs(os.path.join(self.root, "uploads"))
        old_file = os.path.join(self.root, "uploads", "old.png")
        open(old_file, "wb").close()
        conn = FakeConnection(rules=_profile_rules(imagepath="uploads/old.png", image_verified=False))

        code, msg = edit.update_profile(1, None, FakeUpload("a.png"), self.root, db_conn=conn)

        self.assertEqual((code, msg), (1, edit.MSG_IMAGE_FAILED))
        self.assertEqual(conn.events, ["begin", "rollback"])
        self.assertEqual(self._uploads(), ["old.png"])

    def test_画像は成功でもユーザーネームが失敗なら全体をロールバック(self):
        conn = FakeConnection(rules=_profile_rules(name_taken=True))
        code, _ = edit.update_profile(1, "taken", FakeUpload("a.png"), self.root, db_conn=conn)
        self.assertEqual(code, 1)
        self.assertEqual(conn.events, ["begin", "rollback"])
        self.assertEqual(self._uploads(), [])            # 保存した新画像も消えている

    def test_対応していない拡張子はDBに触れずcode1(self):
        conn = FakeConnection(rules=_profile_rules())
        code, msg = edit.update_profile(1, None, FakeUpload("virus.exe"), self.root, db_conn=conn)
        self.assertEqual((code, msg), (1, edit.MSG_BAD_IMAGE))
        self.assertEqual(conn.events, [])
        self.assertEqual(self._uploads(), [])

    def test_DB例外なら新画像を消してcode1(self):
        rules = [("SELECT username, imagepath FROM users", RuntimeError("boom"))]
        conn = FakeConnection(rules=rules)
        code, msg = edit.update_profile(1, None, FakeUpload("a.png"), self.root, db_conn=conn)
        self.assertEqual((code, msg), (1, edit.MSG_PROFILE_FAILED))
        self.assertIn("rollback", conn.events)
        self.assertEqual(self._uploads(), [])

    def test_ユーザーが存在しなければロールバック(self):
        conn = FakeConnection(rules=[("SELECT username, imagepath FROM users", {"rows": []})])
        code, msg = edit.update_profile(1, "x", None, self.root, db_conn=conn)
        self.assertEqual((code, msg), (1, edit.MSG_USER_NOT_FOUND))
        self.assertEqual(conn.events, ["begin", "rollback"])


class ChangePasswordTest(unittest.TestCase):
    def _rules(self, current="OldPass123", verified=True):
        return [
            ("SELECT passhash FROM users", {"rows": [{"passhash": generate_password_hash(current)}]}),
            ("AND passhash = %s", {"rows": [{"id": 1}] if verified else []}),
        ]

    def test_再入力が一致しなければcode7でDBに触れない(self):
        conn = FakeConnection(rules=self._rules())
        code, msg = edit.change_password(1, "OldPass123", "NewPass123", "Different1", db_conn=conn)
        self.assertEqual((code, msg), (7, edit.MSG_PASS_MISMATCH))
        self.assertEqual(conn.events, [])

    def test_現在と同じパスワードならcode6でDBに触れない(self):
        conn = FakeConnection(rules=self._rules())
        code, msg = edit.change_password(1, "OldPass123", "OldPass123", "OldPass123", db_conn=conn)
        self.assertEqual((code, msg), (6, edit.MSG_PASS_SAME))
        self.assertEqual(conn.events, [])

    def test_現在のパスワードが違えばロールバックしてcode5(self):
        conn = FakeConnection(rules=self._rules())
        code, msg = edit.change_password(1, "WrongPass1", "NewPass123", "NewPass123", db_conn=conn)
        self.assertEqual((code, msg), (5, edit.MSG_PASS_CURRENT_WRONG))
        self.assertEqual(conn.events, ["begin", "rollback"])
        self.assertEqual(conn.sqls("UPDATE users"), [])

    def test_成功するとハッシュを更新してコミット(self):
        conn = FakeConnection(rules=self._rules())
        code, msg = edit.change_password(1, "OldPass123", "NewPass123", "NewPass123", db_conn=conn)
        self.assertEqual((code, msg), (0, None))
        self.assertEqual(conn.events, ["begin", "commit"])
        newhash, user_id = conn.sqls("UPDATE users SET passhash")[0][1]
        self.assertEqual(user_id, 1)
        self.assertNotEqual(newhash, "NewPass123")
        self.assertTrue(check_password_hash(newhash, "NewPass123"))

    def test_更新後の確認に失敗したらロールバックしてcode9(self):
        conn = FakeConnection(rules=self._rules(verified=False))
        code, _ = edit.change_password(1, "OldPass123", "NewPass123", "NewPass123", db_conn=conn)
        self.assertEqual(code, 9)
        self.assertEqual(conn.events, ["begin", "rollback"])

    def test_ユーザーが存在しなければcode9(self):
        conn = FakeConnection(rules=[("SELECT passhash FROM users", {"rows": []})])
        code, _ = edit.change_password(1, "OldPass123", "NewPass123", "NewPass123", db_conn=conn)
        self.assertEqual(code, 9)
        self.assertEqual(conn.events, ["begin", "rollback"])

    def test_DB例外ならロールバックしてcode9(self):
        conn = FakeConnection(rules=[("SELECT passhash FROM users", RuntimeError("boom"))])
        code, msg = edit.change_password(1, "OldPass123", "NewPass123", "NewPass123", db_conn=conn)
        self.assertEqual((code, msg), (9, edit.MSG_PASS_FAILED))
        self.assertIn("rollback", conn.events)


if __name__ == "__main__":
    unittest.main()