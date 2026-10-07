"""単体テスト共通のヘルパー。

- load_module : ファイル名にハイフンを含むモジュールも読み込めるローダー。
                読み込み中だけ db / validation をスタブに差し替える
                (本物の db.py / validation.py には依存せず、DBにも接続しない)。
- FakeConnection / FakeCursor : DB接続の代役。呼び出し順 (calls) と SQL (executed) を記録する。
- FakeForm : validation.py のフォームの代役。
"""
import importlib.util
import os
import sys
import types
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_module(relative_path, module_name, form_names):
    """relative_path (y-coco からの相対パス) のファイルをモジュールとして読み込む。"""
    stub_db = types.ModuleType("db")

    def _no_db():
        raise RuntimeError("テスト中に本物のDBへ接続しようとしました")

    stub_db.get_connection = _no_db

    stub_validation = types.ModuleType("validation")
    for name in form_names:
        setattr(stub_validation, name, type(name, (), {}))

    path = os.path.join(ROOT, *relative_path.split("/"))
    with mock.patch.dict(sys.modules, {"db": stub_db, "validation": stub_validation}):
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # Blueprint が root_path を解決できるように
        spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.lastrowid = None
        self.rowcount = 0
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.conn.executed.append((normalized, params))
        if normalized.startswith("INSERT"):
            if self.conn.insert_error:
                raise self.conn.insert_error
            self.lastrowid = self.conn.lastrowid
            self.rowcount = self.conn.insert_rowcount
        elif normalized.startswith("SELECT"):
            self._row = self.conn.select_rows.pop(0) if self.conn.select_rows else None

    def fetchone(self):
        return self._row


class FakeConnection:
    """select_rows : SELECT ごとに fetchone が返す値 (先頭から順に使う)。"""

    def __init__(
        self,
        select_rows=None,
        lastrowid=10,
        insert_rowcount=1,
        insert_error=None,
        commit_error=None,
    ):
        self.select_rows = list(select_rows or [])
        self.lastrowid = lastrowid
        self.insert_rowcount = insert_rowcount
        self.insert_error = insert_error
        self.commit_error = commit_error
        self.calls = []
        self.executed = []

    def begin(self):
        self.calls.append("begin")

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.calls.append("commit")
        if self.commit_error:
            raise self.commit_error

    def rollback(self):
        self.calls.append("rollback")

    def close(self):
        self.calls.append("close")

    def statements(self, prefix):
        """prefix で始まる SQL の (sql, params) だけを返す。"""
        return [(s, p) for s, p in self.executed if s.startswith(prefix)]


class FakeForm:
    def __init__(self, valid=True, errors=None):
        self._valid = valid
        self.errors = errors or {}

    def validate_on_submit(self):
        return self._valid