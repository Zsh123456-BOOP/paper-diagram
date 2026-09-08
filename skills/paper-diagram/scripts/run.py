#!/usr/bin/env python3
"""Resolve the local project environment without downloading or updating anything."""
import os
from pathlib import Path
import subprocess
import sys

skill = Path(__file__).resolve().parents[1]
root = Path(os.environ['CELL_LOCAL_ROOT']).expanduser() if 'CELL_LOCAL_ROOT' in os.environ else skill / 'runtime' if (skill / 'runtime' / 'src' / 'cell_local').is_dir() else skill.parents[1]
if not (root / 'src' / 'cell_local').is_dir():
    raise SystemExit('Set CELL_LOCAL_ROOT to the Paper Diagram source checkout, or install the complete portable Skill with its runtime.')
python = os.environ.get('CELL_LOCAL_PYTHON')
if not python:
    candidates = [root / '.venv' / 'bin' / 'python', root / '.venv' / 'Scripts' / 'python.exe']
    python = next((str(p) for p in candidates if p.is_file()), sys.executable)
env = dict(os.environ)
env['PYTHONPATH'] = str(root / 'src') + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
if len(sys.argv)>1 and sys.argv[1]=='scene':
    command=[python,str(root/'experiments'/'export_reviewed_scene.py'),*sys.argv[2:]]
else:
    command=[python, '-m', 'cell_local', *sys.argv[1:]]
raise SystemExit(subprocess.call(command, env=env))
