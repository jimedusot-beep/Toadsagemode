"""Durable mission control tests. Workers/models below are explicit doubles."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from toad_core.engine import Engine
from toad_core.mission_engine import MissionEngine,MissionBudget
from toad_core.models import ModelError
from toad_core.repair import validate_repair
from toad_core.schema import PackageError,normalize_package,package_digest
from test_packages import package

class ModelDouble:
    def __init__(self,proposals):self.proposals=list(proposals);self.prompts=[]
    def generate_json(self,prompt,**kwargs):
        self.prompts.append(prompt)
        if not self.proposals:raise ModelError('Local model unavailable')
        value=self.proposals.pop(0)
        if isinstance(value,Exception):raise value
        return copy.deepcopy(value)

class LabDouble:
    def __init__(self,passed):self.passed=list(passed);self.calls=0
    def run(self,p,*,cancel=None):
        self.calls+=1;passed=self.passed.pop(0)
        return {'schema':'toad-test-run-v1','backend':'docker','digest':package_digest(p),'executed':True,'passed':passed,'cleanup_ok':True,
                'tests':[{'kind':'python','path':'main.py','passed':passed,'executed':True,'cleanup_ok':True,'stdout':'hello\n' if passed else 'wrong\n','stderr':'' if passed else 'AssertionError','category':'passed' if passed else 'test_failure'}]}

class MissionTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.engine=Engine(self.root/'data')
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def test_create_has_id_plan_and_durable_pause_resume_cancel(self):
        missions=MissionEngine(self.engine,model=ModelDouble([]));m=missions.create('Create a Python calculator')
        self.assertTrue(m['id']);self.assertEqual(m['status'],'queued')
        self.assertEqual(missions.pause(m['id'])['status'],'paused')
        self.assertEqual(missions.run(m['id'])['status'],'paused')
        self.assertEqual(missions.resume(m['id'])['status'],'queued')
        self.assertEqual(missions.cancel(m['id'])['status'],'cancelled')
        self.assertEqual(missions.run(m['id'])['status'],'cancelled')
        self.assertEqual(len(self.engine.store.connection.execute('SELECT * FROM missions').fetchall()),1)
    def test_missing_model_blocks_after_plan_and_preserves_reserved_budget(self):
        model=ModelDouble([]);missions=MissionEngine(self.engine,model=model)
        m=missions.create('Create a calculator');r=missions.run(m['id'])
        self.assertEqual(r['status'],'blocked');self.assertEqual(r['progress']['phase'],'generate')
        self.assertEqual(r['usage']['model_calls'],1);self.assertFalse(r.get('artifacts'))
        self.assertIn('unavailable',r['blocked_reason'].lower())
        missions.resume(m['id']);r=missions.run(m['id'])
        self.assertEqual(r['usage']['model_calls'],2)
        self.assertEqual(r['steps'][0]['status'],'completed')
    def test_success_with_explicit_doubles_packages_sources_and_reports(self):
        missions=MissionEngine(self.engine,model=ModelDouble([package()]),worker=LabDouble([True]))
        m=missions.create('Create a greeting program');r=missions.run(m['id'])
        self.assertEqual(r['status'],'completed');self.assertEqual(r['usage']['model_calls'],1)
        self.assertTrue(Path(r['artifacts']['project_zip']).exists())
        self.assertTrue(Path(r['artifacts']['report']).exists())
        self.assertEqual(missions.run(m['id'])['usage'],r['usage'])
        self.assertEqual(len(self.engine.list()),1)
        self.assertFalse(self.engine.list()[0]['installed'])
    def test_missing_docker_never_claims_mission_completion(self):
        from unittest.mock import patch
        with patch('toad_core.lab.shutil.which',return_value=None):
            missions=MissionEngine(self.engine,model=ModelDouble([package()]))
            m=missions.create('Create a greeting program');r=missions.run(m['id'])
        self.assertEqual(r['status'],'blocked');self.assertNotIn('project_zip',r.get('artifacts',{}))
        self.assertEqual(self.engine.list()[0]['verification'],'unverified')
    def test_source_only_repair_is_retested_before_success(self):
        broken=package('print("wrong")\n');fixed=package()
        model=ModelDouble([broken,fixed]);worker=LabDouble([False,True])
        missions=MissionEngine(self.engine,model=model,worker=worker)
        m=missions.create('Create a greeting program');r=missions.run(m['id'])
        self.assertEqual(r['status'],'completed');self.assertEqual(worker.calls,2)
        self.assertEqual(r['usage']['repairs'],1);self.assertEqual(len(r['repair_history']),1)
        self.assertEqual(r['repair_history'][0]['outcome'],'verified')
        self.assertEqual(len(self.engine.list()),2)
    def test_repairs_cannot_weaken_tests_or_expand_privileges(self):
        original=normalize_package(package());altered=copy.deepcopy(original);altered['tests'][0]['expected_stdout']='wrong\n'
        with self.assertRaises(PackageError):validate_repair(original,altered)
        altered=copy.deepcopy(original);altered['permissions']=['network']
        with self.assertRaises(PackageError):validate_repair(original,altered)
        altered=copy.deepcopy(original);altered['files'].append({'path':'extra.py','content':'pass'})
        with self.assertRaises(PackageError):validate_repair(original,altered)
        unit=package();unit['files'].append({'path':'tests/test_main.py','content':'import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n'});unit['tests']=[{'kind':'unittest','path':'tests'}]
        changed=copy.deepcopy(unit);changed['files'][1]['content']='pass\n'
        with self.assertRaises(PackageError):validate_repair(normalize_package(unit),changed)
    def test_identical_repair_stops_without_a_false_success(self):
        broken=package('print("wrong")\n');missions=MissionEngine(self.engine,model=ModelDouble([broken,broken]),worker=LabDouble([False]))
        m=missions.create('Create a greeting program');r=missions.run(m['id'])
        self.assertEqual(r['status'],'blocked');self.assertIn('change',r['blocked_reason'].lower())
        self.assertFalse(r.get('artifacts'))
    def test_test_and_model_budgets_stop_resumed_work(self):
        model=ModelDouble([ModelError('missing'),package()]);missions=MissionEngine(self.engine,model=model)
        m=missions.create('Create a greeting program',budget=MissionBudget(max_model_calls=1))
        self.assertEqual(missions.run(m['id'])['status'],'blocked')
        missions.resume(m['id']);r=missions.run(m['id'])
        self.assertEqual(r['status'],'blocked');self.assertEqual(len(model.prompts),1)
        self.assertIn('budget',r['blocked_reason'].lower())
    def test_checkpoint_resume_does_not_generate_twice(self):
        model=ModelDouble([package()]);worker=LabDouble([True]);missions=MissionEngine(self.engine,model=model,worker=worker)
        m=missions.create('Create a greeting program');r=missions.run(m['id'],max_steps=3)
        self.assertEqual(r['status'],'queued');self.assertEqual(r['progress']['phase'],'inspect')
        self.assertEqual(len(self.engine.list()),1)
        other=Engine(self.root/'data')
        try:
            resumed=MissionEngine(other,model=model,worker=worker).run(m['id'])
            self.assertEqual(resumed['status'],'completed');self.assertEqual(len(model.prompts),1)
        finally:other.close()
    def test_cancel_during_model_call_drops_proposal_and_prevents_ingest(self):
        controller={}
        class CancellingModel:
            def generate_json(inner,prompt,**kw):
                controller['mission'].cancel(controller['id']);return package()
        missions=MissionEngine(self.engine,model=CancellingModel());m=missions.create('Create a greeting program');controller.update(mission=missions,id=m['id'])
        self.assertEqual(missions.run(m['id'])['status'],'cancelled');self.assertEqual(self.engine.list(),[])

    def test_crashed_runner_cannot_reclaim_elapsed_budget(self):
        import subprocess,sys
        missions=MissionEngine(self.engine,model=ModelDouble([]))
        m=missions.create('Create a greeting program',budget=MissionBudget(max_seconds=1))
        script="from toad_core.engine import Engine; from toad_core.mission_engine import MissionEngine; import os,sys; e=Engine(sys.argv[1]); Crash=type('Crash',(),{'generate_json':lambda self,*a,**k:os._exit(77)}); MissionEngine(e,model=Crash()).run(sys.argv[2])"
        process=subprocess.run([sys.executable,'-c',script,str(self.root/'data'),m['id']],capture_output=True,timeout=5)
        self.assertEqual(process.returncode,77)
        self.engine.store.connection.execute('UPDATE missions SET lease_until=0 WHERE id=?',(m['id'],));self.engine.store.connection.commit()
        model=ModelDouble([package()]);r=MissionEngine(self.engine,model=model).run(m['id'])
        self.assertEqual(r['status'],'blocked')
        self.assertGreaterEqual(r['usage']['elapsed_seconds'],1)
        self.assertEqual(len(model.prompts),0)
