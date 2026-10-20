"""Bounded I/O and wall time for trusted local helper processes only."""
import os
import subprocess
import threading
import time

def run_limited(command, *, input_data=b'', timeout=15, output_limit=64000, env=None, cancel=None):
    """Bound I/O and elapsed time for a trusted executable with an argument list."""
    start=time.monotonic();chunks={'stdout':bytearray(),'stderr':bytearray()};lock=threading.Lock();overflow=threading.Event()
    result={'returncode':None,'stdout':'','stderr':'','timed_out':False,'output_limited':False,'cancelled':False,'error':None,'elapsed':0.0}
    try:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,start_new_session=os.name!='nt')
    except OSError as exc:
        result.update(error=str(exc),elapsed=time.monotonic()-start);return result
    def read(stream,key):
        try:
            while True:
                block=stream.read1(4096)
                if not block:break
                with lock:
                    remaining=max(0,output_limit-sum(len(v) for v in chunks.values()))
                    chunks[key].extend(block[:remaining])
                    if len(block)>remaining:overflow.set()
        finally:stream.close()
    def write():
        try:process.stdin.write(input_data);process.stdin.flush()
        except (BrokenPipeError,OSError):pass
        finally:process.stdin.close()
    readers=[threading.Thread(target=read,args=(process.stdout,'stdout'),daemon=True),threading.Thread(target=read,args=(process.stderr,'stderr'),daemon=True)]
    writer=threading.Thread(target=write,daemon=True)
    for t in [*readers,writer]:t.start()
    try:
        while process.poll() is None:
            if overflow.is_set():break
            if cancel and cancel():result['cancelled']=True;break
            if time.monotonic()-start>=timeout:result['timed_out']=True;break
            try:process.wait(timeout=0.02)
            except subprocess.TimeoutExpired:pass
    finally:
        if process.poll() is None:
            process.kill()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:result['error']='Trusted process could not be reaped'
        for t in [*readers,writer]:t.join(timeout=1)
        result['returncode']=process.poll()
        result['output_limited']=overflow.is_set()
        # Invalid UTF-8 may expand on replacement; retain the original global byte bound.
        remaining=output_limit
        for key in ('stdout','stderr'):
            text=bytes(chunks[key]).decode('utf-8','replace').encode('utf-8')[:remaining].decode('utf-8','ignore')
            result[key]=text;remaining-=len(text.encode('utf-8'))
        result['elapsed']=time.monotonic()-start
    return result

