"""Legacy file converter; use Engine.ingest_path for the transactional catalog."""
from pathlib import Path
from .ingestion import read_bounded,migrate_library
from .schema import MAX_BACKUP_BYTES,MAX_FILE_BYTES,NAME_RE,VERSION_RE,PackageError,strict_json,json_bytes

MAX_IMPORT_BYTES=MAX_BACKUP_BYTES


def import_browser_library(source,destination):
    data=strict_json(read_bounded(source,MAX_IMPORT_BYTES))
    if not isinstance(data,dict) or data.get('schema') not in ('toad-library-v1','toad-library-v2') or not isinstance(data.get('abilities'),list) or len(data['abilities'])>100:raise PackageError('Unsupported library format')
    if data['schema']=='toad-library-v2':catalog=migrate_library(data)
    else:
        records=[]
        for item in data['abilities']:
            if not isinstance(item,dict) or item.get('status')!='unverified' or item.get('installed') is not False:raise PackageError('Imported legacy abilities must be unverified and not installed')
            name,body,version=item.get('name'),item.get('content'),item.get('version','0.1.0')
            if not isinstance(name,str) or not NAME_RE.fullmatch(name) or not isinstance(body,str) or len(body.encode('utf-8'))>MAX_FILE_BYTES:raise PackageError('Invalid legacy record')
            if not isinstance(version,str) or not VERSION_RE.fullmatch(version):raise PackageError('Invalid legacy version')
            if not isinstance(item.get('source','browser-import'),str) or not isinstance(item.get('description',''),str):raise PackageError('Invalid legacy metadata')
            records.append({**item,'version':version,'source':item.get('source','browser-import'),'status':'unverified','installed':False})
        catalog={**data,'abilities':records}
    raw=json_bytes(catalog)
    if len(raw)>MAX_IMPORT_BYTES:raise PackageError('Converted catalog exceeds limit')
    dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive create closes the old exists()/write() race and never overwrites a catalog.
    try:
        with dest.open('xb') as out:out.write(raw+b'\n')
    except FileExistsError as exc:raise PackageError('Destination exists; refuse to overwrite an existing library') from exc
    return len(catalog['abilities'])
