"""Ensure V3 interactive previews are derived only from reviewed, tested sources."""
from pathlib import Path
import tempfile
import unittest

from toad_core.app_studio import AppStudio
from tools.build_interactive_previews import (
    KINDS, THEMES, ORIGINAL_CSP, PREVIEW_CSP, preview_documents,
    make_preview_html, write_previews,
)


class TrustedPreviewTests(unittest.TestCase):
    def test_six_exact_reviewed_kind_theme_combinations(self):
        documents = preview_documents()
        self.assertEqual(
            set(documents),
            {"previews/"+k+"-"+t+"/index.html" for k in KINDS for t in THEMES}
        )
        for kind in KINDS:
            for theme in THEMES:
                with self.subTest(kind=kind,theme=theme):
                    html = make_preview_html(kind, theme)
                    self.assertEqual(html.count(PREVIEW_CSP),1)
                    self.assertNotIn(ORIGINAL_CSP,html)
                    self.assertIn('data-preview-sandbox="reviewed-template-v1"',html)
                    self.assertIn('data-theme="'+theme+'"',html)
                    self.assertIn('Temporary in-memory data',html)
                    self.assertIn('const localStorage = (() => {',html)
                    self.assertIn('event.source !== window.parent',html)
                    self.assertIn('No app data is saved or uploaded.',html)
                    self.assertNotIn('src="app.js"',html)
                    self.assertNotIn('href="styles.css"',html)
                    self.assertNotIn('allow-same-origin',html)
                    self.assertEqual(html.count('<script>'),1)
                    self.assertEqual(html.count('</script>'),1)
                    # Executable preview inherits reviewed template JS,
                    # plus an explicitly auditable, ephemeral storage bridge.
                    app = AppStudio._templates(
                        "preview-"+kind+"-"+theme,
                        "Interactive "+kind.title()+" Preview",theme,kind
                    )
                    js = app["app.js"].replace(
                        "Saved locally on this device.",
                        "Preview only: changes will disappear when the preview resets."
                    )
                    self.assertIn(js,html)

    def test_unsupported_types_rejected_and_output_hashes_stable(self):
        for kind,theme in (("chatbot","forest"),("flashcards","custom"),("../bad","midnight")):
            with self.assertRaisesRegex(ValueError,"Only exact reviewed"):
                make_preview_html(kind,theme)
        with tempfile.TemporaryDirectory() as root:
            result = write_previews(Path(root))
            self.assertEqual(len(result["previews"]),6)
            self.assertFalse(result["allow_same_origin"])
            self.assertFalse(result["model_generated"])
            self.assertFalse(result["preview_persists_data"])
            import hashlib
            for path,digest in result["previews"].items():
                self.assertEqual(hashlib.sha256((Path(root)/path).read_bytes()).hexdigest(),digest)


if __name__ == "__main__":
    unittest.main()
