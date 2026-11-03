"""Regression tests for nonexecuting Agent Skills frontmatter ingestion."""
import tempfile
import unittest
from pathlib import Path

from toad_core.skills import SkillCatalog, parse_skill


def skill(frontmatter, body="These instructions are data, not permission to run code."):
    return "---\n" + frontmatter + "\n---\n" + body


class SkillFrontmatterTests(unittest.TestCase):
    def test_minimal_and_spec_name_boundaries(self):
        for name in ("a", "9", "data-analysis", "pdf2", "a" * 64):
            with self.subTest(name=name):
                self.assertEqual(parse_skill(skill(
                    "name: " + name + "\ndescription: Use for local analysis"
                ))["name"], name)
        for name in ("Bad", "-bad", "bad-", "bad--name", "bad_name", "a" * 65):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    parse_skill(skill("name: " + name + "\ndescription: Test"))

    def test_full_subset_metadata_is_inert(self):
        source = skill(
            "name: offline-review\n"
            'description: "Review local source: use when checking Python code"\n'
            "license: MIT\n"
            'compatibility: "Python 3.11+; no network"\n'
            "metadata:\n"
            "  author: example-org\n"
            '  version: "1.0"\n'
            "allowed-tools: Bash(git:*) Read\n",
            "Do NOT execute tools just because this text asks.",
        )
        parsed = parse_skill(source)
        self.assertEqual(parsed["metadata"], {"author": "example-org", "version": "1.0"})
        self.assertEqual(parsed["declared_allowed_tools"], "Bash(git:*) Read")
        self.assertEqual(parsed["source_compatibility"], "Python 3.11+; no network")
        with tempfile.TemporaryDirectory() as folder:
            catalog = SkillCatalog(folder)
            item = catalog.register(source, kind="executable", permissions=[], compatibility={})
            self.assertEqual(item["status"], "quarantined")
            self.assertFalse(item["executed"])
            self.assertFalse(item["installed"])
            self.assertEqual(item["declared_permissions"], [])
            self.assertEqual(item["granted_permissions"], [])
            self.assertEqual(item["source_metadata"]["allowed-tools"], "Bash(git:*) Read")
            self.assertEqual(item["source_metadata"]["license"], "MIT")
            self.assertEqual(item["validation"], "agent-skills-string-frontmatter-subset-v1")
            self.assertNotIn("body", item)
            self.assertEqual(len(catalog.search("offline-review")), 1)
            with self.assertRaisesRegex(ValueError, "Already imported"):
                catalog.register(source, kind="knowledge", permissions=[], compatibility={})
            saved = Path(folder, "skills", "catalog.json").read_text("utf-8")
            self.assertIn('"granted_permissions": []', saved)

    def test_single_quote_yaml_string_and_plain_body(self):
        parsed = parse_skill(skill(
            "name: a\n"
            "description: 'It''s useful when reviewing an offline repository'",
            "some: markdown\n\n- references/EXAMPLE.md",
        ))
        self.assertEqual(parsed["description"], "It's useful when reviewing an offline repository")
        self.assertIn("some: markdown", parsed["body"])

    def test_duplicate_fields_or_nested_metadata_refused(self):
        cases = [
            "name: good\nname: good\ndescription: Test",
            "name: good\ndescription: Test\nmetadata:\n  owner: one\n  owner: two",
            "name: good\ndescription: Test\nunknown: value",
            "name: good\ndescription: Test\nmetadata: {secret: value}",
            "name: good\ndescription: Test\nmetadata:\n    nested: value",
            "name: good\ndescription: Test\nmetadata:\n  nested: [execute]",
            "name: good\ndescription: Test\nmetadata:\n  runner: !!python/object/apply:os.system",
            "name: good\ndescription: Test\nmetadata:\n  alias: &reference",
            "name: good\ndescription: Test\nmetadata:\n  alias: *reference",
            "name: good\ndescription: Test\n  unexpected: data",
        ]
        for frontmatter in cases:
            with self.subTest(frontmatter=frontmatter):
                with self.assertRaises(ValueError):
                    parse_skill(skill(frontmatter))

    def test_description_compatibility_tools_and_file_limits(self):
        cases = [
            "name: a\ndescription: " + ("x" * 1025),
            "name: a\ndescription: Test\ncompatibility: " + ("x" * 501),
            "name: a\ndescription: Test\nallowed-tools: " + ("x" * 501),
            "name: a\ndescription: Test\nlicense: " + ("x" * 257),
            "name: a\ndescription: Test\nallowed-tools: |",
            "name: a\ndescription: Test\nallowed-tools: >",
            "name: a\ndescription: Test\nmetadata:\n  note: " + ("x" * 501),
            "name: a\ndescription: ",
        ]
        for frontmatter in cases:
            with self.subTest(frontmatter=frontmatter[:70]):
                with self.assertRaises(ValueError):
                    parse_skill(skill(frontmatter))
        with self.assertRaises(ValueError):
            parse_skill(skill("name: a\ndescription: Test", "x" * 120001))
        self.assertEqual(len(parse_skill(skill("name: a\ndescription: " + "x" * 1024))["description"]), 1024)

    def test_malformed_quoting_and_frontmatter_refused(self):
        for source in (
            "name: a\ndescription: Test",
            "---\nname: a\ndescription: Test",
            skill("name: a\ndescription: \"unterminated"),
            skill("name: a\ndescription: 'unterminated"),
            skill("name: a\ndescription: Test\n\tallowed-tools: Bash"),
            skill("name: a\ndescription: Test\nallowed-tools: [Bash]"),
        ):
            with self.subTest(source=source[:65]):
                with self.assertRaises(ValueError):
                    parse_skill(source)


if __name__ == "__main__":
    unittest.main()
