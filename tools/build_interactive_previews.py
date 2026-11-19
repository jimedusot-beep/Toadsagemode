"""Build isolated, interactive HTML previews from exact reviewed app templates.

Only the trusted and verified Tasks, Notes, Flashcards static templates run.
All preview data lives only in the sandboxed frame's in-memory Map.
No arbitrary model code is accepted, no Docker or cloud host is involved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from toad_core.app_studio import AppStudio

KINDS = ("tasks", "notes", "flashcards")
THEMES = ("forest", "midnight")

ORIGINAL_CSP = (
    '<meta http-equiv="Content-Security-Policy" '
    'content="default-src \'none\'; script-src \'self\'; style-src \'self\'; '
    'connect-src \'none\'; base-uri \'none\'; form-action \'none\'">'
)
PREVIEW_CSP = (
    '<meta http-equiv="Content-Security-Policy" '
    'content="default-src \'none\'; script-src \'unsafe-inline\'; '
    'style-src \'unsafe-inline\'; connect-src \'none\'; '
    'img-src \'none\'; font-src \'none\'; frame-src \'none\'; '
    'object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
)

# This is intentionally in the same classic-script scope as the reviewed
# application JS. It shadows the normally inaccessible localStorage global
# within a sandboxed opaque origin and provides *ephemeral* preview storage.
# window.localStorage remains prohibited in the iframe by sandbox policy.
IN_MEMORY_STORAGE = """const localStorage = (() => {
  'use strict';
  const values = new Map();
  return Object.freeze({
    getItem(key) {
      const name = String(key);
      return values.has(name) ? values.get(name) : null;
    },
    setItem(key, value) {
      const name = String(key);
      const text = String(value);
      if (name.length > 100 || text.length > 250000 || values.size > 10) {
        throw new Error('Preview storage capacity reached');
      }
      values.set(name, text);
    }
  });
})();
"""

# Only the parent window may change the preview's visible title.
# Never treat any message as code, URLs, secrets, or HTML.
TITLE_BRIDGE = """window.addEventListener('message', event => {
  'use strict';
  if (event.source !== window.parent) return;
  const input = event.data;
  if (!input || input.type !== 'toad-reviewed-preview-title-v1' ||
      typeof input.title !== 'string' || !input.title.trim() ||
      input.title.length > 80 || /[\\u0000-\\u001f\\u007f]/.test(input.title)) return;
  const heading = document.querySelector('h1');
  if (heading) heading.textContent = input.title.trim();
  document.title = input.title.trim();
});
"""

BANNER = (
    '<p class="toad-preview-warning" role="status">'
    'LIVE DEMO / Temporary in-memory data. Reload or reset discards changes. '
    'No app data is saved or uploaded.</p>'
)
BANNER_CSS = """
.toad-preview-warning{
  border:1px solid #d6b47a;border-radius:10px;background:#41301a;
  color:#fff0d2;padding:10px 12px;font-weight:750;font-size:.78rem;
  max-width:760px;margin:10px auto;
}
"""

def make_preview_html(kind: str, theme: str) -> str:
    if kind not in KINDS or theme not in THEMES:
        raise ValueError("Only exact reviewed kind/theme combinations may be previewed")
    sources = AppStudio._templates(
        "preview-" + kind + "-" + theme, "Interactive " + kind.title() + " Preview", theme, kind
    )
    page = sources["index.html"]
    script = sources["app.js"]
    style = sources["styles.css"]
    if page.count(ORIGINAL_CSP) != 1:
        raise ValueError("Reviewed template CSP anchor has changed")
    if page.count('<link rel="stylesheet" href="styles.css">') != 1:
        raise ValueError("Reviewed CSS anchor has changed")
    if page.count('<script src="app.js" defer></script>') != 1:
        raise ValueError("Reviewed JS anchor has changed")
    if page.count("<body data-theme=") != 1:
        raise ValueError("Reviewed body anchor has changed")
    if script.count("Saved locally on this device.") != 1:
        raise ValueError("Reviewed storage status anchor has changed")
    if any(token in script.lower() for token in ("</script", "<!--")):
        raise ValueError("Unexpected script delimiter in reviewed app source")
    if "</style" in style.lower():
        raise ValueError("Unexpected style delimiter in reviewed app source")
    script = script.replace(
        "Saved locally on this device.",
        "Preview only: changes will disappear when the preview resets."
    )
    page = page.replace(ORIGINAL_CSP, PREVIEW_CSP)
    page = page.replace(
        '<link rel="stylesheet" href="styles.css">',
        "<style>\n" + style + BANNER_CSS + "\n</style>"
    )
    page = page.replace(
        '<script src="app.js" defer></script>',
        "<script>\n" + IN_MEMORY_STORAGE + "\n" + script + "\n" +
        TITLE_BRIDGE + "\n</script>"
    )
    page = page.replace(
        "<body data-theme=", "<body data-preview-sandbox=\"reviewed-template-v1\" data-theme="
    )
    marker = '<div class="shell">'
    if page.count(marker) != 1:
        raise ValueError("Reviewed page layout has changed")
    page = page.replace(marker, BANNER + "\n  " + marker, 1)
    return page


def preview_documents() -> dict[str, str]:
    return {
        "previews/" + kind + "-" + theme + "/index.html": make_preview_html(kind, theme)
        for kind in KINDS for theme in THEMES
    }


def write_previews(root: Path) -> dict:
    root = Path(root)
    previews = preview_documents()
    records = {}
    for path, text in previews.items():
        destination = root / path
        if root.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
            raise ValueError("Cannot write sandbox preview via symlink")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        records[path] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "schema": "toad-reviewed-interactive-previews-v1",
        "previews": records,
        "browser_sandbox": "allow-scripts",
        "allow_same_origin": False,
        "source": "trusted_templates_only",
        "model_generated": False,
        "preview_persists_data": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_previews(args.output), indent=2))
