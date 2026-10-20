"""Opt-in LOCAL live containment checks. Never call from GitHub Actions."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toad_core.lab import DockerWorker,LabPolicy


def sample(code,expected):
    return {'schema':'toad-ability-v2','name':'lab-probe','version':'0.1.0','files':[{'path':'main.py','content':code}],
            'entrypoint':'main.py','tests':[{'kind':'python','path':'main.py','expected_stdout':expected}], 'permissions':[],'dependencies':[]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true',help='Run known harmless containment probes on a provisioned local Docker host')
    args=parser.parse_args()
    if not args.run:parser.error('Pass --run to execute the local Docker probes')
    worker=DockerWorker(LabPolicy(timeout_seconds=2))
    available=worker.availability()
    if not available['available']:print(json.dumps({'live_verified':False,'blocked':available['reason']},indent=2));return 2
    results=[]
    with tempfile.TemporaryDirectory(prefix='toad-host-canary-') as tmp:
        canary=Path(tmp)/'private.txt';canary.write_text('must not reach candidate')
        probes=[
          ('hello','print("hello")','hello\n',True,None),
          ('host_files',f'from pathlib import Path\ntry:\n Path({str(canary)!r}).read_text()\n print("bad")\nexcept OSError:\n print("blocked")','blocked\n',True,None),
          ('root_write','try:\n open("/outside-toad-test", "w").write("bad")\n print("bad")\nexcept OSError:\n print("blocked")','blocked\n',True,None),
          ('network','import socket\ns=socket.socket();s.settimeout(0.5)\ntry:\n s.connect(("198.51.100.1",80));print("bad")\nexcept OSError:\n print("blocked")','blocked\n',True,None),
          ('timeout','while True: pass','',False,'timeout'),
          ('output','print("x"*200000)','',False,'output_limit'),
          ('memory','x=bytearray(1024*1024*1024)','',False,'resource_limit'),
          ('disk','try:\n with open("fill", "wb") as f:\n  for _ in range(80): f.write(b"x"*1024*1024)\n print("bad")\nexcept OSError:\n print("bounded")','bounded\n',True,None),
          ('processes','import os,time\ntry:\n for _ in range(100):\n  if os.fork()==0: time.sleep(10);os._exit(0)\n print("bad")\nexcept OSError:\n print("bounded")','bounded\n',True,None),
        ]
        for name,code,expected,passed,category in probes:
            run=worker.run(sample(code,expected))
            ok=run['passed']==passed and run['executed'] and run['cleanup_ok']
            if category:ok=ok and any(t.get('category')==category for t in run['tests'])
            results.append({'probe':name,'restriction_observed':ok,'run':run})
    good=all(r['restriction_observed'] for r in results)
    print(json.dumps({'live_verified':good,'results':results},indent=2));return 0 if good else 1


if __name__=='__main__':raise SystemExit(main())
