"""No-cost browser Studio packaging tests — no API requests or deployments."""
import json
from pathlib import Path
import tempfile
from unittest import mock
import unittest
import zipfile

from tools.build_free_studio_bundles import (
    STUDIO_DIR, PREVIEW_NAME, STUDIO_NAME,
    build, expected_catalog, validate_catalog,
)
from toad_core.schema import PackageError


class FreeStudioBundlesTests(unittest.TestCase):
    def test_catalog_matches_exact_reviewed_templates(self):
        info = validate_catalog()
        self.assertEqual(info["status"], "catalog_matches_reviewed_sources")
        self.assertEqual(info["kinds"], ["flashcards", "notes", "tasks"])
        with (STUDIO_DIR / "templates.json").open(encoding="utf-8") as file:
            bundled = json.load(file)
        self.assertEqual(bundled, expected_catalog())

    def test_cannot_silently_change_one_bundled_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            catalog = expected_catalog()
            catalog["templates"]["flashcards"]["js"] += "\nconsole.log('altered');\n"
            (directory / "templates.json").write_text(json.dumps(catalog))
            with mock.patch("tools.build_free_studio_bundles.STUDIO_DIR",directory):
                with self.assertRaisesRegex(ValueError, "differs"):
                    validate_catalog()

    def test_creates_exact_separate_deployable_zip_root_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = build(out)
            self.assertEqual(result["paid_requests"], 0)
            self.assertFalse(result["model_called"])
            self.assertFalse(result["deployed"])
            self.assertTrue(result["requires_user_upload_to_netlify"])
            self.assertEqual(len(result["artifacts"]), 2)
            with zipfile.ZipFile(out / PREVIEW_NAME) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"index.html","styles.css","app.js","README.md","build_report.json"})
                report = json.loads(archive.read("build_report.json"))
                self.assertEqual(report["kind"],"flashcards")
                self.assertEqual(report["status"],"generated_unverified")
                self.assertFalse(report["model_generated"])
                self.assertFalse(report["deployed"])
                self.assertIn("Toad Sage Flashcards",archive.read("index.html").decode())
            with zipfile.ZipFile(out / STUDIO_NAME) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"index.html","styles.css","app.js","templates.json"})
                self.assertIn("Free App Studio",archive.read("index.html").decode())
                self.assertEqual(json.loads(archive.read("templates.json")),expected_catalog())
            self.assertEqual(
                {p.name for p in (out/"flashcards-site").iterdir()},
                {"index.html","styles.css","app.js","README.md","build_report.json"}
            )
            self.assertEqual(
                {p.name for p in (out/"browser-studio").iterdir()},
                {"index.html","styles.css","app.js","templates.json"}
            )
            self.assertEqual(
                (out/"flashcards-site"/"index.html").read_bytes(),
                zipfile.ZipFile(out / PREVIEW_NAME).read("index.html")
            )
            metadata = json.loads((out/"artifact_report.json").read_text())
            self.assertEqual(metadata["artifacts"],result["artifacts"])

    def test_refuses_symlinked_output_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            real=root/"real"
            real.mkdir()
            linked=root/"linked"
            try:
                linked.symlink_to(real,target_is_directory=True)
            except (NotImplementedError,OSError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ValueError):
                build(linked)


if __name__ == "__main__":
    unittest.main()
