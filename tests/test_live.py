import json
from pathlib import Path
import tempfile
import unittest

from cell_local.live import compile_scene, export_live, path_segments, vb_string


class LiveCompilerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scene = self.root/'scene.json'
        self.data = dict(width=200, height=100, geometry='scene.svg', texts=[])

    def make(self, body):
        self.scene.write_text(json.dumps(self.data))
        (self.root/'scene.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'+body+'</svg>')
        return compile_scene(self.scene)

    def test_grouping_is_postorder_and_neighbor_cells_stay_independent(self):
        plan=self.make('<g id="matrix"><g id="cell1"><rect id="face1" width="20" height="20"/></g><g id="cell2"><rect id="face2" x="20" width="20" height="20"/></g></g>')
        self.assertEqual([e['id'] for e in plan['events']],['face1','cell1','face2','cell2','matrix'])
        self.assertEqual(plan['events'][-1]['members'],['cell1','cell2'])
        self.assertEqual(plan['events'][2]['bounds'],[20,0,20,20])

    def test_cubic_control_points_and_open_arrow_survive(self):
        e=self.make('<path id="residual" d="M10,20 C30,0 90,0 110,20" fill="none" stroke="#123456" data-line-end="triangle"/>')['events'][0]
        self.assertEqual(e['segments'],[['cubic',30,0,90,0,110,20]])
        self.assertTrue(e['arrow']);self.assertFalse(e['closed'])

    def test_quadratic_converts_to_equivalent_cubic(self):
        start,segments,closed=path_segments('M0,0 Q3,6 6,0')
        self.assertEqual(segments,[['cubic',2,4,4,4,6,0]])

    def test_perspective_face_is_closed(self):
        e=self.make('<polygon id="face" points="10,20 40,0 40,50 10,70"/>')['events'][0]
        self.assertTrue(e['closed']);self.assertEqual(e['segments'][-1],['line',10,20])

    def test_source_text_must_match_and_metrics_are_retained(self):
        self.data['texts']=[dict(id='value',content='2.3',x=50,baseline=40,size=20,advance=28,ascent=19,descent=5,font='Arial',fill='#000000',anchor='middle')]
        e=self.make('<text id="value">2.3</text>')['events'][0]
        self.assertEqual(e['bounds'],[36,21,31,26]);self.assertEqual(e['size'],20)
        with self.assertRaisesRegex(ValueError,'differs'):self.make('<text id="value">2.4</text>')

    def test_unsupported_effects_stop_before_creating_output(self):
        for attrs in ['fill="url(#gradient)"','transform="translate(2,3)"','filter="url(#blur)"','stroke-dasharray="6 3"','fill-rule="evenodd"']:
            with self.subTest(attrs=attrs):
                with self.assertRaises(ValueError):self.make(f'<rect id="r" width="20" height="20" {attrs}/>')
                with self.assertRaises(ValueError):export_live(self.scene,self.root/'out')
                self.assertFalse((self.root/'out').exists())

    def test_compound_holes_are_not_silently_connected(self):
        with self.assertRaisesRegex(ValueError,'one contour'):
            self.make('<path id="hole" d="M0,0 H30 V30 H0 Z M10,10 V20 H20 V10 Z"/>')

    def test_degenerate_arrow_is_refused(self):
        with self.assertRaisesRegex(ValueError,'no drawable'):
            self.make('<path id="bad" d="M20,20 L20,20" fill="none" stroke="#000" data-line-end="triangle"/>')

    def test_invalid_canvas_and_duplicate_ids_are_rejected(self):
        self.data['width']=-200
        with self.assertRaises(ValueError):self.make('')
        self.data['width']=200
        with self.assertRaisesRegex(ValueError,'unique ID'):
            self.make('<rect id="r" width="20" height="20"/><rect id="r" width="20" height="20"/>')

    def test_rounded_corners_have_four_curves(self):
        e=self.make('<rect id="r" x="10" y="20" width="80" height="30" rx="8"/>')['events'][0]
        self.assertEqual(sum(s[0]=='cubic' for s in e['segments']),4)
        self.assertTrue(e['closed'])

    def test_vba_strings_keep_unicode_and_escape_code_quotes(self):
        self.assertEqual(vb_string('A"B'),'"A""B"')
        self.assertEqual(vb_string('中'),'ChrW(20013)')
        self.assertEqual(vb_string('\n'),'ChrW(10)')
        self.assertEqual(vb_string('😀'),'ChrW(-10179) & ChrW(-8704)')

    def test_export_does_not_replace_existing_output(self):
        self.make('<rect id="r" width="20" height="20"/>')
        output=self.root/'out';report=export_live(self.scene,output)
        before=(output/'PaperDiagramLive.bas').read_bytes()
        self.assertEqual(report['shapes'],1)
        with self.assertRaises(FileExistsError):export_live(self.scene,output)
        self.assertEqual((output/'PaperDiagramLive.bas').read_bytes(),before)


if __name__=='__main__':unittest.main()
