"""Pengujian unit dan integrasi SnapDiff menggunakan unittest bawaan Python."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from snapdiff.__main__ import main
from snapdiff.core import SnapDiffError, compare_files, load_snapshot, make_snapshot, render_text, scan_folder


class SnapDiffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()

    def test_detects_added_removed_modified_and_unchanged(self):
        (self.project / "changed.txt").write_text("abc", encoding="utf-8")
        (self.project / "deleted.txt").write_text("delete", encoding="utf-8")
        (self.project / "same.txt").write_text("same", encoding="utf-8")
        before = scan_folder(self.project)
        (self.project / "changed.txt").write_text("xyz", encoding="utf-8")  # ukuran sama, hash berbeda
        (self.project / "deleted.txt").unlink()
        (self.project / "new.txt").write_text("new", encoding="utf-8")
        report = compare_files(before, scan_folder(self.project))
        self.assertEqual(report["summary"], {"added": 1, "removed": 1, "modified": 1, "unchanged": 1})
        self.assertEqual(report["added"], ["new.txt"])
        self.assertEqual(report["removed"], ["deleted.txt"])
        self.assertEqual(report["modified"], ["changed.txt"])
        self.assertIn("~ changed.txt", render_text(report))

    def test_nested_unicode_and_empty_file(self):
        folder = self.project / "dokumen"
        folder.mkdir()
        (folder / "résumé.txt").write_text("", encoding="utf-8")
        result = scan_folder(self.project)
        self.assertEqual(result["dokumen/résumé.txt"]["size"], 0)
        self.assertEqual(len(result["dokumen/résumé.txt"]["sha256"]), 64)

    def test_default_and_custom_exclusions(self):
        (self.project / ".git").mkdir()
        (self.project / ".git" / "config").write_text("git")
        (self.project / "notes.log").write_text("log")
        (self.project / "keep.txt").write_text("keep")
        result = scan_folder(self.project, ("*.log",))
        self.assertEqual(list(result), ["keep.txt"])

    def test_snapshot_saved_inside_folder_is_skipped(self):
        path = self.project / "snapshot.json"
        (self.project / "hello.txt").write_text("hello")
        self.assertEqual(main(["snapshot", str(self.project), "-o", str(path)]), 0)
        self.assertNotIn("snapshot.json", load_snapshot(path)["files"])
        self.assertEqual(main(["snapshot", str(self.project), "-o", str(path)]), 0)
        self.assertNotIn("snapshot.json", load_snapshot(path)["files"])

    def test_compare_cli_json_and_exit_codes(self):
        (self.project / "hello.txt").write_text("hello")
        path = self.root / "snapshot.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["snapshot", str(self.project), "-o", str(path)]), 0)
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            self.assertEqual(main(["compare", str(path), str(self.project), "--format", "json", "--fail-on-change"]), 0)
        self.assertEqual(json.loads(capture.getvalue())["summary"]["unchanged"], 1)
        (self.project / "hello.txt").write_text("changed")
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            self.assertEqual(main(["compare", str(path), str(self.project), "--format", "json", "--fail-on-change"]), 1)
        self.assertEqual(json.loads(capture.getvalue())["modified"], ["hello.txt"])

    def test_compare_report_output_is_skipped(self):
        (self.project / "keep.txt").write_text("keep")
        snapshot = self.root / "snapshot.json"
        report = self.project / "report.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["snapshot", str(self.project), "-o", str(snapshot)]), 0)
            self.assertEqual(main(["compare", str(snapshot), str(self.project), "-o", str(report)]), 0)
            self.assertEqual(main(["compare", str(snapshot), str(self.project), "-o", str(report)]), 0)
        self.assertIn("Tidak ada perubahan", report.read_text())

    def test_invalid_manifest_rejected(self):
        manifest = self.root / "bad.json"
        manifest.write_text('{"format_version": 1, "excludes": [], "files": {"../bad": {"size": 1, "sha256": "' + "0" * 64 + '"}}}')
        with self.assertRaises(SnapDiffError):
            load_snapshot(manifest)
        capture = io.StringIO()
        with contextlib.redirect_stderr(capture):
            self.assertEqual(main(["compare", str(manifest), str(self.project)]), 2)
        self.assertIn("path tidak valid", capture.getvalue())

    def test_nonexistent_folder_error(self):
        with self.assertRaises(SnapDiffError):
            scan_folder(self.root / "missing")

    def test_symlinks_are_skipped(self):
        outside = self.root / "outside.txt"
        outside.write_text("secret")
        link = self.project / "outside.txt"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink tidak didukung pada lingkungan ini")
        self.assertEqual(scan_folder(self.project), {})

    def test_empty_project(self):
        self.assertEqual(make_snapshot(self.project)["files"], {})
        report = compare_files({}, {})
        self.assertEqual(report["summary"]["added"], 0)
        self.assertIn("Tidak ada perubahan", render_text(report))

    def test_reject_overwrite_manifest_with_report(self):
        path = self.root / "snapshot.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["snapshot", str(self.project), "-o", str(path)]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["compare", str(path), str(self.project), "-o", str(path)]), 2)
        self.assertEqual(load_snapshot(path)["format_version"], 1)


if __name__ == "__main__":
    unittest.main()
