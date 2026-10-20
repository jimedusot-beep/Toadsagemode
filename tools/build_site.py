"""Publish a static allowlist; never copy runtime catalogs or source archives."""
import argparse
from pathlib import Path
import shutil

ASSETS=('index.html','web/catalog.js','web/ability-library.js','web/styles.css')


def build(output):
    root=Path(__file__).resolve().parents[1];target=Path(output).absolute()
    if target.is_symlink() or root.is_relative_to(target.resolve()):raise ValueError('Site output cannot be the repository or its parent')
    if target.exists():
        for file in target.rglob('*'):
            if file.is_symlink() or (file.is_file() and file.relative_to(target).as_posix() not in ASSETS):raise ValueError('Output contains unexpected files; choose a new empty directory')
    target.mkdir(parents=True,exist_ok=True)
    for relative in ASSETS:
        source=root/relative;destination=target/relative
        if source.is_symlink():raise ValueError('Static source assets cannot be symlinks')
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='dist');args=parser.parse_args()
    print('Built static site:',build(args.output))
