"""Private transactional storage for trusted orchestration, never candidate code."""
from __future__ import annotations
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .ingestion import timestamp
from .schema import PackageError, MAX_ITEMS, MAX_BACKUP_BYTES, json_bytes


class Store:
    def __init__(self, workspace):
        self.workspace=Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True,exist_ok=True,mode=0o700)
        db=self.workspace/'catalog.sqlite3'
        # Secure existing directories before SQLite can create a WAL or write data.
        # On Windows the caller must provide a workspace protected by user ACLs.
        try:
            if os.name=='posix':self.workspace.chmod(0o700)
            for path in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm'),Path(str(db)+'-journal')):
                if path.is_symlink():raise PackageError('Refusing a symlinked catalog or sidecar')
                if path.exists() and os.name=='posix':path.chmod(0o600)
            descriptor=os.open(db,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
            try:
                if os.name=='posix':os.fchmod(descriptor,0o600)
            finally:os.close(descriptor)
        except OSError as exc:raise PackageError('Cannot secure the private catalog workspace') from exc
        self.connection=sqlite3.connect(db,timeout=10)
        self.connection.row_factory=sqlite3.Row
        self.connection.executescript('''
          PRAGMA foreign_keys=ON;
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE, document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE, digest TEXT NOT NULL, passed INTEGER NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, operation TEXT NOT NULL, candidate_id TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, token TEXT, error TEXT);
          CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY, document TEXT NOT NULL, lease_until REAL, token TEXT);
          CREATE TABLE IF NOT EXISTS activations(name TEXT PRIMARY KEY, document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, event TEXT NOT NULL, entity_id TEXT, detail TEXT NOT NULL);
        ''')
        version=self.connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if version and version[0]!='2':raise PackageError('Unsupported catalog schema; no migration is available')
        self.connection.execute("INSERT OR IGNORE INTO meta VALUES('schema_version','2')")
        self.connection.commit()

    def close(self):self.connection.close()

    @contextmanager
    def transaction(self):
        self.connection.execute('BEGIN IMMEDIATE')
        try:yield self.connection
        except BaseException:self.connection.rollback();raise
        else:self.connection.commit()

    def _event(self, conn, event, entity_id=None, detail=None):
        conn.execute('INSERT INTO events(at,event,entity_id,detail) VALUES(?,?,?,?)',(timestamp(),event,entity_id,json.dumps(detail or {})))
        conn.execute('DELETE FROM events WHERE seq <= (SELECT COALESCE(MAX(seq),0)-10000 FROM events)')

    def _insert(self,conn,record):
        row=conn.execute('SELECT document FROM candidates WHERE identity=?',(record['content_identity'],)).fetchone()
        if row:
            existing=json.loads(row[0]);extras=existing.setdefault('extensions',{})
            sources=extras.setdefault('duplicate_sources',[])
            if record['source'] not in sources:sources.append(record['source'])
            # Preserve differing imported metadata; refuse excess rather than silently dropping it.
            if record['extensions'] and record['extensions']!=existing.get('extensions'):
                imports=extras.setdefault('duplicate_imports',[])
                if record['extensions'] not in imports:imports.append(record['extensions'])
            if len(json_bytes(existing))>MAX_BACKUP_BYTES:raise PackageError('Duplicate metadata exceeds storage limit')
            conn.execute('UPDATE candidates SET document=? WHERE id=?',(json.dumps(existing),existing['id']))
            self._event(conn,'duplicate_received',existing['id'],{'source':record['source']})
            return {**existing,'duplicate':True}
        if conn.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]>=MAX_ITEMS:raise PackageError('Catalog item limit reached')
        if conn.execute('SELECT 1 FROM candidates WHERE id=?',(record['id'],)).fetchone():record={**record,'id':str(uuid.uuid4())}
        conn.execute('INSERT INTO candidates VALUES(?,?,?)',(record['id'],record['content_identity'],json.dumps(record)))
        self._event(conn,'candidate_received',record['id'])
        return {**record,'duplicate':False}

    def put(self,record):
        with self.transaction() as conn:return self._insert(conn,record)

    def put_many(self,records,metadata=None):
        with self.transaction() as conn:
            results=[self._insert(conn,r) for r in records]
            if metadata:
                row=conn.execute("SELECT value FROM meta WHERE key='import_metadata'").fetchone()
                imports=json.loads(row[0]) if row else []
                if metadata not in imports:imports.append(metadata)
                if len(json_bytes(imports))>MAX_BACKUP_BYTES:raise PackageError('Import metadata exceeds limit')
                conn.execute("INSERT OR REPLACE INTO meta VALUES('import_metadata',?)",(json.dumps(imports),))
            return results

    def get(self,identifier):
        row=self.connection.execute('SELECT document FROM candidates WHERE id=?',(identifier,)).fetchone()
        if row is None:raise KeyError('Unknown candidate: '+identifier)
        return json.loads(row[0])

    def all(self):return [json.loads(r[0]) for r in self.connection.execute('SELECT document FROM candidates ORDER BY rowid DESC')]

    def mutate(self,identifier,change):
        with self.transaction() as conn:
            row=conn.execute('SELECT document FROM candidates WHERE id=?',(identifier,)).fetchone()
            if row is None:raise KeyError('Unknown candidate: '+identifier)
            record=json.loads(row[0]);change(record);record['updated_at']=timestamp()
            record['history']=record.get('history',[])[-200:]
            conn.execute('UPDATE candidates SET document=? WHERE id=?',(json.dumps(record),identifier))
            return record

    def delete(self,identifier):
        with self.transaction() as conn:
            record=self.get(identifier)
            if record['installed']:raise PackageError('Deactivate the installed candidate before deleting it')
            for row in conn.execute('SELECT document FROM activations'):
                active=json.loads(row[0])
                if active.get('candidate_id')==identifier or any(h.get('candidate_id')==identifier for h in active.get('history',[])):
                    raise PackageError('Candidate is retained for version history and rollback')
            conn.execute('DELETE FROM candidates WHERE id=?',(identifier,));self._event(conn,'candidate_deleted',identifier)

    def import_metadata(self):
        row=self.connection.execute("SELECT value FROM meta WHERE key='import_metadata'").fetchone()
        return json.loads(row[0]) if row else []

    def save_receipt(self,identifier,result):
        record=self.get(identifier)
        if result.get('digest')!=record['digest']:raise PackageError('Test receipt digest does not match candidate')
        passed=result.get('passed') is True and result.get('executed') is True and result.get('backend')=='docker' and result.get('cleanup_ok') is True and len(result.get('tests',[]))==len(record['manifest']['tests']) and bool(result.get('tests')) and all(x.get('passed') is True and x.get('executed') is True and x.get('cleanup_ok') is True for x in result['tests'])
        receipt={**result,'id':str(uuid.uuid4()),'candidate_id':identifier,'passed':passed,'created_at':timestamp()}
        with self.transaction() as conn:
            conn.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?)',(receipt['id'],identifier,record['digest'],int(passed),json.dumps(receipt),receipt['created_at']))
            self._event(conn,'test_finished',identifier,{'passed':passed,'executed':receipt.get('executed',False),'receipt_id':receipt['id']})
        return receipt

    def latest_receipt(self,identifier,*,passed_only=False):
        query='SELECT document FROM receipts WHERE candidate_id=?'+(' AND passed=1' if passed_only else '')+' ORDER BY rowid DESC LIMIT 1'
        row=self.connection.execute(query,(identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def enqueue(self,identifier):
        with self.transaction() as conn:
            if conn.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]>=1000:raise PackageError('Operation queue is full')
            row=conn.execute("SELECT id FROM jobs WHERE candidate_id=? AND operation='inspect' AND state IN ('queued','running')",(identifier,)).fetchone()
            if row:return row[0]
            key=str(uuid.uuid4());conn.execute("INSERT INTO jobs(id,operation,candidate_id,state) VALUES(?,'inspect',?,'queued')",(key,identifier));return key

    def claim_job(self,*,now=None,lease_seconds=30):
        clock=time.time() if now is None else now
        with self.transaction() as conn:
            conn.execute("UPDATE jobs SET state='failed', error='Retry budget exhausted', token=NULL WHERE state='running' AND lease_until<=? AND attempts>=3",(clock,))
            conn.execute("UPDATE jobs SET state='queued', token=NULL WHERE state='running' AND lease_until<=? AND attempts<3",(clock,))
            row=conn.execute("SELECT * FROM jobs WHERE state='queued' AND attempts<3 ORDER BY rowid LIMIT 1").fetchone()
            if not row:return None
            token=str(uuid.uuid4());conn.execute("UPDATE jobs SET state='running', attempts=attempts+1, lease_until=?,token=? WHERE id=?",(clock+lease_seconds,token,row['id']))
            return dict(conn.execute('SELECT * FROM jobs WHERE id=?',(row['id'],)).fetchone())

    def finish_job(self,key,token,error=None):
        with self.transaction() as conn:
            changed=conn.execute("UPDATE jobs SET state=?,error=?,lease_until=NULL,token=NULL WHERE id=? AND token=? AND state='running'",('failed' if error else 'completed',error,key,token)).rowcount
            if not changed:raise PackageError('Operation lease expired')
        return self.job(key)

    def job(self,key):
        row=self.connection.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
        if not row:raise KeyError(key)
        return dict(row)

    def events(self,limit=100):
        return [dict(r) for r in self.connection.execute('SELECT * FROM events ORDER BY seq DESC LIMIT ?',(min(max(limit,1),1000),))]
