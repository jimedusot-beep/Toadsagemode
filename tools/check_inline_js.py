"""Syntax-check trusted page scripts, inline and external, without executing."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]

class Scripts(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.current={'src':dict(attrs).get('src'),'body':''}
    def handle_data(self,data):
        if self.current is not None:self.current['body']+=data
    def handle_endtag(self,tag):
        if tag=='script' and self.current is not None:self.scripts.append(self.current);self.current=None

page=Scripts();page.feed((root/'index.html').read_text(encoding='utf-8'))
if not page.scripts:raise SystemExit('No page scripts found')
with tempfile.TemporaryDirectory() as folder:
    for index,script in enumerate(page.scripts):
        if script['src']:
            url=urlsplit(script['src'])
            if url.scheme or url.netloc:raise SystemExit('Unexpected remote script')
            path=(root/url.path).resolve()
            if not path.is_relative_to(root):raise SystemExit('Unsafe page script path')
        else:
            path=Path(folder)/f'inline_{index}.js';path.write_text(script['body'],encoding='utf-8')
        subprocess.run(['node','--check',str(path)],check=True)
print(f'Checked {len(page.scripts)} page script(s) without execution')
