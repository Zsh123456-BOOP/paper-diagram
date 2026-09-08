import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('evidence',ROOT/'skills/paper-diagram/scripts/reference_evidence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReferenceEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)
        self.im=Image.new('RGB',(256,128),'white');ImageDraw.Draw(self.im).rectangle((15,25,70,90),outline='black',width=3)
        self.im.save(self.d/'source.png');self.im.save(self.d/'render.png')
        self.ref={'canvas':[256,128],'regions':[{'id':'left','bbox':[0,0,128,128],'status':'pending'}]}
        (self.d/'reference.json').write_text(json.dumps(self.ref));(self.d/'artifact.pptx').write_bytes(b'test artifact placeholder')
        m.freeze(self.d/'source.png',self.d/'reference.json',self.d/'evidence')
        self.snapshot=self.d/'evidence/evidence.json'
    def compare(self,name='comparison'):
        return m.compare(self.snapshot,self.d/'render.png',self.d/'artifact.pptx',self.d/name,'synthetic fixture renderer')
    def test_identical_pixels_never_certify_scientific_fidelity(self):
        r=self.compare();self.assertFalse(r['flagged_regions']);self.assertEqual(r['flagged_tiles'],0)
        self.assertEqual(r['status'],'needs_visual_review')
    def test_displaced_shape_detected_even_if_scene_and_contract_agree(self):
        other=Image.new('RGB',self.im.size,'white');ImageDraw.Draw(other).rectangle((35,25,90,90),outline='black',width=3);other.save(self.d/'render.png')
        r=self.compare();self.assertIn('left',r['flagged_regions'])
    def test_added_content_outside_named_regions_still_detected(self):
        ImageDraw.Draw(self.im).rectangle((180,30,225,100),fill='black');self.im.save(self.d/'render.png')
        r=self.compare();self.assertFalse(r['flagged_regions']);self.assertGreater(r['flagged_tiles'],0)
    def test_missing_small_arrow_detected(self):
        source=Image.open(self.d/'source.png');draw=ImageDraw.Draw(source);draw.line((90,40,120,40),fill='black',width=3);draw.polygon([(120,40),(113,34),(113,46)],fill='black');source.save(self.d/'source2.png')
        m.freeze(self.d/'source2.png',self.d/'reference.json',self.d/'evidence2');self.snapshot=self.d/'evidence2/evidence.json'
        r=self.compare();self.assertGreater(r['regions'][0]['source_edges_without_match_fraction'],0)
    def test_frozen_reference_mutation_rejected(self):
        (self.d/'evidence/reference.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'frozen reference changed'):self.compare()
    def test_source_mutation_rejected(self):
        (self.d/'evidence/source.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'frozen source changed'):self.compare()
    def test_snapshot_overwrite_rejected(self):
        with self.assertRaisesRegex(ValueError,'overwrite'):m.freeze(self.d/'source.png',self.d/'reference.json',self.d/'evidence')
    def test_reviewed_at_build_time_rejected(self):
        self.ref['regions'][0]['status']='reviewed';(self.d/'reference.json').write_text(json.dumps(self.ref))
        with self.assertRaisesRegex(ValueError,'freeze before review'):m.freeze(self.d/'source.png',self.d/'reference.json',self.d/'evidence2')
    def test_aspect_ratio_distortion_rejected(self):
        self.im.resize((256,200)).save(self.d/'render.png')
        with self.assertRaisesRegex(ValueError,'aspect ratio'):self.compare()
    def test_stale_final_artifact_rejected(self):
        self.compare();m.verify_report(self.d/'comparison/pixel-evidence.json')
        (self.d/'artifact.pptx').write_bytes(b'new artifact')
        with self.assertRaisesRegex(ValueError,'stale evidence: artifact'):m.verify_report(self.d/'comparison/pixel-evidence.json')
    def test_stale_preview_rejected(self):
        self.compare();self.im.resize((512,256)).save(self.d/'render.png')
        with self.assertRaisesRegex(ValueError,'stale evidence: render'):m.verify_report(self.d/'comparison/pixel-evidence.json')

if __name__=='__main__':unittest.main()
