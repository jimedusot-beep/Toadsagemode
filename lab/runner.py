"""Trusted in-container intake and test selection; never run on the host."""
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import sys
import unittest


def main():
    raw=sys.stdin.buffer.read(512001)
    if len(raw)>512000:raise ValueError('Package too large')
    package=json.loads(raw)
    files=package['files']
    if not isinstance(files,list) or not 1<=len(files)<=40:raise ValueError('Invalid files')
    root=Path('/work')
    seen=set()
    for f in files:
        path=f['path'];p=PurePosixPath(path)
        if p.is_absolute() or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*',path) or any(x in ('','..','.') for x in path.split('/')):raise ValueError('Unsafe path')
        if path.casefold() in seen:raise ValueError('Duplicate path')
        seen.add(path.casefold())
        body=f['content'].encode('utf-8')
        if len(body)>250000:raise ValueError('Source too large')
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as out:out.write(body)
    spec=package['tests'][int(sys.argv[1])]
    path=spec['path']
    if not isinstance(path,str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*',path) or any(x in ('','..','.') for x in path.split('/')):raise ValueError('Unsafe test path')
    os.chdir(root);sys.path.insert(0,str(root));sys.dont_write_bytecode=True
    if spec['kind']=='python':
        if path not in {f['path'] for f in files}:raise ValueError('Missing test file')
        sys.argv=[path];runpy.run_path(str(root/path),run_name='__main__')
    elif spec['kind']=='unittest':
        suite=unittest.defaultTestLoader.discover(str(root/path),pattern='test*.py')
        if suite.countTestCases()==0:raise ValueError('No tests discovered')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():raise SystemExit(1)
    else:raise ValueError('Unsupported test kind')


if __name__=='__main__':main()
