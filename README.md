# y-coco(地域情報発信アプリ)

## 起動手順(Windows + XAMPP)

1. XAMPP の Apache / MySQL を起動し、`schema.sql` を phpMyAdmin の「インポート」で実行する(DB 名 `ycoco`)。
2. `pip install -r requirements.txt`
3. 管理者を作る: `python create_admin.py admin001 password123`
4. 起動: `python app.py`(または `flask --app app run --debug`)

DB 接続先・`SECRET_KEY` は `config.py`(環境変数 `DB_HOST` `DB_USER` `DB_PASSWORD` `DB_NAME` `SECRET_KEY` で上書き可)。
画像は `static/uploads/` に保存し、DB の `imagepath` にはファイル名だけを入れる。

## テスト

pytest が「アプリケーション制御」で動かない環境でも、標準の unittest で全テストを実行できる。

    python -m unittest discover -s tests -p "*_test.py"

## app.py で登録するもの

    from config import Config
    app.config.from_object(Config)

    from login import login_bp
    from logout import logout_bp
    from list import list_bp
    from detail import detail_bp
    from search import search_bp
    from kh_list import kh_list_bp
    from kh_detail import kh_detail_bp
    from kh_search import kh_search_bp
    from admin.admin_views import admin_bp      # 管理者機能 (/admin 配下)

`/` は `templates/index.html` を返す。`user_views.py` (アカウント・投稿・コメント) も登録すること。

## テンプレートが前提にしているエンドポイント(user_views.py 側)

`tests/templates_test.py::test_every_url_for_endpoint_exists` が、テンプレート内の `url_for` が
`tests/fakes.py` の `USER_VIEW_ENDPOINTS` に揃っていることを確認する。
`user_views.py` の名前・URL が違う場合は、下の表に合わせるか、テンプレートの `url_for` を置換する。

| endpoint | 用途 | 受け取る引数 |
|---|---|---|
| account.register | 新規登録 | |
| account.myaccount / profile_edit / password_change / myposts / notifications | マイアカウント関連 | |
| event.post | イベント投稿 | |
| event.comment | コメント送信(POST) | event_id |
| event.delete_confirm / event.delete | 投稿削除の確認(GET) / 実行(POST) | event_id |
| event.comment_delete_confirm / event.comment_delete | コメント削除の確認 / 実行 | comment_id |
| knowhow.post / comment / delete_confirm / delete / comment_delete_confirm / comment_delete | ノウハウ側も同様 | knowhow_id / comment_id |

## テンプレートに渡す変数(user_views.py 側)

| テンプレート | 変数 |
|---|---|
| account/myaccount.html | `username`, `imagepath`(または `user` に `username` `imagepath`) |
| account/prof_edit.html | `username`。フォーム項目 `newusername`, `newimage` |
| account/pass_change.html | フォーム項目 `nowpass`, `newpass`, `repass` |
| account/register.html | フォーム項目 `username`, `password`, `repassword` |
| account/myposts.html | `post_list`(`id` `title` `description`/`detail` `post_type`)、`comment_list`、`display_msg` |
| account/notifications.html | `notification_list`(`id` `post_type` `post_id` `created_at` `read_flg` `username`)、`display_msg`。既読化は `read_notification_ids` を POST |
| event/post.html | フォーム項目 `event_title` `event_description` `event_image` `event_datetime` `event_fee` `event_location` `event_address` `event_parkinginfo` `event_contactinfo` |
| knowhow/kh_post.html | フォーム項目 `knowhow_title` `knowhow_detail` |
| event/event_delete_confirm.html, knowhow/kh_delete_confirm.html | `event` / `knowhow`(詳細と同じ形の dict) |
| event/event_comment_delete_confirm.html, knowhow/kh_comment_delete_confirm.html | `comment`(`id` `post_id` `comment` `username` `usericon` `created_at`) |

エラーメッセージは `flash(メッセージ, "error")` で出せば、全画面の上部に自動表示される。
CSRF 対策に Flask-WTF の `CSRFProtect` を使う場合、フォームの hidden は自動で出力される(未導入でも動く)。

## コメント・通知の post_type

`1` = イベント、`2` = ノウハウ(`comment.post_type` / `notification.post_type`)。
