"""app.py

y-coco(地域情報発信アプリ)のFlaskアプリ本体。
アプリの生成・設定の読み込み・Blueprintの登録・トップページのルーティングを担当する。

実行方法(code/ ディレクトリで。y_coco をパッケージとして扱う):
    flask --app y_coco.app run --debug
    または
    python -m y_coco.app
"""
from flask import Flask, render_template

from . import config
from .user.user_views import user_bp

# admin_views.py は未作成のため、作成でき次第コメントを外して有効化する
from .admin.admin_views import admin_bp


def create_app(test_config=None):
    """Flaskアプリを生成して返す(アプリケーションファクトリ)。

    Args:
        test_config (dict | None): 指定した場合、config.py の設定を上書きする。
            単体テストで設定を差し替える用途を想定している。
    """
    app = Flask(__name__)

    # config.py の大文字の変数(SECRET_KEY など)を読み込む
    app.config.from_object(config)
    if test_config is not None:
        app.config.update(test_config)

    # Blueprint の登録
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)  # admin_views.py 作成後に有効化

    @app.route("/")
    def index():
        """スタート画面(GD1): ログイン・新規登録を選択する"""
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)