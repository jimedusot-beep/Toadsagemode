"""Offline skill search and reported-evidence trust-boundary regressions."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.cli import dispatch, parser
from toad_core.engine import Engine
from toad_core.skills import SkillCatalog


def skill(name, desc, body):
    return f"---\nname: {name}\ndescription: {desc}\n---\n{body}"


class SkillDiscoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = SkillCatalog(self.root)
        self.first = self.catalog.register(
            skill("python-review", "Review Python code offline", "Scan imported Python before testing."),
            kind="workflow", permissions=["source.read"], compatibility={},
        )
        self.second = self.catalog.register(
            skill("offline-notes", "Capture markdown ideas", "Locally saved Python research notes."),
            kind="knowledge", permissions=[], compatibility={},
        )
        self.third = self.catalog.register(
            skill("python-helper", "Python utilities", "Examples using only the standard library."),
            kind="executable", permissions=[], compatibility={},
        )

    def test_ranked_search_filters_and_hides_body(self):
        hits = self.catalog.search_ranked("Python")
        self.assertEqual([x["name"] for x in hits], ["python-review", "python-helper", "offline-notes"])
        self.assertTrue(all("body" not in item for item in hits))
        self.assertEqual([x["name"] for x in self.catalog.search_ranked("python", kind="knowledge")], ["offline-notes"])
        self.assertEqual([x["name"] for x in self.catalog.search_ranked("python review")], ["python-review"])
        self.assertEqual([x["name"] for x in self.catalog.search_ranked("", limit=2)], ["python-review", "offline-notes"])
        self.assertEqual(self.catalog.search_ranked("unfindable"), [])
        self.assertFalse((self.root / "skills" / "index.sqlite3").exists())

    def test_untrusted_fts_syntax_does_not_become_query_operators(self):
        # Quotes/operators/punctuation never become raw FTS5 expressions.
        self.assertEqual(self.catalog.search_ranked('"python" OR malicious'), [])
        self.assertEqual([x["name"] for x in self.catalog.search_ranked("python")][:1], ["python-helper"])
        for query in ("***", "a" * 65, "one two three four five six seven eight nine ten eleven twelve thirteen"):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    self.catalog.search_ranked(query)
        for kwargs in ({"limit": 0}, {"limit": True}, {"kind": "unchecked"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.catalog.search_ranked("python", **kwargs)

    def test_old_sqlite_without_fts5_uses_offline_fallback(self):
        with patch("toad_core.skills.sqlite3.connect", side_effect=sqlite3.OperationalError("no such module: fts5")):
            hits = self.catalog.search_ranked("python", limit=2)
        self.assertEqual([x["name"] for x in hits], ["python-review", "python-helper"])

    def test_reported_evidence_is_inert_and_binds_exact_digest(self):
        entry = self.catalog.record_evidence(
            self.first["digest"], "scan", "passed", "Ruff scan reported no findings.",
            report_sha256="a" * 64,
        )
        self.assertEqual(entry["trust"], "self_reported_unverified")
        self.assertFalse(entry["grants_permissions"])
        self.assertFalse(entry["execution_performed"])
        self.assertEqual(entry["source_digest"], self.first["digest"])
        self.assertEqual(entry["report_sha256"], "a" * 64)
        persisted = json.loads((self.root / "skills" / "catalog.json").read_text("utf-8"))
        first = persisted["skills"][0]
        self.assertEqual(first["status"], "quarantined")
        self.assertFalse(first["executed"])
        self.assertFalse(first["installed"])
        self.assertEqual(first["granted_permissions"], [])
        self.assertEqual(first["declared_permissions"], ["source.read"])
        self.assertEqual(len(first["evidence"]), 1)
        self.assertEqual(self.catalog.search_ranked("python")[0]["evidence"][0]["trust"], "self_reported_unverified")

    def test_unverified_claim_never_becomes_actual_verification(self):
        for stage in ("sandbox", "test", "human-review"):
            report = self.catalog.record_evidence(self.third["digest"], stage, "passed", "Owner-entered claim only")
            self.assertFalse(report["execution_performed"])
        stored = next(x for x in self.catalog.search_ranked("") if x["digest"] == self.third["digest"])
        self.assertEqual(stored["status"], "quarantined")
        self.assertEqual(stored["granted_permissions"], [])
        self.assertFalse(stored["installed"])
        self.assertFalse(stored["executed"])

    def test_evidence_rejects_fake_or_invalid_records_without_writing(self):
        before = (self.root / "skills" / "catalog.json").read_bytes()
        invalid = [
            ("bad", "scan", "passed", "Test", None),
            ("b" * 64, "scan", "passed", "Test", None),
            (self.first["digest"], "activate", "passed", "Test", None),
            (self.first["digest"], "scan", "approved", "Test", None),
            (self.first["digest"], "scan", "passed", "", None),
            (self.first["digest"], "scan", "passed", "\x00invalid", None),
            (self.first["digest"], "scan", "passed", "x" * 501, None),
            (self.first["digest"], "scan", "passed", "okay", "not-a-digest"),
        ]
        for digest, stage, outcome, note, report in invalid:
            with self.subTest(stage=stage, outcome=outcome, note=note[:20]):
                with self.assertRaises(ValueError):
                    self.catalog.record_evidence(digest, stage, outcome, note, report_sha256=report)
        self.assertEqual((self.root / "skills" / "catalog.json").read_bytes(), before)

    def test_cli_offline_ranked_search_and_manual_evidence(self):
        engine = Engine(self.root)
        try:
            lookup = parser().parse_args(["skills", "list", "--ranked", "--search", "python", "--limit", "1"])
            records = dispatch(engine, lookup)
            self.assertEqual(records[0]["name"], "python-review")
            self.assertNotIn("body", records[0])
            evidence = parser().parse_args([
                "skills", "evidence", self.second["digest"], "scan", "blocked",
                "--note", "Unknown source rights; inspect before any test",
            ])
            result = dispatch(engine, evidence)
            self.assertEqual(result["stage"], "scan")
            self.assertEqual(result["reported_outcome"], "blocked")
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main()
