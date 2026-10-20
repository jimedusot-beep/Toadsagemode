#!/usr/bin/env python3
"""Bounded static validation only. NEVER executes imported content."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toad_core.schema import PackageError, MAX_PACKAGE_BYTES, normalize_package, strict_json
from toad_core.inspection import inspect_package

MAX_BYTES=MAX_PACKAGE_BYTES


def validate(data):
    try:
        report=inspect_package(normalize_package(data))
        return report['errors'],report['warnings']
    except (ValueError,TypeError,RecursionError) as exc:
        message=str(exc)
        if 'path' in message.lower():message='unsafe path: '+message
        return [message],[]


def main():
    if len(sys.argv)!=2:
        print('Usage: python tools/validate_feed.py package.json');return 2
    try:
        with open(sys.argv[1],'rb') as f:raw=f.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise PackageError('Package exceeds 512 KB limit')
        data=strict_json(raw);errors,warnings=validate(data)
        print(json.dumps({'valid_structure':not errors,'errors':errors,'warnings':warnings,'executed':False,'safe_to_run':'not_assessed'},indent=2))
        return 1 if errors else 0
    except (OSError,ValueError,UnicodeError) as exc:
        print(json.dumps({'valid_structure':False,'errors':[str(exc)],'executed':False}));return 1


if __name__=='__main__':sys.exit(main())
