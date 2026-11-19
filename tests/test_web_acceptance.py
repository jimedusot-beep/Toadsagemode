"""Frozen acceptance workflow contract tests: doubles only, no Docker/model execution."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from toad_core.schema import PackageError, json_bytes
from toad_core.web_acceptance import FrozenWebAcceptance, PLAN_SCHEMA, TRIAL_SCHEMA
from toad_core.web_codegen import validate_web_source


GOAL = "Make a flashcard page with a button that changes its text when tapped"
CHECKS = [
    {"kind":"title","expected":"Flashcard Practice"},
    {"kind":"click_text","selector":"#flip","target":"#flip","contains":"Back"},
]
SOURCE = {
    "schema":"toad-web-source-draft-v1",
    "name":"flashcard-practice",
    "title":"Flashcard Practice",
    "files":[
        {"path":"index.html","content":"<!doctype html><html><head><title>Flashcard Practice</title></head><body><button id='flip'>Front</button><script src='app.js' defer></script></body></html>"},
        {"path":"styles.css","content":"body{background:#fff;color:#222}"},
        {"path":"app.js","content":"document.getElementById('flip').addEventListener('click',()=>{document.getElementById('flip').textContent='Back';});"},
    ],
    "declared_features":["tap-to-flip flashcards"],
}


class ModelDouble:
    def __init__(self, verify=None):
        self.calls = []
        self.verify = verify

    def generate_json(self, prompt, **kwargs):
        instruction = json.loads(prompt)
        if self.verify:
            self.verify(instruction)
        self.calls.append((instruction,kwargs))
        return copy.deepcopy(SOURCE)


class WorkerDouble:
    def __init__(self, *, fail=False, wrong_hash=False):
        self.calls = []
        self.fail = fail
        self.wrong_hash = wrong_hash

    def run_web_source(self, source, checks):
        self.calls.append((source,checks))
        return {
            "source_sha256": ("0"*64 if self.wrong_hash else hashlib.sha256(json_bytes(validate_web_source(source))).hexdigest()),
            "checks_sha256": hashlib.sha256(json_bytes(checks)).hexdigest(),
            "executed": True, "passed": not self.fail,
            "cleanup_ok": True, "blocked_reason": "expectation_not_met" if self.fail else None,
            "image_id":"sha256:"+"a"*64,
            "receipt":{"schema":"toad-web-browser-receipt-v1","browser":"webkit","passed":not self.fail},
        }


class FrozenAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "private"

    def tearDown(self):
        self.temp.cleanup()

    def workflow(self, model=None, worker=None):
        return FrozenWebAcceptance(self.workspace,model=model,worker=worker)

    def test_plan_is_created_before_the_model_sees_any_request(self):
        observed=[]
        def inspect_prompt(prompt):
            observed.append(True)
            self.assertEqual(prompt["request"],GOAL)
            self.assertNotIn("checks",prompt)
            self.assertNotIn("title",prompt)
            self.assertTrue(list((self.workspace / "web-acceptance-plans").glob("*.json")))
        model=ModelDouble(verify=inspect_prompt)
        flow=self.workflow(model=model)
        plan=flow.create_plan(GOAL,CHECKS)
        self.assertFalse(plan["model_wrote_checks"])
        self.assertFalse(plan["executed"])
        record=flow.plan(plan["plan_id"])
        self.assertEqual(record["schema"],PLAN_SCHEMA)
        self.assertEqual(record["checks"],CHECKS)
        self.assertEqual(len(record["checks_sha256"]),64)
        self.assertFalse(model.calls)
        created=flow.draft(plan["plan_id"])
        self.assertEqual(len(model.calls),1)
        self.assertEqual(len(observed),1)
        self.assertEqual(created["plan_id"],plan["plan_id"])
        self.assertEqual(created["checks_sha256"],plan["checks_sha256"])
        self.assertFalse(created["release_allowed"])
        self.assertFalse(created["executed"])
        trial=flow.trial(created["trial_id"])
        self.assertEqual(trial["schema"],TRIAL_SCHEMA)
        self.assertEqual(trial["source_draft_id"],created["source_draft_id"])
        self.assertEqual(trial["status"],"quarantined_awaiting_independent_test")

    def test_dry_run_never_calls_worker_and_has_digest_bound_receipt(self):
        worker=WorkerDouble()
        flow=self.workflow(model=ModelDouble(),worker=worker)
        p=flow.create_plan(GOAL,CHECKS)
        trial=flow.draft(p["plan_id"])
        report=flow.test(trial["trial_id"])
        self.assertFalse(report["executed"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["release_allowed"])
        self.assertEqual(report["status"],"blocked_not_authorized")
        self.assertEqual(worker.calls,[])
        live=flow.test(trial["trial_id"],run=True)
        self.assertTrue(live["executed"])
        self.assertTrue(live["passed"])
        self.assertFalse(live["release_allowed"])
        self.assertEqual(live["checks_sha256"],p["checks_sha256"])
        self.assertEqual(worker.calls[0][1],CHECKS)
        self.assertEqual(flow.trial(trial["trial_id"])["status"],"quarantined_awaiting_independent_test")

    def test_failed_worker_and_forged_source_hash_never_pass(self):
        flow=self.workflow(model=ModelDouble(),worker=WorkerDouble(fail=True))
        p=flow.create_plan(GOAL,CHECKS)
        t=flow.draft(p["plan_id"])
        failed=flow.test(t["trial_id"],run=True)
        self.assertFalse(failed["passed"])
        self.assertFalse(failed["release_allowed"])
        wrong=self.workflow(worker=WorkerDouble(wrong_hash=True))
        with self.assertRaisesRegex(PackageError,"hashes"):
            wrong.test(t["trial_id"],run=True)

    def test_plan_tampering_blocks_model_generation_and_is_not_repairable(self):
        model=ModelDouble()
        flow=self.workflow(model=model)
        p=flow.create_plan(GOAL,CHECKS)
        path=self.workspace / "web-acceptance-plans" / (p["plan_id"]+".json")
        plan=json.loads(path.read_text())
        plan["checks"][1]["contains"]="Front"
        path.write_text(json.dumps(plan))
        with self.assertRaises(PackageError):
            flow.plan(p["plan_id"])
        with self.assertRaises(PackageError):
            flow.draft(p["plan_id"])
        self.assertFalse(model.calls)
        self.assertFalse((self.workspace / "ai-web-drafts").exists())

    def test_trial_tampering_blocks_independent_testing(self):
        worker=WorkerDouble()
        flow=self.workflow(model=ModelDouble(),worker=worker)
        p=flow.create_plan(GOAL,CHECKS)
        t=flow.draft(p["plan_id"])
        path=self.workspace / "web-acceptance-trials" / (t["trial_id"]+".json")
        record=json.loads(path.read_text())
        record["source_sha256"]="0"*64
        path.write_text(json.dumps(record))
        with self.assertRaises(PackageError):
            flow.test(t["trial_id"],run=True)
        self.assertEqual(worker.calls,[])

    def test_draft_tamper_is_detected_at_trial_gate(self):
        flow=self.workflow(model=ModelDouble(),worker=WorkerDouble())
        p=flow.create_plan(GOAL,CHECKS)
        trial=flow.draft(p["plan_id"])
        path=self.workspace / "ai-web-drafts" / (trial["source_draft_id"]+".json")
        payload=json.loads(path.read_text())
        payload["draft"]["files"][2]["content"]="console.log('edited')"
        path.write_text(json.dumps(payload))
        with self.assertRaises(PackageError):
            flow.trial(trial["trial_id"])

    def test_limits_invalid_checks_and_symlinks_are_rejected_before_model(self):
        flow=self.workflow(model=ModelDouble())
        for goal,checks in ((GOAL,[]),(GOAL,[{"kind":"eval","javascript":"1+1"}]),
                            (" ",CHECKS),("x"*2501,CHECKS)):
            with self.subTest(goal=goal[:10],checks=checks),self.assertRaises(PackageError):
                flow.create_plan(goal,checks)
        self.assertFalse((self.workspace / "web-acceptance-plans").exists())
        safe=self.root/"safe"
        safe.mkdir()
        link=self.root/"linked"
        try:
            link.symlink_to(safe,target_is_directory=True)
        except (OSError,NotImplementedError):
            return
        with self.assertRaises(PackageError):
            FrozenWebAcceptance(link).create_plan(GOAL,CHECKS)

    def test_cli_freeze_and_show_and_trial_default_do_not_run_docker(self):
        file=self.root/"checks.json"
        file.write_text(json.dumps(CHECKS))
        def call(*args):
            return subprocess.run([sys.executable,"-m","toad_core","--workspace",
                                   str(self.workspace),*args],capture_output=True,text=True,timeout=10)
        created=call("app","freeze-tests",GOAL,"--checks",str(file))
        self.assertEqual(created.returncode,0,created.stderr)
        p=json.loads(created.stdout)
        read=call("app","frozen-tests",p["plan_id"])
        self.assertEqual(read.returncode,0,read.stderr)
        self.assertEqual(json.loads(read.stdout)["checks"],CHECKS)
        bad=call("app","test-web-trial","f"*32)
        self.assertNotEqual(bad.returncode,0)
        self.assertFalse(json.loads(bad.stderr)["ok"])


if __name__=="__main__":
    unittest.main()
