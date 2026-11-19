"""Create two source-only, upload-ready Netlify Drop ZIP artifacts at $0.

Trusted templates only. Refuse stale browser catalog. Never embed secrets,
make AI calls, publish a site, or execute AI-authored web code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from toad_core.app_studio import AppStudio


STUDIO_DIR = ROOT / "free-studio"
ARTIFACT_DIR = ROOT / "dist"
PREVIEW_NAME = "Toad-Sage-Flashcards-iPad.zip"
STUDIO_NAME = "Toad-Sage-Free-App-Studio.zip"
STUDIO_FILES = ("index.html", "styles.css", "app.js", "templates.json", "v2.css", "v2.js")
TEMPLATES = ROOT / "toad_core" / "studio_templates"


def expected_catalog():
    base = (TEMPLATES / "styles.css").read_text(encoding="utf-8")
    content = {}
    for kind in ("tasks", "notes", "flashcards"):
        label = "app" if kind == "tasks" else kind
        html_path = "tasks.html" if kind == "tasks" else kind + ".html"
        css = base
        if kind != "tasks":
            css += "\n" + (TEMPLATES / (kind + ".css")).read_text(encoding="utf-8")
        content[kind] = {
            "html": (TEMPLATES / html_path).read_text(encoding="utf-8"),
            "css": css,
            "js": (TEMPLATES / (label + ".js")).read_text(encoding="utf-8"),
        }
    return {"schema": "toad-free-studio-templates-v1", "templates": content}


def validate_catalog():
    source = STUDIO_DIR / "templates.json"
    if source.is_symlink() or not source.is_file():
        raise ValueError("Missing or symlinked reviewed templates.json")
    with source.open(encoding="utf-8") as file:
        catalog = json.load(file)
    if catalog != expected_catalog():
        raise ValueError("Browser template catalog differs from original reviewed sources")
    return {"status": "catalog_matches_reviewed_sources", "kinds": sorted(catalog["templates"])}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(out=ARTIFACT_DIR):
    info = validate_catalog()
    out = Path(out)
    if out.is_symlink() or (out.exists() and not out.is_dir()):
        raise ValueError("Output location must be an ordinary directory")
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="toad-flashcards-bundle-") as private:
        built = AppStudio(private).create(
            "ipad-flashcards-demo", title="Toad Sage Flashcards",
            kind="flashcards", theme="forest"
        )
        preview = out / PREVIEW_NAME
        shutil.copyfile(built["zip"], preview)
        with zipfile.ZipFile(preview) as archive:
            if set(archive.namelist()) != {
                "index.html", "styles.css", "app.js", "README.md", "build_report.json"
            }:
                raise ValueError("Preview ZIP contains unexpected files")
            report = json.loads(archive.read("build_report.json"))
            if report["status"] != "generated_unverified" or report["deployed"] is not False:
                raise ValueError("Preview report must remain unverified/undeployed")
    bundle = out / STUDIO_NAME
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in STUDIO_FILES:
            path = STUDIO_DIR / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Missing or symlinked studio asset: " + name)
            archive.write(path, name)
    with zipfile.ZipFile(bundle) as archive:
        if archive.namelist() != list(STUDIO_FILES):
            raise ValueError("Browser studio bundle names are invalid")

    # Source-only folders are uploaded to GitHub Actions as a single
    # ready-to-upload outer ZIP per app; avoid confusing ZIP-in-ZIP downloads
    # on mobile Safari, and do not modify any existing Netlify project.
    flash_folder = out / "flashcards-site"
    studio_folder = out / "browser-studio"
    for folder in (flash_folder, studio_folder):
        if folder.is_symlink():
            raise ValueError("Refuse linked static artifact output")
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(mode=0o700, parents=True)
    with zipfile.ZipFile(preview) as archive:
        for name in ("index.html", "styles.css", "app.js", "README.md", "build_report.json"):
            (flash_folder / name).write_bytes(archive.read(name))
    for name in STUDIO_FILES:
        shutil.copyfile(STUDIO_DIR / name, studio_folder / name)
    results = {
        "schema": "toad-static-preview-artifacts-v1",
        "model_called": False,
        "paid_requests": 0,
        "deployed": False,
        "requires_user_upload_to_netlify": True,
        "catalog": info,
        "artifacts": [
            {"name": preview.name, "bytes": preview.stat().st_size, "sha256": _sha(preview)},
            {"name": bundle.name, "bytes": bundle.stat().st_size, "sha256": _sha(bundle)},
        ],
    }
    (out / "artifact_report.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    info = validate_catalog() if args.check_only else build(args.output)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
