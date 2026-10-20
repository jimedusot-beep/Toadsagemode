"""Bounded, portable data contracts. No imported code runs in this module."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath

MAX_FILE_BYTES = 250_000
MAX_PACKAGE_BYTES = 512_000
MAX_BACKUP_BYTES = 2_000_000
MAX_FILES = 40
MAX_ITEMS = 100
LANGUAGES = {'.py':'Python','.js':'JavaScript','.mjs':'JavaScript','.html':'HTML','.css':'CSS',
             '.json':'JSON','.md':'Markdown','.txt':'Text','.toml':'TOML','.yaml':'YAML','.yml':'YAML','.ini':'Text','.cfg':'Text'}
STATUSES = ('received','inspected','needs_review','ready_for_testing','testing','failed','verified','installed','archived')
NAME_RE = re.compile(r'[a-z][a-z0-9_-]{1,63}\Z')
VERSION_RE = re.compile(r'\d+\.\d+\.\d+\Z')


class PackageError(ValueError):
    """An input violates the bounded package contract."""


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise PackageError('Duplicate JSON key: '+key)
            out[key] = value
        return out
    def constant(value):
        raise PackageError('Nonfinite JSON number: '+value)
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError('Invalid JSON: '+str(exc)) from exc


def json_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',',':')).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PackageError('Invalid JSON data') from exc


def safe_path(path, *, directory=False):
    if not isinstance(path, str) or not path or len(path)>180 or re.search(r'[\\:\x00-\x1f]',path):
        raise PackageError('Invalid file path')
    parts = path.split('/')
    for part in parts:
        if (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',part) or part in ('.','..')
                or part.endswith(('.', ' ')) or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',part)):
            raise PackageError('Unsafe or nonportable file path: '+path)
    if parts[0].lower() in ('toad_core','core','policy','security'):
        raise PackageError('Protected core path: '+path)
    if not directory and PurePosixPath(path).suffix.lower() not in LANGUAGES:
        raise PackageError('Unsupported source file extension: '+path)
    return path


def _strings(value, field):
    if not isinstance(value,list) or len(value)>40:
        raise PackageError(field+' must be a bounded string list')
    if any(not isinstance(x,str) or not x.strip() or len(x)>200 or re.search(r'[\x00-\x1f]',x) for x in value):
        raise PackageError('Invalid '+field+' item')
    return list(dict.fromkeys(value))


def _extensions(value):
    if not isinstance(value,dict):
        raise PackageError('extensions must be an object')
    json_bytes(value)
    return dict(value)


def normalize_package(data):
    if not isinstance(data,dict) or data.get('schema') not in ('toad-ability-v1','toad-ability-v2'):
        raise PackageError('Unsupported package schema')
    if len(json_bytes(data))>MAX_PACKAGE_BYTES:
        raise PackageError('Package exceeds 512 KB limit')
    if not isinstance(data.get('name'),str) or not NAME_RE.fullmatch(data['name']):
        raise PackageError('Invalid module name')
    if not isinstance(data.get('version'),str) or not VERSION_RE.fullmatch(data['version']):
        raise PackageError('Version must be major.minor.patch')
    description = data.get('description','')
    if not isinstance(description,str) or len(description)>4000:
        raise PackageError('Invalid description')
    entries = data.get('files')
    if not isinstance(entries,list) or not 1<=len(entries)<=MAX_FILES:
        raise PackageError('files must contain 1 to 40 entries')
    files, paths = [], set()
    for item in entries:
        if not isinstance(item,dict):
            raise PackageError('File must be an object')
        path = safe_path(item.get('path'))
        folded = path.casefold()
        if folded in paths or any(folded.startswith(p+'/') or p.startswith(folded+'/') for p in paths):
            raise PackageError('Duplicate or conflicting file path: '+path)
        paths.add(folded)
        body = item.get('content')
        if not isinstance(body,str) or '\x00' in body or len(body.encode('utf-8'))>MAX_FILE_BYTES:
            raise PackageError('Invalid or oversized file content: '+path)
        extra = _extensions(item.get('extensions',{}))
        extra.update({k:v for k,v in item.items() if k not in ('path','content','extensions')})
        files.append({'path':path,'content':body,'extensions':extra})
    entry = data.get('entrypoint',files[0]['path'])
    if not isinstance(entry,str) or entry not in {f['path'] for f in files}:
        raise PackageError('entrypoint must name a listed file')
    permissions = _strings(data.get('permissions',[]),'permissions')
    if any(not re.fullmatch(r'[a-z][a-z0-9_.:-]{0,99}',p) for p in permissions):
        raise PackageError('Invalid permission name')
    dependencies = _strings(data.get('dependencies',[]),'dependencies')
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:[<>=!~]=?[A-Za-z0-9.*+_-]+(?:,[<>=!~]=?[A-Za-z0-9.*+_-]+)*)?',p) for p in dependencies):
        raise PackageError('Dependencies must be package names/version constraints, never URLs or flags')
    raw_tests = data.get('tests',[])
    if not isinstance(raw_tests,list) or len(raw_tests)>10:
        raise PackageError('tests must be a list with at most 10 entries')
    tests, legacy = [], []
    for test in raw_tests:
        if isinstance(test,str) and data['schema']=='toad-ability-v1':
            if len(test)>1000:raise PackageError('Legacy test too large')
            legacy.append(test)
            continue
        if not isinstance(test,dict) or test.get('kind') not in ('python','unittest'):
            raise PackageError('Unsupported test specification; shell commands are never accepted')
        path = test.get('path')
        if test['kind']=='python':
            safe_path(path)
            if path not in {f['path'] for f in files} or not path.endswith('.py'):
                raise PackageError('Python test must name a listed Python file')
            expected = test.get('expected_stdout')
            if not isinstance(expected,str) or len(expected.encode('utf-8'))>16000:
                raise PackageError('Python test requires bounded expected_stdout')
            normalized = {'kind':'python','path':path,'expected_stdout':expected}
        else:
            safe_path(path,directory=True)
            if not any(f['path'].startswith(path+'/') and re.search(r'/test[^/]*\.py$',f['path']) for f in files):
                raise PackageError('Unittest directory must contain test files')
            normalized = {'kind':'unittest','path':path}
        extra = _extensions(test.get('extensions',{}))
        extra.update({k:v for k,v in test.items() if k not in ('kind','path','expected_stdout','extensions')})
        normalized['extensions'] = extra
        tests.append(normalized)
    compatibility = data.get('compatibility',{'operating_systems':['unknown']})
    if not isinstance(compatibility,dict):raise PackageError('compatibility must be an object')
    if 'operating_systems' in compatibility:_strings(compatibility['operating_systems'],'operating_systems')
    known = {'schema','name','version','description','files','entrypoint','permissions','dependencies','tests','compatibility','extensions'}
    extra = _extensions(data.get('extensions',{}))
    extra.update({k:v for k,v in data.items() if k not in known})
    if legacy:extra['legacy_tests'] = legacy
    result = {'schema':'toad-ability-v2','name':data['name'],'version':data['version'],'description':description,
              'files':files,'entrypoint':entry,'permissions':permissions,'dependencies':dependencies,
              'tests':tests,'compatibility':compatibility,'extensions':extra}
    if len(json_bytes(result))>MAX_PACKAGE_BYTES:raise PackageError('Normalized package exceeds size limit')
    return result


def content_identity(package):
    """Execution-relevant bytes; never trust a digest imported in a backup."""
    payload = {k:package[k] for k in ('entrypoint','permissions','dependencies','tests')}
    payload['files'] = sorted([{'path':f['path'],'content':f['content']} for f in package['files']],key=lambda f:f['path'])
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()


def package_digest(package):
    payload = {'identity':content_identity(package),'name':package['name'],'version':package['version']}
    return hashlib.sha256(json_bytes(payload)).hexdigest()
