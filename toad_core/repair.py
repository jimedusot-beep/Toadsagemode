"""Bounded diagnosis and source-only repairs with frozen tests and permissions."""
import re
from .schema import PackageError,normalize_package,package_digest


def diagnose(result):
    text='\n'.join(str(t.get('stderr',''))+' '+str(t.get('error','')) for t in result.get('tests',[]))
    categories=[t.get('category') for t in result.get('tests',[]) if not t.get('passed')]
    category=next((c for c in categories if c in ('timeout','output_limit','resource_limit','cleanup_failed','worker_error','cancelled')),None)
    if not category:
        category='syntax' if 'SyntaxError' in text else 'missing_dependency' if 'ModuleNotFoundError' in text else 'permission' if 'PermissionError' in text else 'assertion_or_output'
    return {'category':category,'observations':{'passed_tests':sum(t.get('passed') is True for t in result.get('tests',[])),'failed_tests':[t.get('index',i) for i,t in enumerate(result.get('tests',[])) if not t.get('passed')],'executed':result.get('executed',False)},
            'assumptions':['The category is a heuristic; test output may be adversarial.'],'output_excerpt':text[:8000]}


def validate_repair(original,proposed):
    old=normalize_package(original);new=normalize_package(proposed)
    for field in ('name','version','entrypoint','permissions','dependencies','tests','compatibility'):
        if old[field]!=new[field]:raise PackageError('Repair cannot change '+field)
    before={f['path']:f for f in old['files']};after={f['path']:f for f in new['files']}
    if set(before)!=set(after):raise PackageError('Repair cannot add or remove file paths')
    frozen=set()
    for test in old['tests']:
        if test['kind']=='unittest':frozen.update(p for p in before if p.startswith(test['path']+'/'))
    frozen.update(p for p in before if re.search(r'(?:^|/)test[^/]*\.py$',p))
    if any(before[p]!=after[p] for p in frozen):raise PackageError('Repair cannot weaken or change test files')
    changed=[p for p in before if before[p]['content']!=after[p]['content']]
    if not changed or package_digest(old)==package_digest(new):raise PackageError('Repair made no source change; stop without a false success')
    return new,changed
