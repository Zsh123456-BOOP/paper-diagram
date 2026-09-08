"""Small behavioral checks for the optional structure experiments."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'experiments' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    import numpy as np
    tracer = load('trace_centerlines')
except ImportError:
    tracer = None


@unittest.skipIf(tracer is None, 'optional structure dependencies are not installed')
class GraphTests(unittest.TestCase):
    @staticmethod
    def edges(chains):
        return sorted(tuple(sorted((tuple(a), tuple(b)))) for c in chains for a, b in zip(c, c[1:]))

    def test_junction_join_preserves_edges_and_gap(self):
        skeleton = np.zeros((20, 25), dtype=bool)
        skeleton[10, 2:12] = True
        skeleton[5:16, 7] = True
        skeleton[10, 15:22] = True  # An observed gap, not a candidate to bridge.
        chains, report = tracer.graph_chains(skeleton)
        joined, joins = tracer.join_straight_chains(chains)
        self.assertGreater(joins, 0)
        self.assertEqual(self.edges(chains), self.edges(joined))
        self.assertEqual(len(self.edges(chains)), report['visited_edges'])
        self.assertEqual(len(set(self.edges(chains))), len(self.edges(chains)))

    def test_closed_loop_survives(self):
        skeleton = np.zeros((12, 12), dtype=bool)
        skeleton[2, 2:9] = skeleton[8, 2:9] = True
        skeleton[2:9, 2] = skeleton[2:9, 8] = True
        chains, _ = tracer.graph_chains(skeleton)
        self.assertEqual(len(chains), 1)
        self.assertTrue(np.array_equal(chains[0][0], chains[0][-1]))
        joined, _ = tracer.join_straight_chains(chains)
        self.assertEqual(self.edges(chains), self.edges(joined))


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.tool = load('replace_picture_with_curves')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d = Path(self.temp.name)
        self.svg = self.d / 'curve.svg'
        self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><g id="core"><path id="branch-1" d="M5,50 C25,10 75,90 95,50" fill="none" stroke="#55ff99" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/></g></svg>')

    def package(self, shared=False):
        A, P, R = self.tool.A, self.tool.P, self.tool.R
        root = ET.Element('{' + P + '}sld')
        tree = ET.SubElement(ET.SubElement(root, '{' + P + '}cSld'), '{' + P + '}spTree')
        for index in range(2):
            pic = ET.SubElement(tree, '{' + P + '}pic')
            nv = ET.SubElement(pic, '{' + P + '}nvPicPr')
            ET.SubElement(nv, '{' + P + '}cNvPr', id=str(index + 2), name=f'Picture {index}')
            ET.SubElement(ET.SubElement(pic, '{' + P + '}blipFill'), '{' + A + '}blip', {'{' + R + '}embed': 'r1' if index == 0 or shared else 'r2'})
            xf = ET.SubElement(ET.SubElement(pic, '{' + P + '}spPr'), '{' + A + '}xfrm')
            ET.SubElement(xf, '{' + A + '}off', x=str(index * 952500), y='0')
            ET.SubElement(xf, '{' + A + '}ext', cx='952500', cy='952500')
        sp = ET.SubElement(tree, '{' + P + '}sp')
        ET.SubElement(ET.SubElement(sp, '{' + P + '}nvSpPr'), '{' + P + '}cNvPr', id='8', name='Keep this label')
        ET.SubElement(sp, '{' + A + '}t').text = 'Keep the original text — αβ'
        self.other_picture = ET.tostring(tree.findall('{' + P + '}pic')[1])
        rels = ET.Element('{' + self.tool.PKG + '}Relationships')
        for i in (1, 2):
            ET.SubElement(rels, '{' + self.tool.PKG + '}Relationship', Id=f'r{i}', Target=f'/ppt/media/image{i}.png', Type=R + '/image')
        self.source = self.d / 'input.pptx'
        with zipfile.ZipFile(self.source, 'w') as z:
            z.writestr('ppt/slides/slide1.xml', ET.tostring(root))
            z.writestr('ppt/slides/_rels/slide1.xml.rels', ET.tostring(rels))
            z.writestr('ppt/media/image1.png', b'original image')
            z.writestr('ppt/media/image2.png', b'other image')
            z.writestr('ppt/notesSlides/notesSlide1.xml', b'unrelated notes')

    def test_replacement_keeps_text_other_picture_and_notes(self):
        self.package()
        output = self.d / 'output.pptx'
        self.tool.replace_picture(self.source, self.svg, output, 0, [0, 0, 100, 100])
        with zipfile.ZipFile(output) as z:
            self.assertNotIn('ppt/media/image1.png', z.namelist())
            self.assertEqual(z.read('ppt/media/image2.png'), b'other image')
            self.assertEqual(z.read('ppt/notesSlides/notesSlide1.xml'), b'unrelated notes')
            r = ET.fromstring(z.read('ppt/slides/slide1.xml'))
            self.assertEqual([t.text for t in r.iter('{' + self.tool.A + '}t')], ['Keep the original text — αβ'])
            self.assertEqual(ET.tostring(next(r.iter('{' + self.tool.P + '}pic'))), self.other_picture)
            self.assertTrue(list(r.iter('{' + self.tool.A + '}cubicBezTo')))
        with self.assertRaises(ValueError):
            self.tool.replace_picture(self.source, self.svg, output, 0, [0, 0, 100, 100])

    def test_shared_image_stays(self):
        self.package(shared=True)
        output = self.d / 'shared.pptx'
        self.tool.replace_picture(self.source, self.svg, output, 0, [0, 0, 100, 100])
        with zipfile.ZipFile(output) as z:
            self.assertEqual(z.read('ppt/media/image1.png'), b'original image')

    def test_wrong_picture_frame_leaves_no_output(self):
        self.package()
        output = self.d / 'refused.pptx'
        with self.assertRaises(ValueError):
            self.tool.replace_picture(self.source, self.svg, output, 0, [10, 0, 100, 100])
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
