# y-coco(地域情報発信アプリ)

地域のイベントとノウハウを投稿・閲覧できる Flask 製の Web アプリ。
一般ユーザーは投稿・コメント・通知の確認、管理者はアカウント・投稿・コメントの削除ができる。

- Python / Flask(アプリケーションファクトリ + Blueprint 構成)
- ログイン管理: Flask-Login(`y_coco/auth.py`)
- 入力チェック・CSRF: Flask-WTF / WTForms
- DB: MySQL / MariaDB(開発は XAMPP)、接続は PyMySQL
- 検索: Janome による形態素解析 + OR 検索(未導入時は空白区切りで代用)

## 起動手順(Windows + XAMPP)

以下はすべてプロジェクト直下(`y_coco/` フォルダがあるディレクトリ)で実行する。

1. XAMPP の Apache / MySQL を起動し、`schema.sql` を phpMyAdmin の「インポート」で実行する。
2. 依存ライブラリを入れる。

       pip install -r requirements.txt

3. 管理者アカウントを作る(ユーザーネームは半角英数字 3〜10 文字、パスワードは半角英数字 8〜64 文字)。

       python create_admin.py admin001 password123

4. 起動する。

       flask --app y_coco.app run --debug
       # または
       python -m y_coco.app

   `python -m y_coco.app` は `0.0.0.0:5000` で待ち受ける。

## 設定(`y_coco/config.py`)

環境変数で上書きできる。既定値は XAMPP の初期設定(root・パスワードなし)。

| 環境変数 | 既定値 | 内容 |
|---|---|---|
| `SECRET_KEY` | `dev-only-change-me` | セッション・CSRF 用。本番では必ず変更する |
| `DB_HOST` | `localhost` | DB ホスト |
| `DB_PORT` | `3306` | DB ポート |
| `DB_USER` | `root` | DB ユーザー |
| `DB_PASSWORD` | (空) | DB パスワード |
| `DB_NAME` | `pbl-g3` | データベース名 |

> **注意:** `schema.sql` が作る DB 名は `ycoco`、`config.py` の `DB_NAME` 既定値は `pbl-g3` で食い違っている。
> どちらかに揃えること(例: 環境変数 `DB_NAME=ycoco` を指定する、または `schema.sql` / `config.py` を修正する)。

画像は `y_coco/static/uploads/` に保存し、DB の `imagepath` にはファイル名(UUID + 拡張子)だけを入れる。
対応形式は png / jpg / jpeg / gif / webp。

## ディレクトリ構成

    ├── create_admin.py          管理者作成スクリプト
    ├── schema.sql               DB 定義
    ├── requirements.txt
    ├── pytest.ini
    ├── tests/                   テスト
    └── y_coco/
        ├── app.py               アプリ生成・Blueprint 登録・トップページ・エラーページ
        ├── config.py            設定
        ├── db.py                DB 接続・トランザクション補助
        ├── auth.py              Flask-Login 設定、User クラス、admin_required
        ├── validation.py        入力チェック用フォーム
        ├── login.py / logout.py
        ├── list.py / detail.py / search.py          イベントの一覧・詳細・検索
        ├── kh_list.py / kh_detail.py / kh_search.py ノウハウの一覧・詳細・検索
        ├── templates/           共通テンプレート(base, header, footer, _macros など)
        ├── static/              style.css, script.js, images/, uploads/
        ├── user/
        │   ├── user_views.py    一般ユーザー画面のルーティング(Blueprint: user)
        │   ├── account/         register / edit / myposts / delete / notification / notification_check
        │   ├── event/           post.py(投稿), comment.py(コメント)
        │   ├── knowhow/         kh_post.py(投稿), kh_comment.py(コメント)
        │   └── templates/       account/, event/, knowhow/
        └── admin/
            ├── admin_views.py   管理者画面のルーティング(Blueprint: admin, /admin 配下)
            └── templates/       account/, event/, knowhow/

### Blueprint の登録

`app.py` の `BLUEPRINT_MODULES` に並べたモジュールから Blueprint を自動で見つけて登録する。
新しい画面モジュールを追加したら、このタプルにも追加する。

    user_views, admin_views, login, logout, list_views, detail, search,
    kh_list, kh_detail, kh_search,
    event_post, event_comment, kh_post, kh_comment

`user/account/` 内の `register.py` `edit.py` `myposts.py` `delete.py` `notification_check.py` は、
`user_views.py` から関数として呼び出される。ここの Blueprint は登録されないので、ルートは `user_views.py` 側で定義する。

## 主な URL

| 区分 | URL | 内容 |
|---|---|---|
| 共通 | `/` | スタート画面 |
| | `/login` `/logout` | ログイン・ログアウト |
| | `/register` | 新規登録(登録後そのままログイン) |
| イベント | `/events` `/events/<id>` `/events/search` | 一覧(開催前のみ)・詳細・検索 |
| | `/event/post` | 投稿 |
| | `/event/<id>/comment` (POST) | コメント送信 |
| ノウハウ | `/knowhow` `/knowhow/<id>` `/knowhow/search` | 一覧・詳細・検索 |
| | `/knowhow/post` | 投稿 |
| | `/knowhow/<id>/comment` (POST) | コメント送信 |
| マイアカウント | `/myaccount` `/profile/edit` `/password/change` | 表示・プロフィール変更・パスワード変更 |
| | `/myposts` `/notifications` | 過去の投稿・通知 |
| 削除(本人) | `/delete/<kind>/<id>` (POST) | `kind` は event / knowhow / comment |
| | `/event/<id>/delete/confirm` `/knowhow/<id>/delete/confirm` | 投稿の削除確認 |
| | `/event-comments/<id>/delete/confirm` `/knowhow-comments/<id>/delete/confirm` | コメントの削除確認 |
| 管理者 | `/admin/accounts` `/admin/accounts/search` `/admin/accounts/<id>` | アカウント一覧・検索・詳細 |
| | `/admin/accounts/<id>/delete[/confirm]` | アカウント削除 |
| | `/admin/events/<id>/delete[/confirm]` `/admin/event-comments/<id>/delete[/confirm]` | イベント・コメント削除 |
| | `/admin/knowhow/<id>/delete[/confirm]` `/admin/knowhow-comments/<id>/delete[/confirm]` | ノウハウ・コメント削除 |

`/admin` 配下は未ログインならログイン画面へ、管理者以外は 403。
イベント・ノウハウの一覧・詳細・検索は共通モジュールがログインユーザーを見て、管理者用 / 投稿者用 / 一般用のテンプレートを切り替える。

## ログインとテンプレート共通の変数

- ログイン中のユーザーは `flask_login.current_user`(`id` / `username` / `imagepath` / `admin_flg`)で参照する。
- 全テンプレートに `app.py` の context_processor が `login_flg`(ログイン中か)と `unread_count`(一般ユーザーの未読通知数)を渡す。
- エラーメッセージは `flash(メッセージ, "error")`、成功は `flash(メッセージ, "success")` で出す。`base.html` が上部に表示する(success は数秒で消える)。
- CSRF 対策は `CSRFProtect` を全体に適用している。フォームには `{{ csrf() }}`(`_macros.html`)を入れる。

## フォームの項目名

| 画面 | 項目名 |
|---|---|
| 新規登録 | `username` `password` `repassword` |
| ログイン | `username` `password` |
| プロフィール変更 | `username` `image` |
| パスワード変更 | `nowpass` `newpass` `repass` |
| イベント投稿 | `title` `dt`(開催日) `location` `address` `desc` `fee` `parking_info` `contact_info` `image` |
| ノウハウ投稿 | `title` `kh_post` |
| コメント | `comment` |
| 検索(イベント・ノウハウ・アカウント) | GET パラメータ `q` |

入力規則は `validation.py` を参照(ユーザーネーム 3〜10 文字、パスワード 8〜64 文字、いずれも半角英数字。題名 5〜50 文字、コメント 5〜500 文字など)。

## データベース

テーブルは `users` / `event_post` / `knowhow` / `comment` / `notification`。

`comment` と `notification` の `post_type` は、イベントが `1`、ノウハウが `2`(`y_coco/db.py` の `POST_TYPE_EVENT` / `POST_TYPE_KNOWHOW`)。
`post_id` は対応する投稿の `id` を指す(複数テーブルを参照するため外部キーは付けていない)。

## 通知のしくみ

コメントを保存してコミットした後、blinker のシグナル `comment-posted` を送る(`event/comment.py` と `knowhow/kh_comment.py`)。
`user/account/notification.py` がこれを受け取り、投稿者本人以外からのコメントなら `notification` に登録する。
`app.py` が `notification` モジュールを import してシグナルの受信を有効にしている。

## テスト

    pytest

pytest が「アプリケーション制御」などで動かない環境では、標準の unittest で実行できる。

    python -m unittest discover -s tests -p "*_test.py"

## 未使用・要整理のファイル

- `y_coco/admin/account/` の `account_list.py` `user_detail.py` `user_delete.py` `user_search.py` と、
  `y_coco/admin/event/admin-delete.py`、`y_coco/admin/knowhow/admin-kh-delete.py` は、現在 `admin_views.py` から使われていない
  (`admin_views.py` 内で同等の処理を実装している)。
  これらは `from db import get_connection` と書かれており、パッケージ構成(`y_coco.db`)と合っていない。使う場合は import を直す。
- `user/account/` の `register.py` `edit.py` `myposts.py` `delete.py` `notification_check.py` が持つ Blueprint とルートは登録されておらず、`user_views.py` のルートが使われる。
- `kh_post.py` / `kh_comment.py` はファイル名にハイフンを含まない形に統一済み。

## 既知の注意点

- 画像サイズの上限が場所によって異なる。`validation.py` は 3MB、`config.py` の `MAX_CONTENT_LENGTH` はフォーム全体で 2MB(超えると 413 エラー)、イベント投稿画面の表記は 1MB。
  どの値に揃えるか決めて、`validation.py` / `config.py` / テンプレートの表記を合わせること。
- 本番では `SECRET_KEY` と DB の接続情報を必ず環境変数で指定する。