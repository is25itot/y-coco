from flask import Flask, render_template
from pymysql import connect, OperationalError
from pathlib import Path
from flask_wtf import FlaskForm, CSRFProtect
from y_coco import config #まだかいてない


csrf = CSRFProtect()


def create_app(config_key):
    # インスタンス
    app = Flask(__name__)

    # config_keyにマッチする環境のコンフィグクラスを読み込む
    app.config.from_object(config[config_key])

    # パッケージからviewsインポート
    from y_coco.user import user_views

    # register_blueprintでviewsのuserをアプリへ登録する
    app.register_blueprint(user_views.user)

    return app