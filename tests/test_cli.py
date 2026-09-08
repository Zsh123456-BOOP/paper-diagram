"""The public command must finish offline and produce real editable objects."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image, ImageDraw
from pptx import Presentation
from cell_local.cli import main


class CliTests(unittest.TestCase):
    def test_local_end_to_end_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'reference.png'
            im = Image.new('RGB', (120, 60), 'white')
            draw = ImageDraw.Draw(im)
            draw.ellipse((8, 8, 40, 40), fill='#83b970')
            draw.line((42, 24, 102, 24), fill='black', width=2)
            draw.polygon([(101, 20), (110, 24), (101, 28)], fill='black')
            im.save(source)
            before = source.read_bytes()
            output = root / 'result'
            with patch('socket.create_connection', side_effect=AssertionError('Network forbidden in conversion')):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(['convert', str(source), '--output-dir', str(output)])
            self.assertEqual(code, 0)
            self.assertEqual(source.read_bytes(), before)
            report = json.loads((output / 'reference.conversion.json').read_text())
            self.assertEqual(report['svg']['embedded_images'], 0)
            self.assertGreater(report['svg']['path_count'], 0)
            pptx = output / 'reference.pptx'
            self.assertEqual(len(Presentation(pptx).slides), 1)
            with ZipFile(pptx) as z:
                self.assertFalse(any(p.startswith('ppt/media/') for p in z.namelist()))
            saved = pptx.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(['convert', str(source), '--output-dir', str(output)])
            self.assertEqual(code, 2)
            self.assertEqual(saved, pptx.read_bytes())


if __name__ == '__main__':
    unittest.main()
