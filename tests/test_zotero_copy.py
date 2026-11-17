"""Copying the Zotero database safely while Zotero may be writing it."""

import os
import shutil
import sqlite3
import subprocess
import sys

import pytest
from zotero_fixture import ZoteroFixture

from chitragupta_importer.sources import zotero
from chitragupta_importer.sources.zotero import UnreadableLibrary, read_library

# A writer that dies mid-transaction after spilling uncommitted pages into the
# database file, leaving a hot rollback journal beside it (journal_mode=delete).
_DYING_WRITER = """
import os, sqlite3, sys
conn = sqlite3.connect(sys.argv[1], isolation_level=None)
conn.execute("PRAGMA journal_mode = DELETE")
conn.execute("PRAGMA cache_size = 1")
conn.execute("BEGIN")
conn.execute("UPDATE items SET key = 'DIRTYKEY'")
conn.execute("CREATE TABLE padding (blob)")
for _ in range(200):
    conn.execute("INSERT INTO padding VALUES (randomblob(4000))")
os._exit(0)
"""


def _library(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA")
    return fx.build()


def _state(paths):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}


def test_hot_journal_is_copied_beside_the_copy(tmp_path):
    data_dir = _library(tmp_path)
    database = data_dir / "zotero.sqlite"
    subprocess.run([sys.executable, "-c", _DYING_WRITER, str(database)], check=True)
    journal = data_dir / "zotero.sqlite-journal"
    assert journal.exists()
    before = _state((database, journal))
    lib = read_library(data_dir)
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMAAAA"]
    assert _state((database, journal)) == before


def _writing_copy(monkeypatch, writes):
    """Make each copy of the database also change the original, `writes` times in all."""
    real_copy = shutil.copyfile
    calls = []

    def copy(src, dst):
        result = real_copy(src, dst)
        if src.name == "zotero.sqlite":
            calls.append(src)
            if len(calls) <= writes:
                conn = sqlite3.connect(src)
                conn.execute("UPDATE items SET key = ?", (f"ITEM{len(calls):04d}",))
                conn.commit()
                conn.close()
                mtime = src.stat().st_mtime_ns + len(calls) * 10**9
                os.utime(src, ns=(mtime, mtime))
        return result

    monkeypatch.setattr(zotero.shutil, "copyfile", copy)
    return calls


def test_database_changing_during_the_copy_is_copied_again(tmp_path, monkeypatch):
    data_dir = _library(tmp_path)
    calls = _writing_copy(monkeypatch, writes=2)
    lib = read_library(data_dir)
    assert len(calls) == 3
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEM0002"]


def test_database_that_never_settles_is_refused(tmp_path, monkeypatch):
    data_dir = _library(tmp_path)
    calls = _writing_copy(monkeypatch, writes=99)
    with pytest.raises(UnreadableLibrary, match=r"zotero\.sqlite.*kept changing"):
        read_library(data_dir)
    assert len(calls) == 3
