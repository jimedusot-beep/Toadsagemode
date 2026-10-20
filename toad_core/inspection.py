"""Static observations and explicitly uncertain inferences, without imports/eval."""
from __future__ import annotations
import ast
import re
import sys
from pathlib import PurePosixPath
from .schema import LANGUAGES, normalize_package

FLAGS = [
    (r'\b(?:eval\s*\(|exec\s*\(|os\.system|subprocess\.)','dynamic/host command execution'),
    (r'\b(?:shutil\.rmtree|os\.remove|unlink\s*\()','file deletion'),
    (r'\b(?:requests\.|urllib\.|fetch\s*\(|https?://)','network access or reference URL'),
    (r'\b(?:password|secret|api[_-]?key|private[_-]?key|token)\s*[:=]|BEGIN [A-Z ]*PRIVATE KEY','potential secret'),
    (r'\b(?:sudo|chmod|chown|docker\s+run)','privilege operation'),
    (r'(?:[\'\"](?:/(?:home|root|Users|etc|proc|sys)/|[A-Z]:\\)|\.\./)','outside-workspace path indicator'),
]


def inspect_package(package):
    p = normalize_package(package)
    errors, warnings, checked, unchecked, imports = [], [], [], [], set()
    locals_ = {PurePosixPath(f['path']).parts[0].removesuffix('.py') for f in p['files']}
    languages = sorted({LANGUAGES[PurePosixPath(f['path']).suffix.lower()] for f in p['files']})
    systems = set()
    for f in p['files']:
        path, content = f['path'], f['content']
        suffix = PurePosixPath(path).suffix.lower()
        if suffix=='.py':
            try:
                tree = ast.parse(content,filename=path)
                for node in ast.walk(tree):
                    if isinstance(node,ast.Import):imports.update(a.name.split('.')[0] for a in node.names)
                    elif isinstance(node,ast.ImportFrom) and node.module and not node.level:imports.add(node.module.split('.')[0])
                checked.append(path)
            except (SyntaxError,ValueError,RecursionError,MemoryError) as exc:
                errors.append(f'{path}: Python syntax: {getattr(exc,"msg",str(exc))} (line {getattr(exc,"lineno",None)})')
        elif suffix=='.json':
            from .schema import strict_json, PackageError
            try:strict_json(content);checked.append(path)
            except PackageError:errors.append(path+': invalid JSON syntax')
        else:unchecked.append(path)
        for pattern, message in FLAGS:
            if re.search(pattern,content,re.I):warnings.append(path+': '+message)
        if re.search(r'\b(?:win32|winreg|msvcrt|COM\d+)\b',content):systems.add('Windows indication')
        if re.search(r'/dev/|\b(?:termios|fcntl)\b',content):systems.add('POSIX indication')
    stdlib = sorted(imports & set(sys.stdlib_module_names))
    external = sorted(imports-set(stdlib)-locals_)
    if p['permissions']:warnings.append('Requested permissions require policy review; default grant is empty')
    if p['extensions'].get('legacy_tests'):warnings.append('Legacy shell-style tests are preserved but disabled')
    if p['dependencies'] or external:warnings.append('External dependencies are unresolved; nothing will be installed automatically')
    input_kind = 'source' if any(l in ('Python','JavaScript','HTML','CSS') for l in languages) else 'notes_or_data'
    if all(re.fullmatch(r'\s*https?://\S+\s*',f['content']) for f in p['files']):
        input_kind='reference_url';warnings.append('Reference saved without remote retrieval')
    python_tests = bool(p['tests']) and all(t['kind'] in ('python','unittest') for t in p['tests'])
    ready = not errors and not warnings and python_tests and not any(f['path'].endswith('.py') for f in p['files'] if f['path'] in unchecked)
    return {'schema':'toad-inspection-v2','valid_structure':True,'errors':errors,'warnings':sorted(set(warnings)),
            'observations':[f'{len(p["files"])} bounded text/source files','Languages: '+', '.join(languages),'Declared tests: '+str(len(p['tests']))],
            'assumptions':['Purpose is taken from the supplied description, not independently verified.',
                           'Syntax checks do not establish completeness or safety.',
                           'Unlisted operating systems and hardware compatibility remain unknown.'],
            'purpose':p['description'] or 'Not specified','input_kind':input_kind,'languages':languages,
            'dependencies':{'declared':p['dependencies'],'standard_library':stdlib,'third_party':external},
            'compatibility':{'declared':p['compatibility'],'indicators':sorted(systems),'verified':False},
            'syntax_checked':checked,'syntax_unchecked':unchecked,'ready_for_testing':ready,
            'executed':False,'safe_to_run':'not_assessed'}


def status_for_report(report):
    if report['ready_for_testing']:return 'ready_for_testing'
    return 'needs_review' if report['errors'] or report['warnings'] else 'inspected'
