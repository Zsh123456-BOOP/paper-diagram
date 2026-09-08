import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cell_local.scene_qa import *
class SceneQATests(unittest.TestCase):
 def runs(self):
  return [dict(id='f',x=20,baseline=30,advance=12,anchor='start',ink_bbox=[-1,-16,12,3]),dict(id='sub',x=32,baseline=35,advance=7,ink_bbox=[0,-8,7,0])]
 def test_compound_center_preserves_subscript_position(self):
  ts=self.runs();relative=[ts[1]['x']-ts[0]['x'],ts[1]['baseline']-ts[0]['baseline']]
  center_block(ts,[50,50],target_id='box')
  self.assertEqual(center_error(block_box(ts),[50,50]),[0,0])
  self.assertEqual([ts[1]['x']-ts[0]['x'],ts[1]['baseline']-ts[0]['baseline']],relative)
 def test_renderer_calibration_does_not_shift_svg_coordinates(self):
  ts=self.runs();before=block_box(ts);observed=[before[0]+1,before[1]+2,before[2]+1,before[3]+2]
  calibrate_block(ts,observed,renderer='fixture')
  self.assertEqual(block_box(ts),before);self.assertEqual(ts[0]['pptx_offset'],[-1,-2])
 def test_pixel_roi_detects_one_pixel_shift_despite_white_background(self):
  from PIL import Image,ImageDraw
  im=Image.new('RGB',(1000,1000),'white');ImageDraw.Draw(im).rectangle((101,103,120,112),fill='#205080')
  box=color_ink_box(im,'205080',[95,95,130,125]);self.assertEqual(box,[101,103,121,113])
  self.assertEqual(center_error(box,[110,108]),[1,0])
 def test_wrong_arrow_id_does_not_pass_equal_counts(self):
  report=arrow_contract(['input','output'],['input','input'])
  self.assertFalse(report['passed']);self.assertEqual(report['missing'],['output'])
 def test_hidden_tip_is_not_confused_with_absent_probe(self):
  self.assertEqual(visibility_ratio([[1,1]],[[0,0]])['ratio'],0)
  self.assertIsNone(visibility_ratio([[0,0]],[[0,0]])['ratio'])
if __name__=='__main__':unittest.main()
