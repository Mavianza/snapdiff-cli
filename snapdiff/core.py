"""Pemindaian folder dan perbandingan snapshot berbasis SHA-256."""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

VERSION = 1
DEFAULT_EXCLUDES = (".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SnapDiffError(Exception):
    """Kesalahan masukan atau pemindaian yang bisa ditampilkan ke pengguna."""


def _is_excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    parts = PurePosixPath(relative).parts
    for pattern in patterns:
        if not pattern:
            continue
        if fnmatch.fnmatchcase(relative, pattern):
            return True
        if "/" not in pattern and any(fnmatch.fnmatchcase(part, pattern) for part in parts):
            return True
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_folder(root: Path, excludes: tuple[str, ...] = (), skip_paths: tuple[Path, ...] = ()) -> dict[str, dict[str, Any]]:
    """Kembalikan manifest file biasa. Symlink dilewati untuk menghindari traversal."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise SnapDiffError(f"Folder tidak ditemukan: {root}")

    patterns = DEFAULT_EXCLUDES + excludes
    skip = {path.expanduser().resolve() for path in skip_paths}
    result: dict[str, dict[str, Any]] = {}

    def on_error(error: OSError) -> None:
        raise SnapDiffError(f"Gagal membaca folder: {error}")

    try:
        for current, directories, filenames in os.walk(root, topdown=True, followlinks=False, onerror=on_error):
            folder = Path(current)
            directories[:] = sorted(
                name for name in directories
                if not (folder / name).is_symlink()
                and not _is_excluded((folder / name).relative_to(root).as_posix(), patterns)
            )
            for name in sorted(filenames):
                path = folder / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink() or path.resolve() in skip or _is_excluded(relative, patterns):
                    continue
                if not path.is_file():
                    continue
                # Periksa ukuran sebelum/sesudah hashing untuk mendeteksi perubahan saat pemindaian.
                before = path.stat()
                digest = _sha256(path)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise SnapDiffError(f"File berubah saat dipindai: {relative}. Coba lagi.")
                result[relative] = {"sha256": digest, "size": after.st_size}
    except OSError as error:
        raise SnapDiffError(f"Gagal memindai folder: {error}") from error
    return dict(sorted(result.items()))


def make_snapshot(root: Path, excludes: tuple[str, ...] = (), skip_paths: tuple[Path, ...] = ()) -> dict[str, Any]:
    resolved = root.expanduser().resolve()
    return {
        "format_version": VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_folder": str(resolved),
        "excludes": list(excludes),
        "files": scan_folder(resolved, excludes, skip_paths),
    }


def save_json(path: Path, data: dict[str, Any]) -> None:
    """Tulis atomik untuk mencegah JSON terpotong saat proses gagal."""
    import tempfile

    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, prefix=".snapdiff-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, destination)
    except OSError as error:
        raise SnapDiffError(f"Gagal menyimpan {destination}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        with path.expanduser().open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SnapDiffError(f"Tidak dapat membaca snapshot: {error}") from error

    if not isinstance(data, dict) or data.get("format_version") != VERSION:
        raise SnapDiffError("Format atau versi snapshot tidak didukung.")
    files, excludes = data.get("files"), data.get("excludes")
    if not isinstance(files, dict) or not isinstance(excludes, list) or not all(isinstance(x, str) for x in excludes):
        raise SnapDiffError("Struktur snapshot tidak valid.")
    for name, info in files.items():
        if not isinstance(name, str) or not name or "\\" in name or name.startswith("/") or any(part in (".", "..") for part in name.split("/")):
            raise SnapDiffError("Snapshot mengandung path tidak valid.")
        if (not isinstance(info, dict) or not isinstance(info.get("size"), int)
                or isinstance(info.get("size"), bool) or info["size"] < 0
                or not isinstance(info.get("sha256"), str) or not SHA256_PATTERN.fullmatch(info["sha256"])):
            raise SnapDiffError(f"Metadata file tidak valid: {name}")
    return data


def compare_files(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, Any]:
    before_names, after_names = set(before), set(after)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)
    modified = sorted(name for name in before_names & after_names if before[name] != after[name])
    unchanged = len(before_names & after_names) - len(modified)
    return {
        "summary": {"added": len(added), "removed": len(removed), "modified": len(modified), "unchanged": unchanged},
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def render_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "SnapDiff — Hasil Perbandingan",
        f"Ditambah: {summary['added']} | Dihapus: {summary['removed']} | Diubah: {summary['modified']} | Tetap: {summary['unchanged']}",
    ]
    for key, label in (("added", "+"), ("removed", "-"), ("modified", "~")):
        lines.extend(f"{label} {name}" for name in report[key])
    if not any(report[key] for key in ("added", "removed", "modified")):
        lines.append("Tidak ada perubahan.")
    return "\n".join(lines) + "\n"
