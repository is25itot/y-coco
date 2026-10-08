"""app.py

y-coco(地域情報発信アプリ)のFlaskアプリ本体。
アプリの生成・設定の読み込み・Blueprintの登録・トップページ・エラーページを担当する。

実行方法(code/ ディレクトリで。y_coco をパッケージとして扱う):
    flask --app y_coco.app run --debug
    または
    python -m y_coco.app
"""
from flask import Blueprint, Flask, render_template
from flask_wtf.csrf import CSRFProtect

from y_coco import config
from y_coco import detail, kh_detail, kh_list, kh_search, login, logout, search
from y_coco import list as list_views
from y_coco.admin import admin_views
from y_coco.user import user_views

# Blueprint を持つモジュール(登録順)
BLUEPRINT_MODULES = (
    user_views,
    admin_views,
    login,
    logout,
    list_views,
    detail,
    search,
    kh_list,
    kh_detail,
    kh_search,
)

csrf_protect = CSRFProtect()


def find_blueprints(module):
    """モジュール内の Blueprint を返す。

    そのモジュール自身で定義された Blueprint(import_name がモジュール名と一致)を優先する。
    他モジュールから import しただけの Blueprint を二重登録しないための処理。
    """
    found = []
    for obj in vars(module).values():
        if isinstance(obj, Blueprint) and not any(obj is b for b in found):
            found.append(obj)
    own = [bp for bp in found if bp.import_name == module.__name__]
    return own or found


def register_blueprints(app, modules=BLUEPRINT_MODULES):
    """modules に含まれる Blueprint をすべて app に登録する"""
    for module in modules:
        blueprints = find_blueprints(module)
        if not blueprints:
            raise RuntimeError(f"{module.__name__} に Blueprint が見つかりません")
        for bp in blueprints:
            app.register_blueprint(bp)


def create_app(test_config=None):
    """Flaskアプリを生成して返す(アプリケーションファクトリ)。

    Args:
        test_config (dict | None): 指定した場合、config.py の設定を上書きする。
            単体テストで設定を差し替える用途を想定している。
    """
    app = Flask(__name__)

    # config.py の大文字の変数(SECRET_KEY など)を読み込む
    app.config.from_object(config.Config)
    if test_config is not None:
        app.config.update(test_config)

    csrf_protect.init_app(app)
    register_blueprints(app)

    @app.route("/")
    def index():
        """スタート画面: ログイン・新規登録を選択する"""
        return render_template("index.html")

    # @app.errorhandler(404)
    # def not_found(error):
    #     return "ページが見つかりません", 404

    # 404エラー確認用
    @app.errorhandler(404)
    def not_found(error):
        from flask import request
        app.logger.warning("404: %s", request.path)
        return f"ページが見つかりません: {request.path}", 404

    @app.errorhandler(413)
    def too_large(error):
        return "アップロードできるファイルサイズを超えています", 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)