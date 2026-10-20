import unittest
from tools.validate_feed import validate

class ValidatorTests(unittest.TestCase):
    def package(self,code):
        return {"schema":"toad-ability-v1","name":"sample","version":"0.1.0","files":[{"path":"main.py","content":code}],"entrypoint":"main.py","permissions":[],"tests":[]}

    def test_structural_safe_no_execution(self):
        errors,warnings=validate(self.package("print('hello')"))
        self.assertEqual(errors,[])
        self.assertEqual(warnings,[])

    def test_detect_sensitive_operations(self):
        for content,word in [("os.system('echo hi')","dynamic"),("shutil.rmtree('/tmp/x')","deletion"),("requests.get('https://example.com')","network"),("api_key = 'abc'","secret")]:
            with self.subTest(content=content):
                errors,warnings=validate(self.package(content))
                self.assertFalse(errors)
                self.assertTrue(any(word in w for w in warnings),warnings)

    def test_reject_path_traversal(self):
        p=self.package("print(1)")
        p["files"][0]["path"]="../escape.py"
        errors,_=validate(p)
        self.assertTrue(any("unsafe path" in e for e in errors),errors)
