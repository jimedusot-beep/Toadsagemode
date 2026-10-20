"""Syntax-check inline page scripts without running them."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

page = Path(__file__).resolve().parents[1] / "index.html"
html = page.read_text(encoding="utf-8")
scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.DOTALL | re.IGNORECASE)
if not scripts:
    raise SystemExit("No inline scripts found")
for number, script in enumerate(scripts, 1):
    if not script.strip():
        continue
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"inline_{number}.js"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        if result.returncode:
            sys.stderr.write(result.stderr)
            raise SystemExit(result.returncode)
print(f"Checked {len(scripts)} inline script(s)")
