"""create_admin.py - 管理者アカウントを1件作成する初期設定用スクリプト。

使い方:  python create_admin.py <ユーザーネーム> <パスワード>
ユーザーネームは半角英数字3〜10文字、パスワードは半角英数字8〜64文字。
"""
import re
import sys

from werkzeug.security import generate_password_hash

from y_coco import db


def create_admin(username, password):
    if not re.fullmatch(r"[A-Za-z0-9]{3,10}", username):
        raise ValueError("ユーザーネームは半角英数字3〜10文字にしてください。")
    if not re.fullmatch(r"[A-Za-z0-9]{8,64}", password):
        raise ValueError("パスワードは半角英数字8〜64文字にしてください。")

    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                raise ValueError("同じユーザーネームが既に存在します。")
            cur.execute(
                "INSERT INTO users (username, passhash, imagepath, admin_flg) "
                "VALUES (%s, %s, NULL, 1)",
                (username, generate_password_hash(password)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    try:
        create_admin(sys.argv[1], sys.argv[2])
    except ValueError as e:
        sys.exit(str(e))
    print(f"管理者 {sys.argv[1]} を作成しました。")