"""Fail-closed Docker laboratory. There is deliberately no host execution backend."""
from __future__ import annotations
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from .schema import PackageError, normalize_package, package_digest, json_bytes
from .inspection import inspect_package


from .processes import run_limited


@dataclass(frozen=True)
class LabPolicy:
    image: str='toad-sage-lab:1'
    timeout_seconds: float=10
    output_bytes: int=64000
    memory_mb: int=128
    cpus: float=0.5
    pids: int=32
    disk_mb: int=32

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:@-]{0,200}',self.image):raise PackageError('Invalid trusted lab image name')
        limits=((self.timeout_seconds,0.1,60),(self.output_bytes,1000,256000),(self.memory_mb,64,512),(self.cpus,0.1,2),(self.pids,8,64),(self.disk_mb,8,64))
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not low<=v<=high for v,low,high in limits):raise PackageError('Lab resource policy exceeds supported bounds')


class DockerWorker:
    def __init__(self,policy=None):
        self.policy=policy or LabPolicy()
        self.docker=shutil.which('docker')

    def _env(self):
        env={'PATH':os.environ.get('PATH','')}
        for key in ('SYSTEMROOT','WINDIR'):
            if key in os.environ:env[key]=os.environ[key]
        endpoint=os.environ.get('DOCKER_HOST')
        if endpoint:
            if not endpoint.startswith(('unix:///','npipe:////./pipe/')):raise PackageError('Only a local Docker socket is supported')
            env['DOCKER_HOST']=endpoint
        return env

    def _call(self,config,args,**kw):
        return run_limited([self.docker,'--config',config,*args],timeout=kw.pop('timeout',5),output_limit=kw.pop('output_limit',64000),env=self._env(),**kw)

    @staticmethod
    def _ok(result):return result.get('returncode')==0 and not any(result.get(k) for k in ('error','timed_out','output_limited','cancelled'))

    def _probe(self,config):
        if not self.docker:return {'available':False,'reason':'Docker executable is unavailable; host execution is disabled'}
        info=self._call(config,['info','--format','{{json .}}'])
        if not self._ok(info):return {'available':False,'reason':'Local Docker daemon is unavailable or its response exceeded limits'}
        try:data=json.loads(info['stdout'])
        except (ValueError,TypeError):return {'available':False,'reason':'Invalid Docker capability response'}
        if not isinstance(data,dict):return {'available':False,'reason':'Docker capability response must be an object'}
        required=('MemoryLimit','SwapLimit','PidsLimit','CPUCfsQuota','CPUCfsPeriod')
        if data.get('OSType')!='linux' or data.get('CgroupVersion')!='2' or any(data.get(k) is not True for k in required):
            return {'available':False,'reason':'Linux cgroup v2 and enforceable CPU/memory/swap/PID limits are required'}
        security=data.get('SecurityOptions')
        if not isinstance(security,list) or any(not isinstance(x,str) for x in security):
            return {'available':False,'reason':'Invalid Docker security capability response'}
        if not any('seccomp' in x and ('builtin' in x or 'default' in x) for x in security):
            return {'available':False,'reason':'Default Docker seccomp enforcement was not confirmed'}
        image=self._call(config,['image','inspect','--format','{{json .}}',self.policy.image])
        if not self._ok(image):return {'available':False,'reason':'Trusted local lab image is missing; no images are pulled automatically'}
        try:image_id=json.loads(image['stdout'])['Id']
        except (ValueError,KeyError,TypeError):image_id=''
        if not isinstance(image_id,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',image_id):return {'available':False,'reason':'Immutable lab image ID could not be established'}
        return {'available':True,'image_id':image_id,'isolation':'Linux containers with cgroup v2/default seccomp; not a perfect security boundary'}

    def availability(self):
        if not self.docker:return {'available':False,'reason':'Docker executable is unavailable; host execution is disabled'}
        try:
            with tempfile.TemporaryDirectory(prefix='toad-docker-client-') as config:return self._probe(config)
        except (OSError,ValueError) as exc:return {'available':False,'reason':str(exc)}

    def _create_args(self,name,image_id,index):
        p=self.policy
        return ['create','--name',name,'--label=org.toad-sage.lab=1','--interactive','--pull=never','--network=none',
                '--read-only','--user=65532:65532','--cap-drop=ALL','--security-opt=no-new-privileges=true',
                f'--pids-limit={p.pids}',f'--memory={p.memory_mb*1024*1024}',f'--memory-swap={p.memory_mb*1024*1024}',f'--cpus={p.cpus}',
                '--tmpfs',f'/work:rw,nosuid,nodev,noexec,size={p.disk_mb*1024*1024},mode=1777',
                '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=8388608,mode=1777','--ipc=none','--log-driver=none',
                '--ulimit','nofile=64:64','--ulimit',f'nproc={p.pids}:{p.pids}','--ulimit','fsize=8388608:8388608','--ulimit','core=0:0',
                '--hostname=toad-lab','--env=PYTHONHASHSEED=0','--workdir=/work','--entrypoint=/usr/local/bin/python',image_id,
                '-I','-B','/opt/toad_lab/runner.py',str(index)]

    def _inspect(self,config,name):
        response=self._call(config,['inspect',name])
        if not self._ok(response):raise PackageError('Could not inspect disposable container')
        try:return json.loads(response['stdout'])[0]
        except (ValueError,KeyError,IndexError,TypeError) as exc:raise PackageError('Invalid container inspection') from exc

    def _check_container(self,data,image_id):
        h=data.get('HostConfig',{});c=data.get('Config',{});p=self.policy
        required={'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'PidsLimit':p.pids,'Memory':p.memory_mb*1024*1024,
                  'MemorySwap':p.memory_mb*1024*1024,'NanoCpus':int(p.cpus*1e9),'IpcMode':'none'}
        if any(h.get(k)!=v for k,v in required.items()) or data.get('Image')!=image_id:raise PackageError('Container resource/isolation enforcement mismatch')
        if c.get('User')!='65532:65532' or c.get('WorkingDir')!='/work' or c.get('Entrypoint')!=['/usr/local/bin/python']:raise PackageError('Container identity/entrypoint mismatch')
        if h.get('Binds') or h.get('CapAdd') or h.get('Devices') or h.get('DeviceRequests') or set(h.get('CapDrop',[]))!={'ALL'}:raise PackageError('Unsupported container mounts, privileges or devices')
        if any(m.get('Type')!='tmpfs' for m in data.get('Mounts',[])):raise PackageError('Host mounts are forbidden')
        if not any(x in ('no-new-privileges=true','no-new-privileges') for x in h.get('SecurityOpt',[])) or any('unconfined' in x for x in h.get('SecurityOpt',[])):raise PackageError('Privilege/seccomp policy mismatch')
        if h.get('LogConfig',{}).get('Type')!='none':raise PackageError('Unbounded Docker logging is forbidden')
        tmpfs=h.get('Tmpfs',{})
        if set(tmpfs)!={'/work','/tmp'}:raise PackageError('Unexpected writable container directories')
        for path,expected_size in (('/work',p.disk_mb*1024*1024),('/tmp',8388608)):
            flags=set(tmpfs[path].split(','))
            if not {'rw','nosuid','nodev','noexec',f'size={expected_size}'}.issubset(flags):raise PackageError('Writable filesystem limits were not confirmed')

    def _cleanup(self,config,name):
        for _ in range(2):
            r=self._call(config,['rm','--force','--volumes',name],output_limit=4000)
            if self._ok(r) or 'no such container' in r.get('stderr','').lower():return True
        return False

    def run(self,package,*,cancel=None):
        p=normalize_package(package);report=inspect_package(p)
        result={'schema':'toad-test-run-v1','backend':'docker','digest':package_digest(p),'executed':False,'passed':False,'tests':[],
                'policy':self.policy.__dict__.copy(),'blocked_reason':None,'cleanup_ok':True}
        if report['errors'] or not p['tests'] or p['permissions'] or p['dependencies'] or report['dependencies']['third_party']:
            result['blocked_reason']='Tests require valid Python/JSON syntax, structured tests, no external dependencies and no permission grants';return result
        if not self.docker:result['blocked_reason']='Docker executable is unavailable; host execution is disabled';return result
        try:
            with tempfile.TemporaryDirectory(prefix='toad-docker-client-') as config:
                probe=self._probe(config)
                if not probe['available']:result['blocked_reason']=probe['reason'];return result
                result['image_id']=probe['image_id']
                for index,spec in enumerate(p['tests']):
                    if cancel and cancel():result['blocked_reason']='Cancelled before test';break
                    name='toad-lab-'+uuid.uuid4().hex
                    attempt={'index':index,'kind':spec['kind'],'path':spec['path'],'passed':False,'container':name,'executed':False}
                    try:
                        created=self._call(config,self._create_args(name,probe['image_id'],index))
                        if not self._ok(created):raise PackageError('Container creation failed')
                        self._check_container(self._inspect(config,name),probe['image_id'])
                        run=self._call(config,['start','--attach','--interactive',name],input_data=json_bytes(p),timeout=self.policy.timeout_seconds,output_limit=self.policy.output_bytes,cancel=cancel)
                        state=self._inspect(config,name).get('State',{})
                        executed=bool(state.get('StartedAt')) and not str(state.get('StartedAt','')).startswith('0001-')
                        attempt.update(run,executed=executed)
                        good=self._ok(run) and executed and state.get('Running') is False and state.get('ExitCode')==0 and not state.get('OOMKilled') and not state.get('Error')
                        if spec['kind']=='python':good=good and run['stdout']==spec['expected_stdout']
                        attempt['passed']=bool(good)
                        attempt['category']='passed' if good else ('timeout' if run['timed_out'] else 'output_limit' if run['output_limited'] else 'cancelled' if run['cancelled'] else 'resource_limit' if state.get('OOMKilled') else 'test_failure')
                        result['executed']=result['executed'] or executed
                    except (ValueError,OSError) as exc:
                        attempt.update(category='worker_error',error=str(exc));result['blocked_reason']=str(exc)
                    finally:
                        cleanup=self._cleanup(config,name);attempt['cleanup_ok']=cleanup
                        if not cleanup:attempt.update(passed=False,category='cleanup_failed');result['cleanup_ok']=False
                        result['tests'].append(attempt)
                    if not attempt['passed']:break
                result['passed']=len(result['tests'])==len(p['tests']) and all(t['passed'] for t in result['tests']) and result['cleanup_ok']
        except (OSError,ValueError) as exc:result['blocked_reason']=str(exc)
        return result
