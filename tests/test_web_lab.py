"""Contract tests only. NEVER run Docker or AI-authored JS in GitHub CI."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from toad_core.schema import PackageError
from toad_core.web_lab import WebKitDockerWorker, validate_checks, TMP_BYTES, WEB_IMAGE


IMAGE = "sha256:" + "a" * 64


def sample():
    return {
        "schema": "toad-web-source-draft-v1",
        "name": "flash-cards",
        "title": "Flash Cards",
        "files": [
            {"path":"index.html","content":"<!doctype html><html><title>Flash Cards</title><button id='flip'>Flip</button><script src='app.js'></script></html>"},
            {"path":"styles.css","content":"body{color:black}"},
            {"path":"app.js","content":"document.querySelector('#flip').textContent = 'Back'"},
        ],
        "declared_features": ["flashcards"],
    }


def checks():
    return [
        {"kind":"title","expected":"Flash Cards"},
        {"kind":"click_text","selector":"#flip","target":"#flip","contains":"Back"},
    ]


def fake_container():
    return {
        "Image":IMAGE,
        "HostConfig":{
            "NetworkMode":"none","ReadonlyRootfs":True,"Privileged":False,
            "PidsLimit":64,"Memory":512*1024*1024,"MemorySwap":512*1024*1024,
            "NanoCpus":1000000000,"IpcMode":"none",
            "CapDrop":["ALL"],"Binds":None,"CapAdd":None,"Devices":None,
            "DeviceRequests":None,"SecurityOpt":["no-new-privileges=true"],
            "LogConfig":{"Type":"none"},
            "Tmpfs":{
                "/work":"rw,nosuid,nodev,noexec,size=67108864,mode=1777",
                "/tmp":"rw,nosuid,nodev,noexec,size=134217728,mode=1777",
            },
        },
        "Config":{
            "User":"65532:65532","WorkingDir":"/work",
            "Entrypoint":["/usr/bin/node"],"Cmd":["/opt/toad-web/runner.cjs"],
            "Env":["HOME=/tmp","PLAYWRIGHT_BROWSERS_PATH=/ms-playwright"],
        },
        "Mounts":[{"Type":"tmpfs","Destination":"/work"},{"Type":"tmpfs","Destination":"/tmp"}],
        "State":{"StartedAt":"2026-11-19T01:00:00Z","Running":False,"ExitCode":0,
                 "OOMKilled":False,"Error":""},
    }


class WebKitLabContracts(unittest.TestCase):
    def test_fixed_test_vocabulary_cannot_run_user_submitted_code(self):
        self.assertEqual(validate_checks(checks()),checks())
        bad = [
            [],
            [{"kind":"javascript","code":"eval('1+1')"}],
            [{"kind":"text","selector":"#x","contains":"ok","code":"alert(1)"}],
            [{"kind":"click_text","selector":"#x >> script","target":"#x","contains":"x"}],
            [{"kind":"text","selector":"#x","contains":"a\nb"}],
            [{"kind":"title","expected":"x"}]*9,
            [{"kind":"fill_click_text","input":"#name","button":"#save","target":"#list","contains":"x"}],
            [{"kind":"title","expected":"x","after":"run()"}],
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(PackageError):
                validate_checks(item)

    def test_docker_command_never_mounts_host_or_adds_network_privilege(self):
        w=WebKitDockerWorker()
        args=w._create_args("toad-test-1",IMAGE)
        command=" ".join(args)
        for expected in ("--pull=never","--network=none","--read-only",
                         "--cap-drop=ALL","--user=65532:65532",
                         "--security-opt=no-new-privileges=true",
                         "--ipc=none","--log-driver=none",
                         "--entrypoint=/usr/bin/node",IMAGE):
            self.assertIn(expected,command)
        self.assertNotIn("--mount",command)
        self.assertNotIn("--privileged",command)
        self.assertNotIn("--network=host",command)
        self.assertNotIn("docker.sock",command)
        self.assertEqual(args[-1],"/opt/toad-web/runner.cjs")
        self.assertEqual(w.policy.image,WEB_IMAGE)
        self.assertEqual(w.policy.memory_mb,512)

    def test_effective_container_inspection_rejects_weakened_security(self):
        w=WebKitDockerWorker()
        w._check_container(fake_container(),IMAGE)
        mutations=[
            ("HostConfig","NetworkMode","host"),
            ("HostConfig","ReadonlyRootfs",False),
            ("HostConfig","Privileged",True),
            ("HostConfig","PidsLimit",0),
            ("HostConfig","Memory",0),
            ("HostConfig","IpcMode","host"),
            ("HostConfig","Binds",["/tmp:/tmp"]),
            ("HostConfig","Devices",["/dev/null"]),
            ("HostConfig","CapDrop",[]),
            ("HostConfig","SecurityOpt",["seccomp=unconfined"]),
            ("HostConfig","LogConfig",{"Type":"json-file"}),
            ("HostConfig","Tmpfs",{}),
            ("Config","User","root"),
            ("Config","Entrypoint",["/bin/sh"]),
            ("Config","Cmd",["-e","alert(1)"]),
            ("Config","WorkingDir","/host"),
        ]
        for parent,key,value in mutations:
            data=fake_container()
            data[parent][key]=value
            with self.subTest(key=key,value=value), self.assertRaises(PackageError):
                w._check_container(data,IMAGE)
        data=fake_container()
        data["Image"]="sha256:"+"b"*64
        with self.assertRaises(PackageError):
            w._check_container(data,IMAGE)
        data=fake_container()
        data["Mounts"].append({"Type":"bind","Source":"/private"})
        with self.assertRaises(PackageError):
            w._check_container(data,IMAGE)

    def test_no_docker_returns_explicit_block_and_never_executes(self):
        w=WebKitDockerWorker()
        w.docker=None
        result=w.run_web_source(sample(),checks())
        self.assertFalse(result["passed"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["release_allowed"])
        self.assertIn("unavailable",result["blocked_reason"])
        self.assertEqual(result["receipt"],None)
        self.assertEqual(len(result["source_sha256"]),64)

    def test_dummy_docker_receipts_are_not_real_world_evidence(self):
        # CI controlled doubles validate acceptance logic, not real execution.
        receipt={
            "schema":"toad-web-browser-receipt-v1","browser":"webkit",
            "executed":True,"passed":True,
            "checks":[{"index":0,"kind":"title","passed":True},
                      {"index":1,"kind":"click_text","passed":True}],
            "page_errors":0,"blocked_requests":0,
        }
        for change in ({},{'page_errors':1},{'checks':[]},
                       {'checks':[{"index":0,"kind":"title","passed":False}]},
                       {'browser':"chromium"},{'passed':False}):
            w=WebKitDockerWorker()
            w.docker="docker"  # fake path; run_limited never called
            w._probe=lambda _:{"available":True,"image_id":IMAGE}
            inspection=fake_container()
            w._inspect=lambda _config,_name:copy.deepcopy(inspection)
            w._cleanup=lambda _config,_name:True
            current={**receipt,**change}
            def fake_call(_config,args,**kwargs):
                if args[0]=="create":return {"returncode":0,"error":None,"timed_out":False,"output_limited":False,"cancelled":False}
                if args[0]=="start":
                    return {"returncode":0,"stdout":json.dumps(current),"stderr":"",
                            "error":None,"timed_out":False,"output_limited":False,"cancelled":False}
                raise AssertionError("Unexpected command")
            w._call=fake_call
            result=w.run_web_source(sample(),checks())
            self.assertTrue(result["executed"])
            self.assertEqual(result["passed"],not change)
            self.assertFalse(result["release_allowed"])

    def test_failed_cleanup_cannot_yield_green(self):
        w=WebKitDockerWorker()
        w.docker="docker"
        w._probe=lambda _:{"available":True,"image_id":IMAGE}
        w._inspect=lambda _config,_name:fake_container()
        w._cleanup=lambda _config,_name:False
        w._call=lambda _config,args,**kw:{"returncode":0,"stdout":"{}","stderr":"",
                "error":None,"timed_out":False,"output_limited":False,"cancelled":False}
        result=w.run_web_source(sample(),checks())
        self.assertFalse(result["passed"])
        self.assertFalse(result["cleanup_ok"])
        self.assertEqual(result["blocked_reason"],"Browser container cleanup failed")

    def test_cli_default_does_not_execute_drafts(self):
        with tempfile.TemporaryDirectory() as temp:
            r=subprocess.run([sys.executable,"-m","toad_core","--workspace",temp,
                "app","browser-test","f"*32,"--checks","not-on-disk.json"],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('"executed": false',r.stdout.lower())
            self.assertIn("Pass --run",r.stdout)

    def test_trusted_node_harness_syntax_is_checked_without_running_app(self):
        node=shutil.which("node")
        if not node:self.skipTest("Node unavailable on this test machine")
        runner=Path(__file__).resolve().parents[1]/"web_lab"/"runner.cjs"
        result=subprocess.run([node,"--check",str(runner)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=="__main__":
    unittest.main()
