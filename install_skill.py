#!/usr/bin/env python3
"""Install this Skill as a source symlink or a self-contained portable copy."""
import argparse
import os
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--destination', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills')
parser.add_argument('--copy', action='store_true')
args = parser.parse_args()
source = Path(__file__).resolve().parent / 'skills' / 'paper-diagram'
destination = args.destination.expanduser().resolve() / 'paper-diagram'
if destination.exists() or destination.is_symlink():
    raise SystemExit(f'Refusing to replace existing Skill: {destination}')
destination.parent.mkdir(parents=True, exist_ok=True)
if args.copy:
    shutil.copytree(source, destination)
    project = source.parents[1]
    runtime = destination / 'runtime'
    runtime.mkdir()
    ignored = shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info', '.venv', 'build', 'dist')
    shutil.copytree(project / 'src', runtime / 'src', ignore=ignored)
    shutil.copytree(project / 'experiments', runtime / 'experiments', ignore=ignored)
    for name in ['pyproject.toml', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md']:
        shutil.copy2(project / name, runtime / name)
    print(f'Copied portable Skill to {destination}. Install dependencies from {runtime}; no CELL_LOCAL_ROOT setting is needed.')
else:
    destination.symlink_to(source, target_is_directory=True)
    print(f'Installed {destination} -> {source}')
