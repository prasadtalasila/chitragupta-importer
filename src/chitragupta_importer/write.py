"""Writing the papers directory: atomic text writes, PDF copies, stray files."""

import os
import shutil
import tempfile
from collections.abc import Set
from pathlib import Path


def _replace_via_temp(dest: Path, fill) -> None:
    """Fill a temp file next to `dest`, fsync it, then move it onto `dest`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            fill(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, dest)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` as UTF-8 with LF line endings, all or nothing."""
    data = text.encode("utf-8")
    _replace_via_temp(path, lambda handle: handle.write(data))


def _same_bytes(a: Path, b: Path) -> bool:
    """Whether two files hold the same bytes, comparing sizes first."""
    if a.stat().st_size != b.stat().st_size:
        return False
    with a.open("rb") as file_a, b.open("rb") as file_b:
        for chunk in iter(lambda: file_a.read(1 << 16), b""):
            if chunk != file_b.read(len(chunk)):
                return False
    return True


def copy_pdf(src: Path, dest: Path) -> bool:
    """Copy the main PDF `src` to `dest`; False if `dest` already has its bytes."""
    if dest.is_file() and _same_bytes(src, dest):
        return False
    with src.open("rb") as source:
        _replace_via_temp(dest, lambda handle: shutil.copyfileobj(source, handle))
    return True


def unreferenced_files(files_dir: Path, written: Set[str]) -> list[str]:
    """Names of files in `files_dir` this import run did not write, sorted."""
    if not files_dir.is_dir():
        return []
    return sorted(
        entry.name for entry in files_dir.iterdir() if entry.is_file() and entry.name not in written
    )
