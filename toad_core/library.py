"""Legacy v1 catalog compatibility. New applications should use Engine."""
import json
import re
from pathlib import Path


def add_record(catalog_path, package, status='unverified'):
    if status not in ('unverified','validated','rejected'):
        raise ValueError('Use Engine.test for evidence-backed testing; invalid legacy status')
    if not isinstance(package,dict) or not isinstance(package.get('name'),str) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,63}',package['name']):raise ValueError('invalid name')
    if not isinstance(package.get('version'),str) or not re.fullmatch(r'\d+\.\d+\.\d+',package['version']):raise ValueError('invalid version')
    catalog_path=Path(catalog_path)
    if catalog_path.exists() and catalog_path.stat().st_size>2_000_000:raise ValueError('catalog exceeds limit')
    data=json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.exists() else {'schema':'toad-library-v1','abilities':[]}
    if data.get('schema')!='toad-library-v1' or not isinstance(data.get('abilities'),list):raise ValueError('unsupported catalog')
    existing=next((x for x in data['abilities'] if (x.get('name'),x.get('version'))==(package['name'],package['version'])),{})
    item={**existing,**package,'status':status,'installed':False,'source':existing.get('source','manual_import')}
    data['abilities']=[x for x in data['abilities'] if (x.get('name'),x.get('version'))!=(item['name'],item['version'])]+[item]
    catalog_path.parent.mkdir(parents=True,exist_ok=True)
    import os,tempfile
    fd,temp=tempfile.mkstemp(prefix='.toad-catalog-',dir=catalog_path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,indent=2);f.write('\n')
        os.replace(temp,catalog_path)
    finally:
        if Path(temp).exists():Path(temp).unlink()
    return item
