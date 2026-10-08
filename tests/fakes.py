"""テスト共通ヘルパー: DB接続の偽物(Fake)とモジュール読み込み関数。

DB(XAMPP)を起動しなくてもテストできるよう、cursor / commit / rollback の
呼び出しを記録するだけの接続オブジェクトを用意している。
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # y-coco/


def load_module(relative_path, name):
    """ファイルパスからモジュールを読み込む。

    admin-delete.py のようにハイフンを含むファイル名は通常の import が
    使えないため、importlib でパス指定して読み込む。
    """
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self._conn.executed.append((normalized, params))
        result = self._conn.responder(normalized, params) or {}
        self._rows = result.get("rows", [])
        self.rowcount = result.get("rowcount", 1)
        return self.rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class FakeConnection:
    """responder(sql, params) -> {"rows": [...], "rowcount": n} を返す関数。
    例外を投げさせたい場合は responder の中で raise する。
    """

    def __init__(self, responder=None):
        self.responder = responder or (lambda sql, params: {})
        self.executed = []   # [(正規化したSQL, params), ...]
        self.events = []     # "commit" / "rollback" の発生順
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")

    def close(self):
        self.closed = True

    @property
    def committed(self):
        return "commit" in self.events

    @property
    def rolled_back(self):
        return "rollback" in self.events

    def sqls(self):
        return [sql for sql, _ in self.executed]

    def executed_starting_with(self, prefix):
        return [(s, p) for s, p in self.executed if s.startswith(prefix)]