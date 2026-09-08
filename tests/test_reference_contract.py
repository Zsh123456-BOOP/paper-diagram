import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference_check',ROOT/'skills/paper-diagram/scripts/check_reference.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReferenceContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><rect id="a" x="10" y="20" width="50" height="40"/><rect id="b" x="100" y="20" width="80" height="40"/><text id="t1">Stride 2</text><path id="edge" d="M60,40 L100,40" marker-end="url(#arrow)"/></svg>'
        self.scene={'width':200,'height':100,'geometry':'scene.svg'}
        self.ref={'canvas':[200,100],'regions':[{'id':'main','status':'reviewed'}],
          'objects':[{'id':'a','svg_id':'a','bbox':[10,20,50,40]},{'id':'b','svg_id':'b','bbox':[100,20,80,40]}],
          'texts':[{'id':'label','svg_ids':['t1'],'content':'Stride 2'}],
          'edges':[{'id':'relation','svg_id':'edge','start':{'object':'a','side':'right'},'end':{'object':'b','side':'left'}}]}
    def run_check(self):
        (self.base/'scene.svg').write_text(self.svg)
        return m.check(self.ref,self.scene,self.base)
    def test_valid_connected_diagram(self):
        self.assertEqual(self.run_check()['contract_status'],'pass')
        self.assertEqual(self.run_check()['status'],'review')
    def test_visible_arrow_detached_from_target(self):
        self.svg=self.svg.replace('L100,40','L100,75')
        self.assertIn('end detached',str(self.run_check()['errors']))
    def test_scientific_label_mutation(self):
        self.svg=self.svg.replace('Stride 2','Stride?')
        self.assertIn('text mismatch',str(self.run_check()['errors']))
    def test_shifted_node_with_edge_following_still_fails_source_box(self):
        self.svg=self.svg.replace('x="100"','x="110"').replace('L100,40','L110,40')
        self.assertIn('source bbox mismatch',str(self.run_check()['errors']))
    def test_missing_edge(self):
        self.svg=self.svg.replace('id="edge"','id="wrong"')
        self.assertEqual(self.run_check()['status'],'fail')
    def test_incomplete_text_inventory(self):
        self.ref['texts']=[]
        self.assertIn('uncovered text',str(self.run_check()['errors']))
    def test_transformed_geometry_cannot_silently_pass(self):
        self.svg=self.svg.replace('<path id="edge"','<path transform="translate(0 20)" id="edge"')
        self.assertEqual(self.run_check()['status'],'fail')
    def test_unreviewed_regions_and_exceptions_do_not_pass(self):
        self.ref['regions'][0]['status']='pending'
        self.assertEqual(self.run_check()['status'],'review')
    def test_curved_edge_endpoints(self):
        self.svg=self.svg.replace('M60,40 L100,40','M60,40 C70,10 90,10 100,40')
        self.assertEqual(self.run_check()['contract_status'],'pass')
        self.assertEqual(self.run_check()['status'],'review')
    def test_self_authored_wrong_reference_cannot_certify_fidelity(self):
        self.svg=self.svg.replace('Stride 2','Stride?')
        self.ref['texts'][0]['content']='Stride?'
        self.ref['regions'][0]['status']='reviewed'
        result=self.run_check()
        self.assertEqual(result['contract_status'],'pass')
        self.assertEqual(result['status'],'review')
        self.assertEqual(result['visual_fidelity'],'not_evaluated')
    def test_observed_real_regression_endpoints(self):
        for tip,box in [((536,442),(536,341,81,62)),((674,550),(674,505,79,30)),((927,393),(928,336,62,37))]:
            with self.subTest(tip=tip):
                x,y,w,h=box
                # Same endpoint/node geometry as the rejected reconstruction.
                self.svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><rect id="b" x="{x}" y="{y}" width="{w}" height="{h}"/><path id="edge" d="M0,0 L{tip[0]},{tip[1]}" marker-end="url(#arrow)"/></svg>'
                self.ref['objects']=[{'id':'b','svg_id':'b'}];self.ref['texts']=[]
                self.ref['edges'][0]['start']={'point':[0,0]}
                self.assertIn('end detached',str(self.run_check()['errors']))

if __name__=='__main__':unittest.main()
