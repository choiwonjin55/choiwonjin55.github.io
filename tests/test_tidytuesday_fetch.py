import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError


SCRIPT = Path(__file__).resolve().parents[1] / ".agents/skills/tidytuesday-fetch/scripts/fetch_latest.py"
SPEC = importlib.util.spec_from_file_location("tidytuesday_fetch", SCRIPT)
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


class FetchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.week_dir = self.root / "2026/2026-03-17-test-data"
        self.files = [
            {"name": name, "download_url": f"https://example.com/{name}",
             "html_url": f"https://example.com/{name}"}
            for name in ("readme.md", "data.csv", "dictionary.md")
        ]

    def run_fetch(self, *, force=False, content=None, failure=None):
        args = SimpleNamespace(week="2026-03-17", target_date="2026-09-26",
                               out_root=str(self.root), force=force)

        def download(url):
            if url.endswith("dictionary.md"):
                if failure:
                    raise failure
                return b"Column definitions"
            return content if content is not None else b"name,value\na,1\nb,2\n"

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(fetch, "parse_args", return_value=args))
            stack.enter_context(patch.object(fetch, "list_week_files", return_value=self.files))
            stack.enter_context(patch.object(fetch, "request_text", return_value="# Test Data"))
            stack.enter_context(patch.object(fetch, "request_bytes", side_effect=download))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return fetch.main()

    def seed_workspace(self):
        for name, content in {
            "viz/code/01_main.py": "user analysis",
            "viz/figures/main.png": "user figure",
            "notes/interpretation.md": "user notes",
            "notes/summary.md": "old generated summary",
            "raw/obsolete.csv": "old raw data",
            "preview/obsolete.head.csv": "old preview",
            "manifest.json": "old manifest",
        }.items():
            path = self.week_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def snapshot(self):
        return {str(path.relative_to(self.week_dir)): path.read_bytes()
                for path in self.week_dir.rglob("*") if path.is_file()}

    def test_first_fetch_persists_final_paths_and_profiles(self):
        self.assertEqual(self.run_fetch(), 0)
        manifest = json.loads((self.week_dir / "manifest.json").read_text())
        self.assertEqual(manifest["local_root"], str(self.week_dir))
        for entry in manifest["files"]:
            self.assertTrue(Path(entry["path"]).is_file())
            if entry["type"] == "csv":
                self.assertEqual(entry["rows"], 2)
                self.assertEqual(entry["columns"], ["name", "value"])
                self.assertTrue(Path(entry["preview_file"]).is_file())
        for name in ("summary.md", "columns.md"):
            self.assertNotIn(".tidytuesday-", (self.week_dir / "notes" / name).read_text())
        self.assertFalse(list(self.week_dir.parent.glob(".tidytuesday-*")))

    def test_force_preserves_analysis_and_custom_notes(self):
        self.seed_workspace()
        before = self.snapshot()
        self.assertEqual(self.run_fetch(force=True), 0)
        after = self.snapshot()
        for name in ("viz/code/01_main.py", "viz/figures/main.png", "notes/interpretation.md"):
            self.assertEqual(after[name], before[name])
        self.assertNotEqual(after["notes/summary.md"], before["notes/summary.md"])
        self.assertNotIn("raw/obsolete.csv", after)
        self.assertNotIn("preview/obsolete.head.csv", after)
        self.assertIn("raw/data.csv", after)

    def test_existing_workspace_requires_force(self):
        self.seed_workspace()
        before = self.snapshot()
        with self.assertRaises(SystemExit):
            self.run_fetch()
        self.assertEqual(self.snapshot(), before)

    def test_network_failure_preserves_existing_workspace(self):
        self.seed_workspace()
        before = self.snapshot()
        with self.assertRaises(URLError):
            self.run_fetch(force=True, failure=URLError("interrupted download"))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(self.week_dir.parent.glob(".tidytuesday-*")))

    def test_profile_failure_does_not_publish_partial_workspace(self):
        with self.assertRaises(UnicodeDecodeError):
            self.run_fetch(content=b"\xff\xfeinvalid CSV")
        self.assertFalse(self.week_dir.exists())
        self.assertFalse(list(self.week_dir.parent.glob(".tidytuesday-*")))


if __name__ == "__main__":
    unittest.main()
