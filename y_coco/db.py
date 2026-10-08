"""db.py - データベース接続 (XAMPP の MySQL / MariaDB)

get_connection() は DictCursor 付きの pymysql 接続を返す。
トランザクションは呼び出し側で commit() / rollback() する (autocommit=False)。
接続情報は config.py (環境変数で上書き可) に書く。
"""
import pymysql
from pymysql.cursors import DictCursor

from y_coco.config import Config


def get_connection():
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )