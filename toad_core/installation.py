"""Receipt-bound, versioned sandbox-only activation. Never imports abilities."""
from __future__ import annotations
import json
import os
import shutil
import tempfile
from pathlib import Path
from .ingestion import timestamp, read_bounded
from .schema import PackageError, normalize_package, package_digest, MAX_PACKAGE_BYTES, json_bytes


class Registry:
    def __init__(self,engine):
        self.engine=engine;self.store=engine.store;self.root=self.store.workspace/'abilities'
        if self.root.is_symlink():raise PackageError('Ability storage cannot be a symlink')
        self.root.mkdir(mode=0o700,exist_ok=True)

    def _evidence(self,identifier):
        record=self.engine.get(identifier);p=normalize_package(record['manifest'])
        if p['permissions'] or p['dependencies']:raise PackageError('Only zero-grant, dependency-free sandbox abilities can activate')
        if package_digest(p)!=record['digest']:raise PackageError('Package changed since verification')
        receipt=self.store.latest_receipt(identifier)
        if (record['verification']!='verified' or record['status'] not in ('verified','installed') or not receipt
                or not receipt.get('passed') or not receipt.get('executed') or receipt.get('backend')!='docker'
                or receipt.get('digest')!=record['digest'] or not receipt.get('cleanup_ok')):
            raise PackageError('Activation requires a successful local Docker receipt for the current package')
        return record,p,receipt

    def _slot(self,p,digest):
        slot=self.root/p['name']/p['version']/digest
        for path in (self.root,self.root/p['name'],self.root/p['name']/p['version'],slot):
            if path.is_symlink():raise PackageError('Symlink in ability storage')
        if not slot.resolve().is_relative_to(self.root.resolve()):raise PackageError('Ability path escaped its registry')
        return slot

    def _verify_slot(self,slot,p,record,receipt):
        if slot.is_symlink():raise PackageError('Installed package is a symlink')
        expected={f['path']:f['content'] for f in p['files']}
        actual=set()
        for file in slot.rglob('*'):
            if file.is_symlink():raise PackageError('Installed package contains a symlink')
            if file.is_file():actual.add(file.relative_to(slot).as_posix())
        if actual!=set(expected)|{'.toad-install.json'}:raise PackageError('Installed package files differ from verified snapshot')
        for path,content in expected.items():
            try:body=read_bounded(slot/path,250000).decode('utf-8')
            except (UnicodeError,OSError) as exc:raise PackageError('Cannot read installed snapshot') from exc
            if body!=content:raise PackageError('Installed source was modified')
        try:meta=json.loads(read_bounded(slot/'.toad-install.json',MAX_PACKAGE_BYTES+4000))
        except (ValueError,OSError) as exc:raise PackageError('Invalid installation metadata') from exc
        original=self.store.connection.execute('SELECT document FROM receipts WHERE id=? AND candidate_id=? AND passed=1',(meta.get('receipt_id'),record['id'])).fetchone()
        original=json.loads(original[0]) if original else None
        if (meta.get('digest')!=record['digest'] or meta.get('candidate_id')!=record['id'] or meta.get('allowed_capabilities')!=[]
                or meta.get('activation_mode')!='sandbox_only' or not original or original.get('digest')!=record['digest']
                or not original.get('executed') or not original.get('cleanup_ok') or original.get('backend')!='docker'):
            raise PackageError('Installation evidence does not match a valid local receipt')

    def _stage(self,p,record,receipt):
        slot=self._slot(p,record['digest'])
        if slot.exists():self._verify_slot(slot,p,record,receipt);return slot
        slot.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temp=Path(tempfile.mkdtemp(prefix='.staged-',dir=self.root))
        try:
            for f in p['files']:
                target=temp/f['path'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(f['content'],encoding='utf-8');target.chmod(0o444)
            metadata={'candidate_id':record['id'],'digest':record['digest'],'receipt_id':receipt['id'],'manifest':p,
                      'allowed_capabilities':[],'activation_mode':'sandbox_only','staged_at':timestamp()}
            (temp/'.toad-install.json').write_bytes(json_bytes(metadata))
            os.rename(temp,slot)
        finally:
            if temp.exists():shutil.rmtree(temp)
        self._verify_slot(slot,p,record,receipt)
        return slot

    def get(self,name):
        row=self.store.connection.execute('SELECT document FROM activations WHERE name=?',(name,)).fetchone()
        if not row:raise KeyError('No activation for '+name)
        return json.loads(row[0])

    def activate(self,identifier,*,allowed_capabilities=None):
        if allowed_capabilities not in (None,[]):raise PackageError('Privilege expansion is unsupported; grants must be empty')
        record,p,receipt=self._evidence(identifier);slot=self._stage(p,record,receipt)
        with self.store.transaction() as conn:
            row=conn.execute('SELECT document FROM activations WHERE name=?',(p['name'],)).fetchone()
            previous=json.loads(row[0]) if row else None
            if previous and previous.get('candidate_id')==identifier:return previous
            history=list(previous.get('history',[])) if previous else []
            if previous and previous.get('candidate_id'):
                history.append({k:previous[k] for k in ('candidate_id','version','digest','path')})
                old=self.store.get(previous['candidate_id']);old.update(installed=False,status='verified')
                old['history'].append({'event':'deactivated','at':timestamp()})
                conn.execute('UPDATE candidates SET document=? WHERE id=?',(json.dumps(old),old['id']))
            activation={'name':p['name'],'candidate_id':identifier,'version':p['version'],'digest':record['digest'],'path':str(slot),
                        'activation_mode':'sandbox_only','allowed_capabilities':[],'activated_at':timestamp(),'history':history}
            conn.execute('INSERT OR REPLACE INTO activations VALUES(?,?)',(p['name'],json.dumps(activation)))
            record.update(installed=True,status='installed',previous_versions=history,rollback=history[-1] if history else None)
            record['history'].append({'event':'installed_sandbox_only','at':timestamp(),'receipt_id':receipt['id']})
            conn.execute('UPDATE candidates SET document=? WHERE id=?',(json.dumps(record),identifier))
            self.store._event(conn,'activated_sandbox_only',identifier,{'version':p['version']})
        return activation

    def deactivate(self,name):
        with self.store.transaction() as conn:
            active=self.get(name)
            if active.get('candidate_id'):
                old=self.store.get(active['candidate_id']);old.update(installed=False,status='verified')
                old['history'].append({'event':'deactivated','at':timestamp()})
                conn.execute('UPDATE candidates SET document=? WHERE id=?',(json.dumps(old),old['id']))
                active['history'].append({k:active[k] for k in ('candidate_id','version','digest','path')})
            active['candidate_id']=None
            conn.execute('UPDATE activations SET document=? WHERE name=?',(json.dumps(active),name));self.store._event(conn,'deactivated',name)
        return active

    def rollback(self,name):
        active=self.get(name)
        prior=next((h for h in reversed(active.get('history',[])) if h['candidate_id']!=active.get('candidate_id')),None)
        if prior is None:raise PackageError('No previous verified version is available')
        return self.activate(prior['candidate_id'])
