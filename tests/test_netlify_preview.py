"""Review-only checks: the Netlify preview is exactly the trusted app template.

No Netlify request, browser execution, deployment, or untrusted code runs here.
"""
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "toad_core" / "studio_templates"
PREVIEW = ROOT / "netlify-preview"


class NetlifyTaskPreviewTests(unittest.TestCase):
    def test_source_matches_reviewed_app_template(self):
        source = (TEMPLATE / "tasks.html").read_text(encoding="utf-8")
        expected = source.replace("{{TITLE}}", "Toad Sage Tasks").replace("{{THEME}}", "forest")
        self.assertEqual((PREVIEW / "index.html").read_text(encoding="utf-8"), expected)
        for name in ("app.js", "styles.css"):
            with self.subTest(name=name):
                self.assertEqual((PREVIEW / name).read_bytes(), (TEMPLATE / name).read_bytes())

    def test_only_explicit_published_static_files_exist(self):
        self.assertEqual(
            {p.name for p in PREVIEW.iterdir() if p.is_file()},
            {"index.html", "app.js", "styles.css", "netlify.toml", "robots.txt"},
        )
        self.assertFalse(any(p.is_symlink() for p in PREVIEW.iterdir()))
        self.assertNotIn("<script>", (PREVIEW / "index.html").read_text(encoding="utf-8"))

    def test_no_build_execution_remote_api_or_writable_endpoint(self):
        config = tomllib.loads((PREVIEW / "netlify.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["build"]["publish"], ".")
        self.assertEqual(config["build"]["command"], "")
        self.assertNotIn("functions", config)
        self.assertNotIn("plugins", config)
        self.assertNotIn("redirects", config)
        headers = config["headers"][0]["values"]
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("connect-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")


if __name__ == "__main__":
    unittest.main()
