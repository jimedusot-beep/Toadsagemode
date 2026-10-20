"""Text/source/ZIP and versioned backup intake. Never extracts or executes code."""
from __future__ import annotations
import json
import re
import stat
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from .schema import (PackageError, MAX_FILE_BYTES, MAX_PACKAGE_BYTES, MAX_BACKUP_BYTES, MAX_FILES, MAX_ITEMS,
                     NAME_RE, LANGUAGES, normalize_package, strict_json, json_bytes, safe_path, package_digest, content_identity)
from .inspection import inspect_package, status_for_report


def timestamp():return datetime.now(timezone.utc).isoformat()


def slug(value):
    name = re.sub(r'[^a-z0-9]+','-',value.lower()).strip('-')[:64] or 'new-ability'
    if not name[0].isalpha():name='toad-'+name
    if len(name)<2:name+='-ability'
    return name[:64]


def detect(text):
    if re.search(r'^\s*(?:from\s+\w+\s+import|import\s+\w+|def\s+\w+\s*\(|class\s+\w+|print\s*\()',text,re.M):return 'Python','py'
    if re.search(r'^\s*(?:<!doctype html|<(?:html|div|body|img|h[1-6]|p|script)\b)',text,re.I):return 'HTML','html'
    if re.search(r'^\s*[\[{]',text):return 'JSON','json'
    if re.search(r'\b(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=|console\.log\s*\()',text):return 'JavaScript','js'
    if re.search(r'^[.#]?[\w-]+\s*\{[^}]*:[^}]*\}',text,re.M):return 'CSS','css'
    return 'Text','md'


def candidate(package, content, *, source='manual paste', extensions=None):
    p=normalize_package(package); report=inspect_package(p); stamp=timestamp()
    return {'id':str(uuid.uuid4()),'name':p['name'],'description':p['description'],'version':p['version'],'source':source,
            'created_at':stamp,'updated_at':stamp,'language':', '.join(report['languages']),'content':content,'manifest':p,
            'dependencies':p['dependencies'],'permissions':p['permissions'],'compatibility':p['compatibility'],
            'digest':package_digest(p),'content_identity':content_identity(p),'status':status_for_report(report),
            'verification':'unverified','installed':False,'validation_results':report,'test_results':[],
            'previous_versions':[],'rollback':None,'related_missions':[],
            'history':[{'event':'received','at':stamp},{'event':'inspected','at':stamp}], 'extensions':extensions or {}}


def ingest_text(text, *, filename=None, name=None, source='manual paste', description=None):
    if not isinstance(text,str) or not text.strip():raise PackageError('Empty feed')
    maximum=MAX_PACKAGE_BYTES if filename and str(filename).endswith('.json') else MAX_FILE_BYTES
    if len(text.encode('utf-8'))>maximum:raise PackageError('Feed exceeds size limit')
    parsed=None
    if text.lstrip().startswith(('{','[')):
        try:parsed=strict_json(text)
        except PackageError:pass  # ordinary malformed JSON is saved for inspection, never executed
    if isinstance(parsed,dict) and str(parsed.get('schema','')).startswith('toad-ability-'):
        p=normalize_package(parsed)
        if name:p['name']=slug(name)
        if description is not None:p['description']=description
        return candidate(p,text,source=source)
    if isinstance(parsed,dict) and parsed.get('schema')=='toad-feed-v1':
        body=parsed.get('content')
        if not isinstance(body,str):raise PackageError('Invalid legacy feed content')
        r=ingest_text(body,name=name,source=parsed.get('source',source),description=description)
        r['extensions']['original_feed']=parsed
        return r
    files=[]
    aliases={'python':'py','py':'py','javascript':'js','js':'js','html':'html','css':'css','json':'json','markdown':'md','md':'md','text':'txt','txt':'txt'}
    for i, match in enumerate(re.finditer(r'^```([^\n\r]*)\r?\n(.*?)^```\s*$',text,re.M|re.S),1):
        info=match[1].strip().split();ext=aliases.get(info[0].lower(),'txt') if info else 'txt'
        files.append({'path':info[1] if len(info)>1 else f'part-{i}.{ext}','content':match[2]})
    if len(files)==1 and files[0]['path'].startswith('part-1.') and not filename:files[0]['path']='main.'+files[0]['path'].split('.')[-1]
    kind,ext=detect(text)
    if not files:files=[{'path':filename or ('notes.md' if ext=='md' else 'main.'+ext),'content':text}]
    title=name or ('project-package' if len(files)>1 else (text.strip().split('\n')[0][:55] if kind=='Text' else kind+'-ability'))
    p={'schema':'toad-ability-v2','name':slug(title),'version':'0.1.0','description':description if description is not None else text.strip().split('\n')[0][:300],
       'files':files,'entrypoint':files[0]['path'],'permissions':[],'dependencies':[],'tests':[]}
    return candidate(p,text,source=source)


def read_bounded(path,maximum):
    with Path(path).open('rb') as f:raw=f.read(maximum+1)
    if len(raw)>maximum:raise PackageError('Input exceeds size limit')
    return raw


def ingest_zip(path, *, name=None, source=None):
    read_bounded(path,MAX_PACKAGE_BYTES)
    files,total=[],0
    seen_entries=set();directory_spellings={};file_paths=set()
    try:
        with zipfile.ZipFile(path) as archive:
            if len(archive.infolist())>MAX_FILES+20:raise PackageError('Too many ZIP entries')
            for info in archive.infolist():
                entry_path=info.filename.rstrip('/')
                safe_path(entry_path,directory=info.is_dir())
                folded=entry_path.casefold()
                if folded in seen_entries:raise PackageError('Duplicate ZIP member path')
                seen_entries.add(folded)
                parts=entry_path.split('/')
                for length in range(1,len(parts)+(1 if info.is_dir() else 0)):
                    prefix='/'.join(parts[:length]);key=prefix.casefold()
                    if key in file_paths or key in directory_spellings and directory_spellings[key]!=prefix:raise PackageError('Conflicting ZIP directory path')
                    directory_spellings[key]=prefix
                if not info.is_dir():
                    if folded in directory_spellings:raise PackageError('Conflicting ZIP file/directory path')
                    file_paths.add(folded)
                if stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:raise PackageError('ZIP links/encryption are unsupported')
                mode=stat.S_IFMT(info.external_attr>>16)
                if mode not in (0,stat.S_IFREG,stat.S_IFDIR):raise PackageError('ZIP contains a special file')
                if info.is_dir():continue
                total+=info.file_size
                if info.file_size>MAX_FILE_BYTES or total>MAX_PACKAGE_BYTES or info.file_size>max(1,info.compress_size)*100:
                    raise PackageError('ZIP expansion or file size exceeds limit')
                raw=archive.read(info)
                if len(raw)!=info.file_size:raise PackageError('ZIP file size mismatch')
                files.append({'path':info.filename,'content':raw.decode('utf-8-sig')})
                if len(files)>MAX_FILES:raise PackageError('Too many ZIP source files')
    except (zipfile.BadZipFile,UnicodeError,RuntimeError) as exc:raise PackageError('Invalid ZIP/text source') from exc
    if not files:raise PackageError('ZIP contains no supported source files')
    manifests=[f for f in files if f['path']=='toad-ability.json']
    if manifests:
        p=normalize_package(strict_json(manifests[0]['content']))
        actual={f['path']:f['content'] for f in files if f['path']!='toad-ability.json'}
        expected={f['path']:f['content'] for f in p['files']}
        if actual and actual!=expected:raise PackageError('ZIP contents differ from embedded manifest')
    else:
        p={'schema':'toad-ability-v2','name':slug(name or Path(path).stem),'version':'0.1.0','description':'Uploaded ZIP project',
           'files':files,'entrypoint':next((f['path'] for f in files if f['path'].endswith('.py')),files[0]['path']),
           'dependencies':[],'permissions':[],'tests':[]}
    return candidate(p,'Uploaded ZIP project',source=source or str(Path(path).name))


def ingest_path(path, *, name=None, source=None):
    path=Path(path)
    if path.suffix.lower()=='.zip':return ingest_zip(path,name=name,source=source)
    safe_path(path.name)
    raw=read_bounded(path,MAX_BACKUP_BYTES if path.suffix.lower()=='.json' else MAX_FILE_BYTES)
    try:text=raw.decode('utf-8-sig')
    except UnicodeError as exc:raise PackageError('Only UTF-8 text/source files are supported') from exc
    if path.suffix.lower()=='.json':
        try:parsed=strict_json(text)
        except PackageError:parsed=None
        if isinstance(parsed,dict) and str(parsed.get('schema','')).startswith('toad-library-'):return migrate_library(parsed)
    return ingest_text(text,filename=path.name,name=name,source=source or path.name)


def migrate_library(data):
    if not isinstance(data,dict) or data.get('schema') not in ('toad-library-v1','toad-library-v2'):
        raise PackageError('Unsupported library schema')
    if len(json_bytes(data))>MAX_BACKUP_BYTES or not isinstance(data.get('abilities'),list) or len(data['abilities'])>MAX_ITEMS:
        raise PackageError('Invalid or oversized library')
    result=[];ids=set()
    for old in data['abilities']:
        if not isinstance(old,dict) or not isinstance(old.get('content'),str) or not isinstance(old.get('name'),str) or not NAME_RE.fullmatch(old['name']):
            raise PackageError('Invalid ability record')
        source=old.get('source','backup import')
        if not isinstance(source,str) or len(source)>200:raise PackageError('Invalid source')
        description=old.get('description','')
        if not isinstance(description,str):raise PackageError('Invalid description')
        if 'manifest' in old:r=candidate(normalize_package(old['manifest']),old['content'],source=source)
        else:r=ingest_text(old['content'],name=old['name'],source=source,description=description)
        identifier=old.get('id')
        if identifier is not None:
            if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identifier) or identifier in ids:raise PackageError('Invalid or duplicate identifier')
            r['id']=identifier
        ids.add(r['id'])
        r['extensions']={'original':old}
        if old.get('status')=='archived':r['status']='archived'
        r['created_at']=old.get('created_at',r['created_at'])
        r['history'].append({'event':'backup_imported_unverified','at':timestamp()})
        result.append(r)
    return {'schema':'toad-library-v2','schema_version':2,'abilities':result,
            'extensions':{'original':{k:v for k,v in data.items() if k!='abilities'}}}
