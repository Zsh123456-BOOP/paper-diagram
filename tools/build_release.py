#!/usr/bin/env python3
"""Build a portable skill archive, without dependencies or local runtime data."""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    output = ROOT / 'dist' / 'paper-diagram-skill.zip'
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='paper-diagram-release-') as tmp:
        destination = Path(tmp)
        subprocess.run([sys.executable, str(ROOT / 'install_skill.py'), '--copy',
                        '--destination', str(destination)], check=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((destination / 'paper-diagram').rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                    archive.write(path, path.relative_to(destination))
    print(output)

if __name__ == '__main__':
    main()
