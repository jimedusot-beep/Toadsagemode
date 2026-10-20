"""Tests trusted orchestration and fixed Docker boundaries; no candidate runs here."""
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from toad_core.lab import DockerWorker, LabPolicy, run_limited
from toad_core.schema import normalize_package, package_digest, PackageError
from toad_core.engine import Engine
from test_packages import package

IMAGE='sha256:'+'a'*64


def host_info():
    return {'OSType':'linux','CgroupVersion':'2','MemoryLimit':True,'SwapLimit':True,'PidsLimit':True,
            'CPUCfsQuota':True,'CPUCfsPeriod':True,'SecurityOptions':['name=seccomp,profile=builtin']}


def container_info(policy):
    return {'Image':IMAGE,'State':{'StartedAt':'2026-10-20T15:00:00Z','Running':False,'ExitCode':0,'OOMKilled':False,'Error':''},'Config':{'User':'65532:65532','WorkingDir':'/work','Entrypoint':['/usr/local/bin/python']},'Mounts':[],
            'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'Binds':None,'CapAdd':None,'CapDrop':['ALL'],
              'Devices':[],'DeviceRequests':None,'PidsLimit':policy.pids,'Memory':policy.memory_mb*1024*1024,'MemorySwap':policy.memory_mb*1024*1024,
              'NanoCpus':int(policy.cpus*1e9),'SecurityOpt':['no-new-privileges=true'],'IpcMode':'none','LogConfig':{'Type':'none'},
              'Tmpfs':{'/work':f'rw,nosuid,nodev,noexec,size={policy.disk_mb*1024*1024},mode=1777','/tmp':'rw,nosuid,nodev,noexec,size=8388608,mode=1777'}}}


class DockerBoundary:
    def __init__(self, *, output='hello\n', code=0, bad_config=False, cleanup=False):
        self.calls=[];self.output=output;self.code=code;self.bad_config=bad_config;self.cleanup=cleanup
    def __call__(self,cmd,**kw):
        self.calls.append((cmd,kw));out='';code=0
        if 'info' in cmd:out=json.dumps(host_info())
        elif 'image' in cmd:out=json.dumps({'Id':IMAGE})
        elif 'create' in cmd:out='container-id'
        elif 'inspect' in cmd:
            config=container_info(LabPolicy())
            if self.bad_config:config['HostConfig']['NetworkMode']='host'
            out=json.dumps([config])
        elif 'start' in cmd:out=self.output;code=self.code
        elif 'rm' in cmd:code=1 if self.cleanup else 0
        else:raise AssertionError(cmd)
        return {'returncode':code,'stdout':out,'stderr':'failure' if code else '', 'timed_out':False,'output_limited':False,'cancelled':False,'elapsed':0.01}


class ProcessLimitTests(unittest.TestCase):
    def test_timeout_and_output_limits_are_enforced_on_trusted_helpers(self):
        r=run_limited([sys.executable,'-c','import time; time.sleep(5)'],timeout=0.15,output_limit=1024)
        self.assertTrue(r['timed_out']);self.assertLess(r['elapsed'],3)
        r=run_limited([sys.executable,'-c','print("x"*100000)'],timeout=2,output_limit=1000)
        self.assertTrue(r['output_limited']);self.assertLessEqual(len(r['stdout'].encode())+len(r['stderr'].encode()),1000)
    def test_spawn_failure_and_cancellation_never_succeed(self):
        r=run_limited(['/no/such/toad-executable'],timeout=1,output_limit=1000)
        self.assertIsNone(r['returncode']);self.assertTrue(r['error'])
        r=run_limited([sys.executable,'-c','import time; time.sleep(5)'],timeout=2,output_limit=1000,cancel=lambda:True)
        self.assertTrue(r['cancelled'])


class LabTests(unittest.TestCase):
    def test_missing_docker_blocks_without_host_fallback(self):
        with patch('toad_core.lab.shutil.which',return_value=None),patch('toad_core.lab.run_limited') as runner:
            result=DockerWorker().run(package())
            self.assertFalse(result['executed']);self.assertFalse(result['passed']);runner.assert_not_called()

    def test_fixed_policy_is_checked_before_execution_and_cleanup_always_runs(self):
        boundary=DockerBoundary()
        with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=boundary):
            result=DockerWorker().run(package())
        self.assertTrue(result['passed']);self.assertEqual(result['digest'],package_digest(normalize_package(package())))
        create=next(c for c,k in boundary.calls if 'create' in c)
        self.assertIn('--network=none',create);self.assertIn('--read-only',create);self.assertIn('--cap-drop=ALL',create)
        self.assertIn('--pull=never',create);self.assertIn(IMAGE,create)
        self.assertFalse(any('--volume' in c or '--mount' in c or '/var/run/docker.sock' in c for c in create))
        start=next(k for c,k in boundary.calls if 'start' in c)
        self.assertIn(b'print',start['input_data'])
        self.assertTrue(any('rm' in c for c,k in boundary.calls))

    def test_bad_isolation_and_unsupported_dependencies_fail_closed(self):
        boundary=DockerBoundary(bad_config=True)
        with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=boundary):
            result=DockerWorker().run(package())
        self.assertFalse(result['passed']);self.assertFalse(result['executed'])
        self.assertFalse(any('start' in c for c,k in boundary.calls))
        self.assertTrue(any('rm' in c for c,k in boundary.calls))
        p=package();p['permissions']=['network']
        with patch('toad_core.lab.run_limited') as runner:
            result=DockerWorker().run(p)
        runner.assert_not_called();self.assertFalse(result['passed'])

    def test_output_mismatch_failed_test_and_cleanup_failure_never_verify(self):
        for options in [{'output':'wrong\n'},{'code':1},{'cleanup':True}]:
            with self.subTest(options=options):
                boundary=DockerBoundary(**options)
                with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=boundary):
                    result=DockerWorker().run(package())
                self.assertFalse(result['passed'])

    def test_missing_or_weak_host_enforcement_blocks(self):
        boundary=DockerBoundary()
        def weak(cmd,**kw):
            r=boundary(cmd,**kw)
            if 'info' in cmd:r['stdout']=json.dumps({**host_info(),'MemoryLimit':False})
            return r
        with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=weak):
            result=DockerWorker().run(package())
        self.assertFalse(result['executed']);self.assertFalse(result['passed'])

    def test_blocked_run_does_not_set_verified_or_failed_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine(tmp)
            try:
                a=e.ingest_package(package())
                with patch('toad_core.lab.shutil.which',return_value=None):r=e.test(a['id'])
                self.assertFalse(r['passed']);self.assertFalse(r['executed'])
                self.assertEqual(e.get(a['id'])['status'],'ready_for_testing')
                self.assertEqual(e.get(a['id'])['verification'],'unverified')
            finally:e.close()

    def test_resource_configuration_cannot_expand_without_bounds(self):
        for kw in [{'timeout_seconds':0},{'memory_mb':8192},{'pids':10000},{'cpus':12},{'disk_mb':4096}]:
            with self.assertRaises(PackageError):LabPolicy(**kw)
