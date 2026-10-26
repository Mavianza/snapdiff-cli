"""Antarmuka perintah SnapDiff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import SnapDiffError, compare_files, load_snapshot, make_snapshot, render_text, save_json, scan_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snapdiff", description="Deteksi perubahan file dalam folder dengan snapshot SHA-256.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="Simpan kondisi folder saat ini ke JSON.")
    snapshot.add_argument("folder", type=Path, help="Folder yang akan dipindai.")
    snapshot.add_argument("-o", "--output", type=Path, required=True, help="Lokasi file snapshot JSON.")
    snapshot.add_argument("--exclude", action="append", default=[], metavar="POLA", help="Abaikan nama/path sesuai pola glob; boleh diulang.")

    compare = subparsers.add_parser("compare", help="Bandingkan snapshot dengan folder saat ini.")
    compare.add_argument("snapshot", type=Path, help="File snapshot JSON.")
    compare.add_argument("folder", type=Path, help="Folder saat ini.")
    compare.add_argument("--format", choices=("text", "json"), default="text", help="Format laporan.")
    compare.add_argument("-o", "--output", type=Path, help="Simpan laporan ke file (opsional).")
    compare.add_argument("--fail-on-change", action="store_true", help="Exit code 1 jika ditemukan perubahan (berguna untuk CI).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            output = args.output.expanduser().resolve()
            data = make_snapshot(args.folder, tuple(args.exclude), skip_paths=(output,))
            save_json(output, data)
            print(f"Snapshot disimpan: {output} ({len(data['files'])} file)")
            return 0

        snapshot_path = args.snapshot.expanduser().resolve()
        manifest = load_snapshot(snapshot_path)
        skipped = [snapshot_path]
        if args.output is not None:
            skipped.append(args.output.expanduser().resolve())
        current = scan_folder(args.folder, tuple(manifest["excludes"]), tuple(skipped))
        report = compare_files(manifest["files"], current)
        output_text = (json.dumps(report, indent=2, ensure_ascii=False) + "\n") if args.format == "json" else render_text(report)
        if args.output is not None:
            destination = args.output.expanduser().resolve()
            if destination == snapshot_path:
                raise SnapDiffError("Output laporan tidak boleh menimpa snapshot.")
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(output_text, encoding="utf-8")
            except OSError as error:
                raise SnapDiffError(f"Gagal menyimpan laporan: {error}") from error
            print(f"Laporan disimpan: {destination}")
        else:
            print(output_text, end="")
        has_changes = any(report[key] for key in ("added", "removed", "modified"))
        return 1 if args.fail_on_change and has_changes else 0
    except SnapDiffError as error:
        print(f"snapdiff: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
