"""Trusted isolated-mode HTTP transport; stdin is JSON data, never executed."""
import json
import sys
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def main():
    raw=sys.stdin.buffer.read(600001)
    if len(raw)>600000:raise ValueError('Transport request too large')
    data=json.loads(raw)
    body=json.dumps(data['payload'],ensure_ascii=False).encode('utf-8') if data['payload'] is not None else None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    request=urllib.request.Request(data['url'],data=body,headers={'Content-Type':'application/json','Accept':'application/json'})
    with opener.open(request,timeout=data['timeout']) as response:result=response.read(data['max_bytes']+1)
    if len(result)>data['max_bytes']:raise ValueError('Model response exceeded byte limit')
    sys.stdout.buffer.write(result)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,urllib.error.URLError) as exc:
        print(str(exc)[:500],file=sys.stderr);raise SystemExit(1)
