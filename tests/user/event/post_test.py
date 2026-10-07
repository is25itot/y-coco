"""user/event/post.py の単体テスト

実行 (y-coco ディレクトリで):
    python -m unittest tests.test_event_post -v
    python -m pytest tests/test_event_post.py
"""
import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

from flask import Flask

sys.path.insert(0, os.path.dirname(__file__))
from helpers import FakeConnection, FakeForm, load_module  # noqa: E402

mod = load_module("user/event/post.py", "y_coco_event_post", ["PostForm"])


def sample_data(**overrides):
    data = {
        "title": "地域のお祭り",
        "description": "みんなで楽しむ夏祭りです",
        "datetime": "2026-10-07 10:00:00",
        "fee": 500,
        "location": "山形駅前広場",
        "address": "山形県山形市香澄町1-1-1",
        "parking_info": "駅前駐車場あり",
        "contact_info": "023-000-0000",
    }
    data.update(overrides)
    return data


def sample_form(**overrides):
    form = {
        "event_title": "地域のお祭り",
        "event_description": "みんなで楽しむ夏祭りです",
        "event_datetime": "2026-10-07T10:00",
        "event_fee": "500",
        "event_location": "山形駅前広場",
        "event_address": "山形県山形市香澄町1-1-1",
        "event_parkinginfo": "駅前駐車場あり",
        "event_contactinfo": "023-000-0000",
    }
    form.update(overrides)
    return form


def make_image(name="photo.PNG", content=b"fake-image"):
    return (io.BytesIO(content), name)


class SaveEventPostTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app.config["EVENT_IMAGE_DIR"] = self.tmp.name

    def run_save(self, conn, data=None, image=None):
        with self.app.app_context(), mock.patch.object(
            mod, "get_connection", return_value=conn
        ):
            return mod.save_event_post(1, data or sample_data(), image)

    def make_file_storage(self, name="photo.PNG"):
        from werkzeug.datastructures import FileStorage

        return FileStorage(stream=io.BytesIO(b"fake-image"), filename=name)

    def test_success_without_image_commits(self):
        conn = FakeConnection(select_rows=[(10,)], lastrowid=10)
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (0, 10))
        self.assertEqual(conn.calls, ["begin", "commit", "close"])

    def test_insert_receives_all_fields_in_order(self):
        conn = FakeConnection(select_rows=[(10,)])
        self.run_save(conn)

        (_, params), = conn.statements("INSERT")
        self.assertEqual(
            params,
            (
                1,
                "地域のお祭り",
                "みんなで楽しむ夏祭りです",
                None,  # 画像なし
                "2026-10-07 10:00:00",
                500,
                "山形駅前広場",
                "山形県山形市香澄町1-1-1",
                "駅前駐車場あり",
                "023-000-0000",
            ),
        )

    def test_success_with_image_uses_uuid_filename_and_saves_file(self):
        conn = FakeConnection(select_rows=[(10,)])
        code, post_id = self.run_save(conn, image=self.make_file_storage("photo.PNG"))

        self.assertEqual((code, post_id), (0, 10))
        (_, params), = conn.statements("INSERT")
        image_path = params[3]
        self.assertRegex(image_path, r"^[0-9a-f]{32}\.png$")
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, image_path)))

    def test_image_name_is_not_the_original_filename(self):
        conn = FakeConnection(select_rows=[(10,)])
        self.run_save(conn, image=self.make_file_storage("my-secret-name.jpg"))

        (_, params), = conn.statements("INSERT")
        self.assertNotIn("my-secret-name", params[3])

    def test_verify_miss_rolls_back_with_code_3(self):
        conn = FakeConnection(select_rows=[None])
        code, post_id = self.run_save(conn, image=self.make_file_storage())

        self.assertEqual((code, post_id), (3, None))
        self.assertEqual(conn.calls, ["begin", "rollback", "close"])
        self.assertEqual(os.listdir(self.tmp.name), [])  # 画像は保存されない

    def test_insert_error_rolls_back_with_code_3(self):
        conn = FakeConnection(insert_error=RuntimeError("db down"))
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (3, None))
        self.assertIn("rollback", conn.calls)
        self.assertNotIn("commit", conn.calls)
        self.assertEqual(conn.calls[-1], "close")

    def test_commit_error_removes_saved_image(self):
        conn = FakeConnection(select_rows=[(10,)], commit_error=RuntimeError("boom"))
        code, post_id = self.run_save(conn, image=self.make_file_storage())

        self.assertEqual((code, post_id), (3, None))
        self.assertIn("rollback", conn.calls)
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_unsupported_image_extension_fails_without_insert(self):
        conn = FakeConnection(select_rows=[(10,)])
        code, _ = self.run_save(conn, image=self.make_file_storage("evil.exe"))

        self.assertEqual(code, 3)
        self.assertEqual(conn.statements("INSERT"), [])
        self.assertIn("rollback", conn.calls)

    def test_dict_cursor_row_is_supported(self):
        conn = FakeConnection(select_rows=[{"id": 42}])
        code, post_id = self.run_save(conn)

        self.assertEqual((code, post_id), (0, 42))


class BuildDataTest(unittest.TestCase):
    def build(self, **overrides):
        app = Flask(__name__)
        with app.test_request_context(
            "/event/post", method="POST", data=sample_form(**overrides)
        ):
            return mod._build_data()

    def test_datetime_is_normalized(self):
        data, errors = self.build(event_datetime="2026-10-07T10:00")
        self.assertEqual(errors, [])
        self.assertEqual(data["datetime"], "2026-10-07 10:00:00")

    def test_datetime_accepts_slash_format_from_screen_layout(self):
        data, errors = self.build(event_datetime="2026/10/07/10:30")
        self.assertEqual(errors, [])
        self.assertEqual(data["datetime"], "2026-10-07 10:30:00")

    def test_invalid_datetime_is_error(self):
        _, errors = self.build(event_datetime="明日の昼")
        self.assertEqual(len(errors), 1)

    def test_blank_fee_defaults_to_zero(self):
        data, errors = self.build(event_fee="")
        self.assertEqual(errors, [])
        self.assertEqual(data["fee"], 0)

    def test_fee_is_converted_to_int(self):
        data, _ = self.build(event_fee="1200")
        self.assertEqual(data["fee"], 1200)

    def test_non_numeric_fee_is_error(self):
        _, errors = self.build(event_fee="abc")
        self.assertEqual(len(errors), 1)

    def test_negative_fee_is_error(self):
        _, errors = self.build(event_fee="-1")
        self.assertEqual(len(errors), 1)

    def test_too_long_parking_info_is_error(self):
        _, errors = self.build(event_parkinginfo="あ" * 101)
        self.assertEqual(len(errors), 1)

    def test_too_long_contact_info_is_error(self):
        _, errors = self.build(event_contactinfo="a" * 256)
        self.assertEqual(len(errors), 1)


class RouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test"
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app.config["EVENT_IMAGE_DIR"] = self.tmp.name
        self.app.register_blueprint(mod.event_post_bp)
        self.client = self.app.test_client()

        self.render = mock.patch.object(
            mod, "render_template", return_value="rendered"
        ).start()
        self.addCleanup(mock.patch.stopall)

    def login(self, user_id=1):
        with self.client.session_transaction() as sess:
            sess["user"] = user_id

    def use_form(self, valid=True, errors=None):
        form = FakeForm(valid=valid, errors=errors)
        mock.patch.object(mod, "PostForm", return_value=form).start()
        return form

    def use_db(self, conn):
        mock.patch.object(mod, "get_connection", return_value=conn).start()
        return conn

    def test_not_logged_in_redirects_to_login(self):
        resp = self.client.get("/event/post")

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/login"))

    def test_get_renders_post_form(self):
        self.login()
        self.use_form()
        resp = self.client.get("/event/post")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.render.call_args.args[0], "event/post.html")

    def test_validation_error_shows_message_and_skips_db(self):
        self.login()
        self.use_form(valid=False, errors={"event_title": ["題名は5文字以上です"]})
        get_conn = mock.patch.object(mod, "get_connection").start()

        resp = self.client.post("/event/post", data=sample_form())

        self.assertEqual(resp.status_code, 200)
        self.assertIn("題名は5文字以上です", self.render.call_args.kwargs["ev_er_message"])
        get_conn.assert_not_called()

    def test_invalid_fee_shows_message_and_skips_db(self):
        self.login()
        self.use_form()
        get_conn = mock.patch.object(mod, "get_connection").start()

        self.client.post("/event/post", data=sample_form(event_fee="abc"))

        self.assertIn("料金", self.render.call_args.kwargs["ev_er_message"])
        get_conn.assert_not_called()

    def test_success_redirects_to_detail(self):
        self.login()
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(10,)], lastrowid=10))

        resp = self.client.post("/event/post", data=sample_form())

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/event/10"))
        self.assertIn("commit", conn.calls)

    def test_user_id_comes_from_session_not_from_form(self):
        self.login(user_id=7)
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(10,)]))

        self.client.post("/event/post", data=sample_form(user_id="999"))

        (_, params), = conn.statements("INSERT")
        self.assertEqual(params[0], 7)

    def test_success_with_image_saves_uuid_named_file(self):
        self.login()
        self.use_form()
        conn = self.use_db(FakeConnection(select_rows=[(10,)]))

        data = sample_form()
        data["event_image"] = make_image("photo.png")
        resp = self.client.post(
            "/event/post", data=data, content_type="multipart/form-data"
        )

        self.assertEqual(resp.status_code, 302)
        (_, params), = conn.statements("INSERT")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{32}\.png", params[3]))
        self.assertEqual(os.listdir(self.tmp.name), [params[3]])

    def test_db_failure_returns_500_with_message(self):
        self.login()
        self.use_form()
        self.use_db(FakeConnection(select_rows=[None]))

        resp = self.client.post("/event/post", data=sample_form())

        self.assertEqual(resp.status_code, 500)
        self.assertEqual(self.render.call_args.kwargs["code"], 3)
        self.assertIn("失敗", self.render.call_args.kwargs["ev_er_message"])


if __name__ == "__main__":
    unittest.main()