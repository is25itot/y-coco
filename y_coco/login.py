"""
login.py
ユーザーのログイン認証処理を行うモジュールです。
"""

from werkzeug.security import check_password_hash
# db.py からユーザー取得関数をインポート（プロジェクトのDB構造に合わせて調整してください）
from y_coco.db import get_user_by_username


def authenticate_user(username, password):
    """
    入力されたユーザーネームとパスワードを検証し、認証結果を返します。

    Parameters:
        username (str): 入力されたユーザーネーム
        password (str): 入力された平文パスワード

    Returns:
        tuple: (success: bool, message_or_user: str | dict)
            - 成功時: (True, user_dict)
            - 失敗時: (False, "エラーメッセージ")
    """
    # 必須項目の入力チェック
    if not username or not password:
        return False, "ユーザーネームとパスワードを入力してください。"

    # データベースからユーザー情報を取得
    user = get_user_by_username(username)
    if not user:
        # セキュリティ上、ユーザーが存在しない場合も一般的なエラーメッセージを返す
        return False, "ユーザーネームまたはパスワードが正しくありません。"

    # パスワードハッシュの検証
    # （DB側のカラム名に合わせて user['password_hash'] または user['password'] を参照）
    stored_hash = user.get('password_hash') or user.get('password')

    if not stored_hash or not check_password_hash(stored_hash, password):
        return False, "ユーザーネームまたはパスワードが正しくありません。"

    # 認証成功（ユーザー情報を返す）
    return True, user