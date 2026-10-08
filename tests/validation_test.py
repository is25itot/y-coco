"""validation.py の単体テスト (pytest)

実行: pytest -v
境界値(最小/最大とその前後)・空・形式違いを網羅する。
※ フォーム名を UserForm に変更した場合は import と使用箇所を合わせること。
"""
import io

import pytest
from flask import Flask

from y_coco.validation import (
    UserForm,
    PasswordForm,
    ImageForm,
    PostForm,
    KhPostForm,
    CommentForm,
    MAX_IMAGE_SIZE,
)


@pytest.fixture(scope="module")
def app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", WTF_CSRF_ENABLED=False)  # テストではCSRFを無効化
    return app


@pytest.fixture
def run(app):
    """フォームにPOSTデータを渡して (validate結果, errors) を返す"""

    def _run(form_cls, **data):
        with app.test_request_context(method="POST", data=data):
            form = form_cls()
            return form.validate(), form.errors

    return _run


def file_data(size, name="a.png"):
    return (io.BytesIO(b"a" * size), name)


# ---------- username ----------
@pytest.mark.parametrize("value, ok", [
    ("abc", True),            # 下限
    ("a" * 10, True),         # 上限
    ("ab", False),            # 下限-1
    ("a" * 11, False),        # 上限+1
    ("", False),              # 空
    ("abc_", False),          # 記号
    ("あいう", False),         # 日本語
    ("ａｂｃ", False),         # 全角英数字
])
def test_username(run, value, ok):
    result, errors = run(UserForm, username=value)
    assert result is ok
    assert ("username" in errors) is (not ok)


# ---------- password ----------
@pytest.mark.parametrize("value, ok", [
    ("a" * 8, True),
    ("a" * 64, True),
    ("a" * 7, False),
    ("a" * 65, False),
    ("", False),
    ("abcdefg!", False),
    ("パスワード1234", False),
])
def test_password(run, value, ok):
    result, errors = run(PasswordForm, password=value)
    assert result is ok
    assert ("password" in errors) is (not ok)


# ---------- image ----------
@pytest.mark.parametrize("name", ["a.png", "a.jpg", "a.jpeg", "a.gif", "a.webp"])
def test_image_allowed_extension(run, name):
    result, _ = run(ImageForm, image=file_data(10, name))
    assert result is True


@pytest.mark.parametrize("name", ["a.txt", "a.bmp", "a.pdf"])
def test_image_invalid_extension(run, name):
    result, errors = run(ImageForm, image=file_data(10, name))
    assert result is False
    assert "image" in errors


def test_image_size_limit(run):
    ok, _ = run(ImageForm, image=file_data(MAX_IMAGE_SIZE))          # ちょうど1MB
    ng, errors = run(ImageForm, image=file_data(MAX_IMAGE_SIZE + 1))  # 1MB超
    assert ok is True
    assert ng is False
    assert "image" in errors


# ---------- PostForm ----------
def valid_post(**override):
    data = {"title": "a" * 5, "desc": "a" * 5, "location": "山形", "dt": "2026-10-05"}
    data.update(override)
    return data


def test_post_valid(run):
    result, errors = run(PostForm, **valid_post())
    assert result is True and errors == {}


@pytest.mark.parametrize("field, value", [
    ("title", ""), ("title", "a" * 4), ("title", "a" * 51),
    ("desc", ""), ("desc", "a" * 4), ("desc", "a" * 5001),
    ("location", ""), ("location", "   "),     # 空白のみも空扱い
    ("dt", ""), ("dt", "abc"), ("dt", "2026-02-30"), ("dt", "2026/10/05"),
])
def test_post_invalid(run, field, value):
    result, errors = run(PostForm, **valid_post(**{field: value}))
    assert result is False
    assert field in errors


@pytest.mark.parametrize("field, value", [
    ("title", "a" * 50), ("desc", "a" * 5000),
])
def test_post_upper_bound(run, field, value):
    result, _ = run(PostForm, **valid_post(**{field: value}))
    assert result is True


def test_desc_newline_counts_as_one_char(run):
    # ブラウザは改行を \r\n で送る。1文字として数えて5000文字ちょうどならOK
    ok, _ = run(PostForm, **valid_post(desc="a\r\n" * 2500))
    ng, _ = run(PostForm, **valid_post(desc="a\r\n" * 2500 + "a"))
    assert ok is True
    assert ng is False


# ---------- KhPostForm ----------
@pytest.mark.parametrize("data, ok", [
    ({"title": "a" * 5, "kh_post": "a" * 5}, True),
    ({"title": "a" * 50, "kh_post": "a" * 500}, True),
    ({"title": "a" * 4, "kh_post": "a" * 5}, False),
    ({"title": "a" * 51, "kh_post": "a" * 5}, False),
    ({"title": "", "kh_post": "a" * 5}, False),
    ({"title": "a" * 5, "kh_post": "a" * 4}, False),
    ({"title": "a" * 5, "kh_post": "a" * 501}, False),
    ({"title": "a" * 5, "kh_post": ""}, False),
])
def test_kh_post(run, data, ok):
    result, _ = run(KhPostForm, **data)
    assert result is ok


# ---------- CommentForm ----------
@pytest.mark.parametrize("value, ok", [
    ("a" * 5, True), ("a" * 500, True),
    ("a" * 4, False), ("a" * 501, False), ("", False),
])
def test_comment(run, value, ok):
    result, errors = run(CommentForm, comment=value)
    assert result is ok
    assert ("comment" in errors) is (not ok)