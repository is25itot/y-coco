"""単体テスト用の疑似DB接続 (XAMPP を起動しなくてもテストできる)。

使い方:
    conn = FakeConnection(rules=[
        ("SELECT id FROM users", {"rows": [{"id": 1}]}),   # SQLにこの文字列が含まれたらこの結果を返す
        ("INSERT INTO users",    {"rowcount": 0}),
        ("UPDATE users",         RuntimeError("DBエラー")),  # 例外を渡すと execute で送出される
    ])
    - rules は上から順に調べ、最初に当てはまったものを使う (当てはまらなければ rowcount=1, rows=[])
    - 結果をリストで渡すと、1回呼ぶごとに先頭から消費する (最後の1件は繰り返し使う)
    - conn.events   : begin / commit / rollback / close の呼び出し履歴
    - conn.executed : 実行された (SQL, params) の履歴 (SQLの空白は1つに整形済み)
"""
import logging
import os
import sys

# 異常系テストで出る logger.exception のログを表示しない
logging.disable(logging.CRITICAL)

# テスト対象 (y_coco パッケージ) を import できるようにする
# tests/ の1つ上 (= y_coco/ と tests/ が並ぶフォルダ) だけを検索パスに追加する
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.rowcount = 0
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        self._conn.executed.append((sql, params))
        response = self._conn.respond(sql)
        if isinstance(response, Exception):
            raise response
        self.rowcount = response.get("rowcount", 1)
        self._rows = list(response.get("rows", []))
        return self.rowcount

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        rows, self._rows = self._rows, []
        return rows


class FakeConnection:
    def __init__(self, rules=None):
        self.rules = list(rules or [])
        self.events = []
        self.executed = []

    @property
    def closed(self):
        return "close" in self.events

    def respond(self, sql):
        for needle, response in self.rules:
            if needle in sql:
                if isinstance(response, list):
                    return response.pop(0) if len(response) > 1 else response[0]
                return response
        return {"rowcount": 1, "rows": []}

    def cursor(self):
        return FakeCursor(self)

    def begin(self):
        self.events.append("begin")

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.events.append("close")

    # --- テストで使う補助 ---
    def sqls(self, needle):
        """needle を含む SQL の (sql, params) だけを返す。"""
        return [(s, p) for s, p in self.executed if needle in s]