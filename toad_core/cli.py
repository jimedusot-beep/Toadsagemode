"""Documented offline CLI. JSON output is suitable for scripting and reports."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .engine import Engine
from .schema import PackageError, STATUSES, MAX_PACKAGE_BYTES


def parser():
    p=argparse.ArgumentParser(prog='toad',description='Toad Sage local absorption engine')
    p.add_argument('--workspace',help='Private catalog directory; defaults outside this repository')
    commands=p.add_subparsers(dest='command',required=True)
    ingest=commands.add_parser('ingest',help='Ingest text/source/manifest/ZIP/backup without execution');ingest.add_argument('path',help='File path, or - for UTF-8 text on stdin');ingest.add_argument('--name');ingest.add_argument('--source')
    inspect=commands.add_parser('inspect');inspect.add_argument('id')
    lib=commands.add_parser('library');sub=lib.add_subparsers(dest='action',required=True)
    listing=sub.add_parser('list');listing.add_argument('--search',default='');listing.add_argument('--status',choices=STATUSES);listing.add_argument('--language')
    for action in ('show','archive','restore','delete','install'):
        item=sub.add_parser(action);item.add_argument('id')
    commands.add_parser('status')
    empathy=commands.add_parser('empathy',help='Private conversational reference lessons, never executable abilities')
    es=empathy.add_subparsers(dest='action',required=True)
    en=es.add_parser('note');en.add_argument('text');en.add_argument('--audience',choices=['adult','child','general'],default='general')
    ei=es.add_parser('import');ei.add_argument('path');ei.add_argument('--audience',choices=['adult','child','general'],default='general')
    el=es.add_parser('list');el.add_argument('--search',default='');el.add_argument('--audience',choices=['adult','child','general']);el.add_argument('--reviewed',action='store_true')
    for action in ('show','delete'):
        command=es.add_parser(action);command.add_argument('id')
    er=es.add_parser('review');er.add_argument('id');er.add_argument('status',choices=['needs_review','helpful','inappropriate','needs_revision']);er.add_argument('--note',required=True)
    ee=es.add_parser('edit');ee.add_argument('id');ee.add_argument('path',help='JSON object containing corrected lesson content fields')
    ex=es.add_parser('export');ex.add_argument('--output');ex.add_argument('--force',action='store_true')
    ec=es.add_parser('compare');ec.add_argument('scenario');ec.add_argument('--audience',choices=['adult','child','general'],default='adult');ec.add_argument('--output')
    ev=es.add_parser('evaluate');ev.add_argument('--split',choices=['practice','heldout'],required=True);ev.add_argument('--id',required=True);ev.add_argument('--output')
    skills=commands.add_parser('skills',help='Quarantined skill descriptions')
    sk=skills.add_subparsers(dest='action',required=True)
    imp=sk.add_parser('import');imp.add_argument('path');imp.add_argument('--kind',choices=['knowledge','workflow','executable'],default='knowledge');imp.add_argument('--permission',action='append',default=[])
    ls=sk.add_parser('list');ls.add_argument('--search',default='');ls.add_argument('--kind',choices=['knowledge','workflow','executable'])
    agent=commands.add_parser('agent',help='Experimental bounded candidate agent')
    ast=agent.add_subparsers(dest='action',required=True)
    ar=ast.add_parser('run');ar.add_argument('id');ar.add_argument('--candidate-id',required=True);ar.add_argument('--goal',required=True)
    at=ast.add_parser('trace');at.add_argument('id');at.add_argument('--candidate-id',required=True)

    bridge=commands.add_parser('bridge',help='Start loopback-only private phone bridge (no remote execution)')
    bridge.add_argument('--port',type=int,default=8765)
    doctor=commands.add_parser('doctor',help='Check local readiness without running candidate code')
    doctor.add_argument('--probe',action='store_true',help='Also query local Docker and Ollama metadata; no downloads or candidate execution')
    model=commands.add_parser('model');model.add_argument('action',choices=['status'])
    mission=commands.add_parser('mission');ms=mission.add_subparsers(dest='action',required=True)
    mc=ms.add_parser('create');mc.add_argument('goal');mc.add_argument('--max-model-calls',type=int,default=6);mc.add_argument('--max-test-runs',type=int,default=4);mc.add_argument('--max-repairs',type=int,default=2);mc.add_argument('--max-seconds',type=float,default=180)
    ms.add_parser('list')
    for action in ('show','run','pause','resume','cancel','report'):
        item=ms.add_parser(action);item.add_argument('id')
        if action=='run':item.add_argument('--steps',type=int,default=20)
    test=commands.add_parser('test',help='Run configured tests only in the restricted Docker worker');test.add_argument('id')
    lab=commands.add_parser('lab');lab.add_argument('action',choices=['status'])
    for action in ('rollback','deactivate'):
        command=sub.add_parser(action);command.add_argument('name')
    sub.add_parser('active')
    export=commands.add_parser('export');export.add_argument('--output');export.add_argument('--id',action='append',dest='ids');export.add_argument('--force',action='store_true')
    queue=commands.add_parser('queue');qs=queue.add_subparsers(dest='action',required=True);qi=qs.add_parser('inspect');qi.add_argument('id');qr=qs.add_parser('run');qr.add_argument('--limit',type=int,default=10)
    logs=commands.add_parser('logs');logs.add_argument('--limit',type=int,default=100)
    return p


def write_output(path,data,force=False):
    target=Path(path).expanduser();target.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive create protects existing files; replace is only enabled by explicit --force.
    if not force:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False);f.write('\n')
    else:
        import tempfile
        fd,temp=tempfile.mkstemp(prefix='.toad-export-',dir=target.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False);f.write('\n')
            os.replace(temp,target)
        finally:
            if Path(temp).exists():Path(temp).unlink()
    return {'saved':str(target.resolve())}


def dispatch(engine,args):
    if args.command=='empathy':
        from .empathy import EmpathyLibrary
        from .schema import strict_json
        catalog=EmpathyLibrary(engine.store)
        def read_text(path,limit=2_000_000):
            source=Path(path)
            if source.is_symlink() or not source.is_file() or source.stat().st_size>limit:raise PackageError('Unsafe or oversized empathy input')
            with source.open('rb') as stream:raw=stream.read(limit+1)
            if len(raw)>limit:raise PackageError('Empathy input exceeds limit')
            return raw.decode('utf-8-sig')
        if args.action=='note':return catalog.ingest(args.text,audience=args.audience)
        if args.action=='import':
            text=read_text(args.path)
            if Path(args.path).suffix.lower()=='.json':return catalog.import_data(strict_json(text))
            if Path(args.path).suffix.lower() not in ('.txt','.md'):raise PackageError('Use UTF-8 .txt, .md or a JSON lesson library')
            return catalog.ingest(text,audience=args.audience)
        if args.action=='list':return catalog.search(args.search,audience=args.audience,reviewed_only=args.reviewed)
        if args.action=='show':return catalog.get(args.id)
        if args.action=='review':return catalog.review(args.id,args.status,args.note)
        if args.action=='edit':return catalog.edit(args.id,strict_json(read_text(args.path)))
        if args.action=='delete':catalog.delete(args.id);return {'deleted':args.id}
        if args.action=='export':
            data=catalog.export()
            return write_output(args.output,data,args.force) if args.output else data
        if args.action=='evaluate':
            data=strict_json(read_text(Path(__file__).resolve().parents[1]/'empathy'/(args.split+'.json')))
            matches=[item for item in data['scenarios'] if item['id']==args.id]
            if not matches:raise PackageError('Unknown scenario in selected split')
            item=matches[0];report=catalog.compare(item['prompt'],audience=item['audience'])
            report.update({'split':args.split,'scenario_id':item['id']})
        else:report=catalog.compare(args.scenario,audience=args.audience)
        return write_output(args.output,report) if args.output else report
    if args.command=='skills':
        from .skills import SkillCatalog
        registry=SkillCatalog(engine.store.workspace)
        if args.action=='list':return registry.search(args.search,kind=args.kind)
        source=Path(args.path)
        if source.is_symlink() or source.stat().st_size>120000:raise PackageError('Unsafe/oversized skill input')
        return registry.register(source.read_text(encoding='utf-8'),kind=args.kind,permissions=args.permission,compatibility={})
    if args.command=='agent':
        from .controlled_agent import ControlledAgent
        controller=ControlledAgent(engine,args.id,candidate_id=args.candidate_id)
        return controller.run(args.goal) if args.action=='run' else controller.state
    if args.command=='ingest':
        options={k:v for k,v in {'name':args.name,'source':args.source}.items() if v is not None}
        if args.path=='-':
            raw=sys.stdin.buffer.read(MAX_PACKAGE_BYTES+1)
            if len(raw)>MAX_PACKAGE_BYTES:raise PackageError('Standard input exceeds limit')
            return engine.ingest_text(raw.decode('utf-8-sig'),**options)
        return engine.ingest_path(args.path,**options)
    if args.command=='inspect':return engine.inspect(args.id)
    if args.command=='status':return engine.status()
    if args.command=='model':
        from .models import OllamaAdapter
        return OllamaAdapter().availability()
    if args.command=='mission':
        from .mission_engine import MissionEngine,MissionBudget
        missions=MissionEngine(engine)
        if args.action=='create':return missions.create(args.goal,budget=MissionBudget(max_model_calls=args.max_model_calls,max_test_runs=args.max_test_runs,max_repairs=args.max_repairs,max_seconds=args.max_seconds))
        if args.action=='list':return missions.list()
        if args.action=='run':return missions.run(args.id,max_steps=args.steps)
        if args.action in ('show','report'):return missions.get(args.id)
        return getattr(missions,args.action)(args.id)
    if args.command=='lab':
        from .lab import DockerWorker
        return DockerWorker().availability()
    if args.command=='test':return engine.test(args.id)
    if args.command=='library':
        if args.action in ('install','rollback','deactivate','active'):
            from .installation import Registry
            registry=Registry(engine)
            if args.action=='install':return registry.activate(args.id)
            if args.action=='rollback':return registry.rollback(args.name)
            if args.action=='deactivate':return registry.deactivate(args.name)
            return [json.loads(r[0]) for r in engine.store.connection.execute('SELECT document FROM activations')]
        if args.action=='list':return engine.list(query=args.search,status=args.status,language=args.language)
        if args.action=='show':return engine.get(args.id)
        if args.action in ('archive','restore'):return engine.archive(args.id,restore=args.action=='restore')
        engine.delete(args.id);return {'deleted':args.id}
    if args.command=='export':
        data=engine.export(ids=args.ids)
        return write_output(args.output,data,args.force) if args.output else data
    if args.command=='queue':return {'job_id':engine.queue_inspection(args.id)} if args.action=='inspect' else engine.run_queue(args.limit)
    if args.command=='logs':return engine.store.events(args.limit)
    raise PackageError('Unsupported command')


def main(argv=None):
    args=parser().parse_args(argv);engine=None
    try:
        if args.command=='doctor':
            from .readiness import readiness
            result=readiness(args.workspace,probe=args.probe)
            print(json.dumps(result,indent=2,ensure_ascii=False))
            if result['capabilities']['library']!='ready':return 1
            return 2 if args.probe and result['capabilities']['missions']!='ready' else 0
        if args.command=='bridge':
            from .bridge import serve
            if not 1024<=args.port<=65535:raise ValueError('Choose an unprivileged port 1024–65535')
            serve(args.workspace,args.port)
            return 0
        engine=Engine(args.workspace);result=dispatch(engine,args)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if args.command=='test' and not result.get('passed'):return 1
        if args.command in ('lab','model') and not result.get('available'):return 2
        if args.command=='mission' and args.action=='run' and result.get('status')=='blocked':return 2
        return 0
    except (ValueError,OSError,KeyError,RuntimeError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)}),file=sys.stderr);return 1
    finally:
        if engine:engine.close()
