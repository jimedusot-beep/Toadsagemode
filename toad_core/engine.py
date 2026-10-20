"""Local absorption orchestration; imported code is data until Docker tests."""
from __future__ import annotations
import json
import os
from pathlib import Path
from . import ingestion
from .inspection import inspect_package, status_for_report
from .schema import PackageError, STATUSES, MAX_BACKUP_BYTES, json_bytes, package_digest
from .storage import Store


def default_workspace():
    override=os.environ.get('TOAD_WORKSPACE')
    if override:return Path(override).expanduser()
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'ToadSage'
    return Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))/'toad-sage'


class Engine:
    def __init__(self,workspace=None):self.store=Store(workspace or default_workspace())
    def close(self):self.store.close()
    def get(self,identifier):return self.store.get(identifier)
    def ingest_text(self,text,**options):return self.store.put(ingestion.ingest_text(text,**options))
    def ingest_package(self,package,*,source='manual package',content=None):
        return self.store.put(ingestion.candidate(package,content if content is not None else 'Structured source package',source=source))
    def ingest_path(self,path,**options):
        data=ingestion.ingest_path(path,**options)
        if data.get('schema')=='toad-library-v2':
            results=self.store.put_many(data['abilities'],data.get('extensions'))
            return {'imported':sum(not r['duplicate'] for r in results),'duplicates':sum(r['duplicate'] for r in results),'ids':[r['id'] for r in results]}
        return self.store.put(data)
    def import_library(self,data):
        lib=ingestion.migrate_library(data)
        return self.store.put_many(lib['abilities'],lib.get('extensions'))
    def list(self,*,query='',status=None,language=None):
        if status and status not in STATUSES:raise PackageError('Unknown candidate status')
        query=query.casefold()
        return [r for r in self.store.all() if (not query or query in ' '.join(str(r.get(k,'')) for k in ('name','description','content','source')).casefold()) and (not status or r['status']==status) and (not language or language.casefold() in r['language'].casefold())]
    def inspect(self,identifier):
        record=self.get(identifier);report=inspect_package(record['manifest'])
        if package_digest(record['manifest'])!=record['digest']:raise PackageError('Stored package digest mismatch')
        def change(r):
            r['validation_results']=report
            if r['status'] not in ('archived','installed','verified'):r['status']=status_for_report(report)
            r['history'].append({'event':'inspected','at':ingestion.timestamp()})
        self.store.mutate(identifier,change)
        return report
    def archive(self,identifier,restore=False):
        def change(r):
            if r['installed']:raise PackageError('Deactivate the candidate before archiving')
            r['status']=status_for_report(r['validation_results']) if restore else 'archived'
            if restore:
                receipt=self.store.latest_receipt(identifier)
                verified=(r['verification']=='verified' and package_digest(r['manifest'])==r['digest']
                          and receipt and receipt.get('passed') is True and receipt.get('executed') is True
                          and receipt.get('backend')=='docker' and receipt.get('cleanup_ok') is True
                          and receipt.get('digest')==r['digest'])
                r['verification']='verified' if verified else 'unverified'
                if verified:r['status']='verified'
            r['history'].append({'event':'restored' if restore else 'archived','at':ingestion.timestamp()})
        return self.store.mutate(identifier,change)
    def delete(self,identifier):self.store.delete(identifier)
    def export(self,*,ids=None):
        records=self.store.all() if ids is None else [self.get(i) for i in ids]
        result={'schema':'toad-library-v2','schema_version':2,'exported_at':ingestion.timestamp(),'abilities':records,'extensions':{'imports':self.store.import_metadata()}}
        if len(json_bytes(result))>MAX_BACKUP_BYTES:raise PackageError('Export exceeds 2 MB; select fewer candidate IDs')
        return result
    def queue_inspection(self,identifier):return self.store.enqueue(identifier)
    def run_queue(self,limit=10):
        if not 1<=limit<=100:raise PackageError('Queue limit must be 1–100')
        results=[]
        for _ in range(limit):
            job=self.store.claim_job()
            if job is None:break
            error=None
            try:
                if job['operation']!='inspect':raise PackageError('Unsupported queued operation')
                self.inspect(job['candidate_id'])
            except (ValueError,KeyError,OSError) as exc:error=str(exc)[:2000]
            results.append(self.store.finish_job(job['id'],job['token'],error))
        return results
    def status(self):
        records=self.store.all()
        return {'schema':'toad-status-v2','workspace':str(self.store.workspace),'candidates':len(records),
                'statuses':{s:sum(r['status']==s for r in records) for s in STATUSES},'execution_default':'disabled; explicit restricted Docker tests only',
                'queue':dict(self.store.connection.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state').fetchall())}
    def test(self,identifier,worker=None,*,cancel=None):
        from .lab import DockerWorker
        r=self.get(identifier)
        if r['status']=='archived':raise PackageError('Restore the archived candidate before testing')
        if r['installed']:raise PackageError('Test a new candidate version rather than an active installation')
        if package_digest(r['manifest'])!=r['digest']:raise PackageError('Stored package digest mismatch')
        self.store.mutate(identifier,lambda x:x.update(status='testing'))
        try:result=(worker or DockerWorker()).run(r['manifest'],cancel=cancel)
        except Exception:
            self.store.mutate(identifier,lambda x:x.update(status=status_for_report(x['validation_results'])))
            raise
        receipt=self.store.save_receipt(identifier,result)
        def done(x):
            x['test_results']=(x['test_results']+[receipt])[-20:]
            x['verification']='verified' if receipt['passed'] else 'unverified'
            x['status']='verified' if receipt['passed'] else ('failed' if receipt.get('executed') else status_for_report(x['validation_results']))
            x['history'].append({'event':'test_passed' if receipt['passed'] else ('test_failed' if receipt.get('executed') else 'test_blocked'),'at':ingestion.timestamp(),'receipt_id':receipt['id']})
        self.store.mutate(identifier,done)
        return receipt
