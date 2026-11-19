"""Cloud AI adapter contract tests. All provider replies are simulated;
no API key, paid call, or external network request is used by CI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock
import unittest

from toad_core.cloud_models import CloudModelConfig, OpenAIResponsesAdapter, app_model
from toad_core.models import ModelError, OllamaAdapter
from toad_core.schema import PackageError


def success(text='{"result":"ok"}', *, reasoning=False):
    output = [{"type":"message","role":"assistant",
               "content":[{"type":"output_text","text":text}]}]
    if reasoning:
        output.insert(0,{"type":"reasoning","summary":[]})
    return {"status":"completed","output":output}


class FakeRunner:
    def __init__(self, reply=None, **flags):
        self.calls=[]
        self.reply=reply if reply is not None else success()
        self.flags=flags

    def __call__(self, command, **kwargs):
        self.calls.append((command,kwargs))
        return {
            "returncode":0,"stdout":json.dumps(self.reply) if not isinstance(self.reply,str) else self.reply,
            "stderr":"","error":None,"timed_out":False,"cancelled":False,
            "output_limited":False,
            **self.flags,
        }


class CloudModelTests(unittest.TestCase):
    def configured(self, runner=None):
        return OpenAIResponsesAdapter(
            CloudModelConfig(model="gpt-5.3-codex",max_output_tokens=4096),
            process_runner=runner or FakeRunner()
        )

    def env(self,**extra):
        return mock.patch.dict(os.environ, {
            "TOAD_MODEL_PROVIDER":"openai",
            "TOAD_OPENAI_MODEL":"gpt-5.3-codex",
            "OPENAI_API_KEY":"test-key-do-not-call",
            "TOAD_ALLOW_PAID_AI":"YES",
            **extra,
        },clear=True)

    def test_not_enabled_never_spawns_a_process(self):
        runner=FakeRunner()
        for item in ({},{"TOAD_ALLOW_PAID_AI":"NO"},
                     {"TOAD_ALLOW_PAID_AI":"YES"}):
            with self.subTest(item=item), mock.patch.dict(os.environ,item,clear=True):
                with self.assertRaises(ModelError):
                    self.configured(runner).generate_json("propose a notebook")
        self.assertEqual(runner.calls,[])

    def test_configured_provider_returns_valid_json_data_only(self):
        runner=FakeRunner(success('{"safe":true}',reasoning=True))
        with self.env():
            status=self.configured(runner).readiness()
            self.assertTrue(status["configured"])
            self.assertFalse(status["connection_verified"])
            self.assertFalse(status["request_performed"])
            data=self.configured(runner).generate_json("Describe an app",purpose="AI proposal")
        self.assertEqual(data,{"safe":True})
        self.assertEqual(len(runner.calls),1)
        command,options=runner.calls[0]
        self.assertIn("_cloud_transport.py",command[-1])
        self.assertNotIn("test-key-do-not-call"," ".join(command))
        self.assertTrue(options["env"]["OPENAI_API_KEY"])
        self.assertEqual(options["env"].keys(),{"OPENAI_API_KEY","PATH"})
        sent=json.loads(options["input_data"])
        self.assertNotIn("test-key-do-not-call",json.dumps(sent))
        self.assertEqual(sent["payload"]["store"],False)
        self.assertEqual(sent["payload"]["tools"],[])
        self.assertEqual(sent["payload"]["text"]["format"]["type"],"json_object")
        self.assertEqual(sent["payload"]["max_output_tokens"],4096)
        self.assertEqual(sent["payload"]["model"],"gpt-5.3-codex")

    def test_bad_response_refusal_tool_calls_and_malformed_json_rejected(self):
        wrong=[
            {"status":"incomplete","output":[]},
            {"status":"completed","output":[]},
            {"status":"completed","output":[{"type":"tool_call","name":"shell"}]},
            {"status":"completed","output":[{"type":"message","role":"user","content":[]}]},
            {"status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"refusal","refusal":"no"}]}]},
            success("not-json"),
            success("[]"),
            success('{"safe":1,"safe":2}'),
            "not-outer-json",
        ]
        with self.env():
            for payload in wrong:
                with self.subTest(payload=payload),self.assertRaises(ModelError):
                    self.configured(FakeRunner(payload)).generate_json("Build a notebook")

    def test_process_failures_are_reported_without_raw_key_or_stderr(self):
        with self.env():
            for flags in (
                {"returncode":1,"stderr":"test-key-do-not-call"},
                {"timed_out":True},
                {"output_limited":True},
                {"cancelled":True},
                {"error":"test-key-do-not-call"},
            ):
                with self.subTest(flags=flags):
                    with self.assertRaises(ModelError) as error:
                        self.configured(FakeRunner(**flags)).generate_json("Make notes")
                    self.assertNotIn("test-key-do-not-call",str(error.exception))

    def test_invalid_models_limits_and_user_prompts_refuse(self):
        for name in ("","../../secrets","open ai","x"*102):
            with self.subTest(model=name),self.assertRaises(PackageError):
                CloudModelConfig(model=name)
        for kwargs in ({"timeout_seconds":0},{"max_output_tokens":65536},
                       {"max_response_bytes":10000000}):
            with self.subTest(kwargs=kwargs),self.assertRaises(PackageError):
                CloudModelConfig(model="approved",**kwargs)
        runner=FakeRunner()
        with self.env():
            for prompt in ("", "x"*50001):
                with self.assertRaises(ModelError):
                    self.configured(runner).generate_json(prompt)
            with self.assertRaises(ModelError):
                self.configured(runner).generate_json("test",purpose="bad\nheader")
        self.assertFalse(runner.calls)

    def test_factory_is_explicit_and_offline_by_default(self):
        with mock.patch.dict(os.environ,{},clear=True):
            self.assertIsInstance(app_model(),OllamaAdapter)
        with self.env():
            self.assertIsInstance(app_model(),OpenAIResponsesAdapter)
        with self.env(TOAD_MODEL_PROVIDER="malicious"):
            with self.assertRaises(PackageError):
                app_model()

    def test_https_endpoint_cannot_be_user_overridden(self):
        source=(Path(__file__).resolve().parents[1]/"toad_core"/"_cloud_transport.py").read_text()
        self.assertIn('https://api.openai.com/v1/responses',source)
        self.assertIn("NoRedirect",source)
        self.assertIn("ProxyHandler({})",source)
        self.assertNotIn("TOAD_OPENAI_ENDPOINT",source)
        self.assertNotIn("OPENAI_BASE_URL",source)


if __name__=="__main__":
    unittest.main()
