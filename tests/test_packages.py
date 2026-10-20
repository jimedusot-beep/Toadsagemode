"""Nonexecution, migration, and portable input boundary regressions."""
import copy
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from toad_core.schema import PackageError, normalize_package, strict_json, package_digest
from toad_core.ingestion import ingest_text, ingest_path, migrate_library
from toad_core.inspection import inspect_package


def package(code='print("hello")\n', name='hello-demo', version='0.1.0'):
    return {'schema':'toad-ability-v2','name':name,'version':version,'description':'Harmless demonstration',
            'files':[{'path':'main.py','content':code}], 'entrypoint':'main.py', 'permissions':[],
            'dependencies':[], 'tests':[{'kind':'python','path':'main.py','expected_stdout':'hello\n'}]}


class PackageTests(unittest.TestCase):
    def test_syntax_inspection_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'must-not-exist'
            p=package(f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad")')
            r=inspect_package(normalize_package(p))
            self.assertFalse(marker.exists())
            self.assertFalse(r['executed'])
            self.assertEqual(r['safe_to_run'],'not_assessed')
            self.assertIn('pathlib',r['dependencies']['standard_library'])

    def test_fenced_multifile_preserves_original_and_safe_paths(self):
        raw='An example\n```python main.py\nprint(1)\n```\n```python tests/test_main.py\nimport unittest\n```'
        r=ingest_text(raw)
        self.assertEqual(r['content'],raw)
        self.assertEqual([f['path'] for f in r['manifest']['files']],['main.py','tests/test_main.py'])
        self.assertFalse(r['installed'])
        self.assertEqual(r['verification'],'unverified')

    def test_plain_idea_and_invalid_json_are_saved_honestly(self):
        for raw in ['Build a robot controller.','{"broken":']:
            r=ingest_text(raw)
            self.assertEqual(r['content'],raw)
            self.assertNotEqual(r['status'],'verified')
        self.assertTrue(ingest_text('{"broken":')['validation_results']['errors'])

    def test_paths_reject_aliases_and_protected_core(self):
        for path in ['../a.py','/root.py','C:/x.py','a\\x.py','toad_core/main.py','.git/hook.py','CON.py','a./x.py','a//x.py','a/../x.py']:
            with self.subTest(path=path):
                p=package();p['files'][0]['path']=path;p['entrypoint']=path
                with self.assertRaises(PackageError):normalize_package(p)
        p=package();p['files'].append({'path':'MAIN.py','content':'other'})
        with self.assertRaises(PackageError):normalize_package(p)

    def test_limits_permissions_and_tests_are_validated(self):
        for changes in [
            {'permissions':[{'admin':True}]},
            {'files':[{'path':'main.py','content':'x'*250001}]},
            {'tests':['python main.py']},
            {'tests':[{'kind':'shell','command':'echo unsafe'}]},
            {'tests':[{'kind':'python','path':'missing.py','expected_stdout':''}]},
            {'dependencies':['--index-url=https://evil.example']},
        ]:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(PackageError):normalize_package({**package(),**changes})

    def test_strict_json_rejects_duplicates_and_nonfinite(self):
        for raw in ['{"a":1,"a":2}','{"x":NaN}','{"x":Infinity}']:
            with self.assertRaises(PackageError):strict_json(raw)

    def test_syntax_errors_and_external_imports_need_review(self):
        broken=inspect_package(normalize_package(package('def nope(:\n')))
        self.assertTrue(broken['errors'])
        external=inspect_package(normalize_package(package('import requests\nprint(1)')))
        self.assertIn('requests',external['dependencies']['third_party'])
        self.assertFalse(external['ready_for_testing'])

    def test_semantic_digest_ignores_description_but_binds_tests_and_permissions(self):
        p=normalize_package(package());d=package_digest(p)
        p['description']='New prose';self.assertEqual(package_digest(p),d)
        p['tests'][0]['expected_stdout']='different';self.assertNotEqual(package_digest(p),d)

    def test_unknown_manifest_and_file_metadata_survives(self):
        p=package();p['custom']={'owner':'Jimmy'};p['files'][0]['license']='example'
        r=normalize_package(p)
        self.assertEqual(r['extensions']['custom'],{'owner':'Jimmy'})
        self.assertEqual(r['files'][0]['extensions']['license'],'example')
        self.assertEqual(normalize_package(r),r)

    def test_legacy_shell_tests_remain_disabled(self):
        p=package();p['schema']='toad-ability-v1';p['tests']=['python main.py']
        r=normalize_package(p)
        self.assertEqual(r['tests'],[])
        self.assertEqual(r['extensions']['legacy_tests'],['python main.py'])
        self.assertFalse(inspect_package(r)['ready_for_testing'])

    def test_library_import_retains_source_extras_and_downgrades_claims(self):
        data={'schema':'toad-library-v1','extra':'top','abilities':[{'name':'legacy-demo','content':'print(1)','source':'Gemini','custom':{'keep':True},'version':'0.1.0','status':'unverified','installed':False}]}
        out=migrate_library(data)
        r=out['abilities'][0]
        self.assertEqual(r['source'],'Gemini')
        self.assertTrue(r['extensions']['original']['custom']['keep'])
        self.assertEqual(out['extensions']['original']['extra'],'top')
        r['status']='installed';r['installed']=True;r['test_results']=[{'passed':True}]
        again=migrate_library(out)['abilities'][0]
        self.assertFalse(again['installed'])
        self.assertEqual(again['verification'],'unverified')
        self.assertEqual(again['test_results'],[])

    def test_zip_never_extracts_and_rejects_traversal_links_and_bombs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bundle.zip'
            for filename,body,mode in [('main.py','print(1)',None),('../escape.py','bad',None),('link.py','target',stat.S_IFLNK|0o777),('bomb.py','x'*250001,None)]:
                with self.subTest(filename=filename):
                    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                        if mode:
                            entry=zipfile.ZipInfo(filename);entry.create_system=3;entry.external_attr=mode<<16;z.writestr(entry,body)
                        else:z.writestr(filename,body)
                    if filename=='main.py':self.assertEqual(ingest_path(path)['manifest']['files'][0]['path'],'main.py')
                    else:
                        with self.assertRaises(PackageError):ingest_path(path)
            self.assertFalse((Path(tmp)/'escape.py').exists())

    def test_url_is_stored_as_reference_without_retrieval(self):
        r=ingest_text('https://github.com/example/project')
        self.assertIn('reference',r['validation_results']['input_kind'])
        self.assertEqual(r['status'],'needs_review')

class ZipManifestCollisionTests(unittest.TestCase):
    def test_manifest_zip_rejects_duplicate_members_instead_of_dropping_source(self):
        import warnings
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'duplicate.zip'
            for entries in [
                [('toad-ability.json',json.dumps(package())),('main.py','first copy'),('main.py','print("hello")\n')],
                [('toad-ability.json',json.dumps(package())),('toad-ability.json',json.dumps(package())),('main.py','print("hello")\n')],
                [('toad-ability.json',json.dumps(package())),('MAIN.py','first copy'),('main.py','print("hello")\n')],
            ]:
                with self.subTest(paths=[x[0] for x in entries]):
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore',UserWarning)
                        with zipfile.ZipFile(target,'w') as z:
                            for filename,body in entries:z.writestr(filename,body)
                    with self.assertRaises(PackageError):ingest_path(target)
