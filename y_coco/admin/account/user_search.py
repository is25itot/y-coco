"""user_search.py : アカウント検索機能 (M-FL7, M-FL8, M-FL9)

入力された文章を形態素解析(Janome)で単語に分割し、OR検索でアカウントを探す。
該当なしの場合は error_code = 1 とエラーメッセージを返す。

Janome が未インストールの場合は、空白区切りで単語に分割する。
    pip install janome

前提: db.py に get_connection() があり、pymysql(DictCursor)の接続を返すこと。
"""

ERROR_NOT_FOUND = 1
MSG_NOT_FOUND = "該当するものがありませんでした。"
MSG_EMPTY_KEYWORD = "検索ワードを入力してください。"

_tokenizer = None


def _open_connection():
    from db import get_connection
    return get_connection()


def _janome_tokens(text):
    """Janomeで分割した単語のリストを返す。Janome未導入なら None。"""
    global _tokenizer
    try:
        from janome.tokenizer import Tokenizer
    except ImportError:
        return None
    if _tokenizer is None:
        _tokenizer = Tokenizer()  # 初期化が重いので使い回す

    tokens = []
    for token in _tokenizer.tokenize(text):
        pos = token.part_of_speech.split(",")[0]
        if pos in ("助詞", "記号"):  # 検索に不要な品詞は除外
            continue
        tokens.append(token.surface)
    return tokens


def split_words(text):
    """文章を単語(形態素)のリストに分割する(重複・空は除く)。"""
    if text is None:
        return []
    text = text.strip()
    if not text:
        return []

    tokens = _janome_tokens(text)
    if tokens is None:
        tokens = text.split()  # 半角/全角空白で分割

    words = []
    for token in tokens:
        token = token.strip()
        if token and token not in words:
            words.append(token)
    return words


def escape_like(word):
    """LIKE検索用に % _ とエスケープ文字 ! をエスケープする。"""
    return word.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _response(words, results, error_code, error_message):
    return {
        "words": words,
        "results": results,
        "has_result": bool(results),
        "error_code": error_code,
        "error_message": error_message,
    }


def search_accounts(keyword, db_conn=None):
    """ユーザーネームをOR検索する。

    Returns:
        {"words": list, "results": list, "has_result": bool,
         "error_code": 0 or 1, "error_message": str or None}
        error_code = 1 の場合は admin の検索画面へ戻し、入力欄を空にする。
    """
    words = split_words(keyword)
    if not words:
        return _response(words, [], ERROR_NOT_FOUND, MSG_EMPTY_KEYWORD)

    conditions = " OR ".join(["username LIKE %s ESCAPE '!'"] * len(words))
    sql = (
        "SELECT id, username, imagepath, admin_flg FROM users WHERE "
        + conditions
        + " ORDER BY id DESC"
    )
    params = tuple("%" + escape_like(word) + "%" for word in words)

    own_connection = db_conn is None
    conn = db_conn if db_conn is not None else _open_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        if own_connection:
            conn.close()

    results = list(rows) if rows else []
    if not results:
        return _response(words, [], ERROR_NOT_FOUND, MSG_NOT_FOUND)
    return _response(words, results, 0, None)
