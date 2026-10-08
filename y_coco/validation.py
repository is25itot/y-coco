"""validation.py
入力された値を受け取り、入力値が入力規則に適合しているかチェックする。
(モジュール設計書 使用機能ID: FL1)

エラーメッセージは Flask-WTF(WTForms)の form.<field>.errors に格納され、
テンプレート側で表示される。
"""
import os
from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError

# 半角英数字のみ (\Z で末尾の改行も許可しない)
ALNUM_PATTERN = r"[A-Za-z0-9]+\Z"
ALNUM_MESSAGE = "半角英数字のみで入力してください"

ALLOWED_IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp"]
MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1MB
DATE_FORMAT = "%Y-%m-%d"


def required(label):
    """空チェック用バリデータ"""
    return DataRequired(message=f"{label}を入力してください")


def length(label, min_len, max_len):
    """文字列長チェック用バリデータ"""
    return Length(
        min=min_len,
        max=max_len,
        message=f"{label}は{min_len}～{max_len}文字以内で入力してください",
    )


def normalize_newline(value):
    """textareaの改行(ブラウザからは \\r\\n で送られる)を \\n に統一する。
    これにより改行1つが1文字として文字数チェックされる。"""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    return value


def validate_image_size(form, field):
    """画像のファイルサイズが1MB以内かチェックする"""
    file = field.data
    if not file or not getattr(file, "filename", ""):
        return  # 未選択はここでは判定しない
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)  # 後続の保存処理のため先頭に戻す
    if size > MAX_IMAGE_SIZE:
        raise ValidationError("画像のファイルサイズは1MB以内にしてください")


def validate_date_format(form, field):
    """日付の形式(YYYY-MM-DD)として正しいかチェックする"""
    try:
        datetime.strptime(field.data, DATE_FORMAT)
    except (TypeError, ValueError):
        raise ValidationError("日付の形式が正しくありません(例: 2026-10-05)")


class UserForm(FlaskForm):
    username = StringField(
        "username",
        validators=[
            required("username"),
            length("username", 3, 10),
            Regexp(ALNUM_PATTERN, message=ALNUM_MESSAGE),
        ],
    )


class PasswordForm(FlaskForm):
    password = PasswordField(
        "password",
        validators=[
            required("password"),
            length("password", 8, 64),
            Regexp(ALNUM_PATTERN, message=ALNUM_MESSAGE),
        ],
    )


class ImageForm(FlaskForm):
    image = FileField(
        "image",
        validators=[
            FileAllowed(
                ALLOWED_IMAGE_EXTENSIONS,
                message="対応形式は .png .jpg(.jpeg) .gif .webp です",
            ),
            validate_image_size,
        ],
    )


class PostForm(FlaskForm):
    title = StringField(
        "title",
        validators=[required("title"), length("title", 5, 50)],
    )
    # textarea(改行を含む)を受け取るため TextAreaField を使用
    desc = TextAreaField(
        "desc",
        filters=[normalize_newline],
        validators=[required("desc"), length("desc", 5, 5000)],
    )
    location = StringField("location", validators=[required("location")])
    dt = StringField("dt", validators=[required("dt"), validate_date_format])


class KhPostForm(FlaskForm):
    # PostForm の title と同じ規則
    title = StringField(
        "title",
        validators=[required("title"), length("title", 5, 50)],
    )
    # 設計書の項目名は kh-post だが、Pythonの属性名にハイフンは使えないため kh_post とする
    kh_post = StringField(
        "kh-post",
        validators=[required("kh-post"), length("kh-post", 5, 500)],
    )


class CommentForm(FlaskForm):
    comment = StringField(
        "comment",
        validators=[required("comment"), length("comment", 5, 500)],
    )