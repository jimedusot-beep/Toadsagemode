"""Local setup diagnostics. Metadata probes never run or generate candidate code."""
from __future__ import annotations
from dataclasses import replace
import os
import platform
import sqlite3
import sys
from .engine import Engine, default_workspace
from .ingestion import timestamp
from .lab import DockerWorker
from .models import ModelConfig, OllamaAdapter


def readiness(workspace=None, *, probe=False):
    """Check private catalog access; optionally probe bounded local dependencies.

    Opening the catalog creates it if absent and secures POSIX permissions.
    No candidate contents, names, or model prompts are included in this report.
    """
    runtime_ok=sys.version_info >= (3,11)
    checks={
        'runtime':{'status':'ready' if runtime_ok else 'blocked','python':platform.python_version(),
                   'platform':platform.system(),'required':'Python 3.11+'},
        'workspace':{'status':'not_checked'},
        'lab':{'status':'not_checked','reason':'Optional local metadata probe was not requested'},
        'model':{'status':'not_checked','reason':'Optional loopback metadata probe was not requested'},
    }
    steps=[]
    engine=None
    if runtime_ok:
        try:
            engine=Engine(workspace or default_workspace())
            count=engine.store.connection.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]
            checks['workspace']={'status':'ready','path':str(engine.store.workspace),'candidates':count,
                                 'privacy':'POSIX owner-only permissions enforced' if os.name=='posix' else 'Windows ACL privacy must be checked by the user'}
        except (OSError,ValueError,sqlite3.Error) as exc:
            checks['workspace']={'status':'blocked','reason':str(exc)}
        finally:
            if engine:engine.close()
    library_ok=runtime_ok and checks['workspace']['status']=='ready'
    if not runtime_ok:steps.append('Install Python 3.11 or newer, then rerun python -m toad_core doctor.')
    if checks['workspace']['status']=='blocked':
        steps.append('Fix the private workspace path, permissions or catalog error above; rerun with --workspace PATH before doctor. Do not delete an existing catalog to hide the error.')
    if not library_ok and probe:
        for name in ('lab','model'):checks[name]['reason']='Probe skipped because library readiness is blocked'
    if library_ok and probe:
        lab=DockerWorker().availability()
        checks['lab']={'status':'ready' if lab['available'] else 'blocked',**lab}
        try:
            # Read metadata only, with a shorter whole-operation HTTP deadline.
            model=OllamaAdapter(replace(ModelConfig.from_environment(),timeout_seconds=3)).availability()
        except (OSError,ValueError) as exc:model={'available':False,'reason':str(exc)}
        checks['model']={'status':'ready' if model['available'] else 'blocked',**model}
        if not lab['available']:
            steps.append('See SETUP-ACER.md and docs/LAB.md for a supported local Docker backend, trusted lab image and required restrictions; rerun python -m toad_core lab status.')
        if not model['available']:
            steps.append('See docs/MISSIONS.md to configure loopback Ollama and an already installed model; rerun python -m toad_core model status. Nothing is downloaded automatically.')
        if lab['available']:
            steps.append('Before relying on execution, follow docs/LAB.md and run python tools/lab_smoke.py --run on this local host; metadata availability does not verify containment.')
        if lab['available'] and model['available']:
            steps.append('After the containment smoke checks pass, create and run one harmless bounded mission using docs/MISSIONS.md; model quality and project correctness remain unverified.')
    elif library_ok:
        steps.append('For local Docker and Ollama metadata checks, run python -m toad_core doctor --probe. No candidate code will run.')
    if library_ok:
        steps.append('Offline feeds and backups are available now; transfer browser exports privately and ingest them using python -m toad_core ingest BACKUP.json.')
    capabilities={'library':'ready' if library_ok else 'blocked',
                  'testing':checks['lab']['status'] if library_ok else 'blocked',
                  'missions':'blocked' if not library_ok or 'blocked' in (checks['lab']['status'],checks['model']['status']) else
                             'ready' if all(checks[k]['status']=='ready' for k in ('lab','model')) else 'not_checked'}
    return {'schema':'toad-readiness-v1','checked_at':timestamp(),'probes_requested':probe,
            'checks':checks,'capabilities':capabilities,'execution_performed':False,'containment_verified':False,
            'next_steps':steps}
