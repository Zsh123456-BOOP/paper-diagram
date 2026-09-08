from pathlib import Path
import importlib.util,json,tempfile,unittest,zipfile
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scene_export',ROOT/'experiments/svg_scene_to_pptx.py');tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
A,P=tool.A,tool.P
class SceneExportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.d=Path(self.temp.name)
  self.svg=self.d/'scene.svg';self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#0000ff"/></linearGradient></defs><g id="editable block"><path id="face" d="M10,10 H90 V90 H10 Z M30,30 V70 H70 V30 Z" fill="url(#fade)"/><path id="empty" d="M20,20 l0,0 Z"/></g><text id="label" x="10" y="20">ABC</text></svg>')
  self.manifest=self.d/'scene.json';self.job={'width':100,'height':100,'geometry':str(self.svg),'texts':[{'id':'label','content':'ABC','wordart':True}]};self.manifest.write_text(json.dumps(self.job))
  self.base=self.d/'base.pptx';self.output=self.d/'result.pptx';self.write_base('ABC')
 def write_base(self,text):
  slide=E.Element('{'+P+'}sld');tree=E.SubElement(E.SubElement(slide,'{'+P+'}cSld'),'{'+P+'}spTree');E.SubElement(tree,'{'+P+'}nvGrpSpPr');E.SubElement(tree,'{'+P+'}grpSpPr')
  sp=E.SubElement(tree,'{'+P+'}sp');E.SubElement(E.SubElement(sp,'{'+P+'}nvSpPr'),'{'+P+'}cNvPr',id='2',name='label');E.SubElement(E.SubElement(sp,'{'+P+'}spPr'),'{'+A+'}xfrm')
  body=E.SubElement(sp,'{'+P+'}txBody');E.SubElement(body,'{'+A+'}bodyPr');E.SubElement(E.SubElement(E.SubElement(body,'{'+A+'}p'),'{'+A+'}r'),'{'+A+'}t').text=text
  presentation=E.Element('{'+P+'}presentation');E.SubElement(presentation,'{'+P+'}sldSz',cx='952500',cy='952500');E.SubElement(E.SubElement(presentation,'{'+P+'}sldIdLst'),'{'+P+'}sldId',id='256')
  with zipfile.ZipFile(self.base,'w') as z:z.writestr('ppt/slides/slide1.xml',E.tostring(slide));z.writestr('ppt/presentation.xml',E.tostring(presentation))
 def test_groups_holes_gradient_and_live_text_survive(self):
  report=tool.make_candidate(self.manifest,self.base,self.output)
  self.assertEqual(report['discarded_degenerate_paths'],1)
  with zipfile.ZipFile(self.output) as z:
   r=E.fromstring(z.read('ppt/slides/slide1.xml'))
   self.assertEqual([x.text for x in r.iter('{'+A+'}t')],['ABC'])
   self.assertEqual(len(list(r.iter('{'+A+'}close'))),2)
   self.assertEqual(len(list(r.iter('{'+A+'}gradFill'))),1)
   self.assertEqual(next(r.iter('{'+A+'}prstTxWarp')).get('prst'),'textPlain')
   self.assertEqual(next(r.iter('{'+P+'}grpSp')).find('.//{'+P+'}cNvPr').get('name'),'editable block')
   self.assertFalse(any(n.startswith('ppt/media/') for n in z.namelist()))
 def test_text_mismatch_is_refused(self):
  self.write_base('Different text')
  with self.assertRaisesRegex(ValueError,'text differs'):tool.make_candidate(self.manifest,self.base,self.output)
  self.assertFalse(self.output.exists())
 def test_native_gradient_stroke_retains_alpha_stops(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#eb901a" stop-opacity="0.02"/><stop offset="0.4" stop-color="#eb901a" stop-opacity="0.35"/><stop offset="1" stop-color="#eb901a"/></linearGradient></defs><path id="strand" d="M10 20 C30 80 70 80 90 20" fill="none" stroke="url(#fade)" stroke-width="2" opacity="0.5"/><text id="label">ABC</text></svg>')
  report=tool.make_candidate(self.manifest,self.base,self.output)
  self.assertEqual(report['native_gradient_strokes'],1)
  with zipfile.ZipFile(self.output) as z:r=E.fromstring(z.read('ppt/slides/slide1.xml'))
  grad=r.find('.//{'+A+'}ln/{'+A+'}gradFill')
  self.assertEqual([e.get('pos') for e in grad.iter('{'+A+'}gs')],['0','40000','100000'])
  self.assertEqual([e.get('val') for e in grad.iter('{'+A+'}alpha')],['1000','17500','50000'])
  self.assertEqual(grad.find('{'+A+'}lin').get('ang'),'0')
 def test_degenerate_arrow_is_reported_instead_of_disappearing(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path id="broken-arrow" d="M10 20 L10 20" stroke="#000000" data-line-end="triangle"/><text id="label">ABC</text></svg>')
  with self.assertRaisesRegex(ValueError,'no drawable shaft'):tool.make_candidate(self.manifest,self.base,self.output)
 def test_canvas_mismatch_is_refused(self):
  self.job['width']=101;self.manifest.write_text(json.dumps(self.job))
  with self.assertRaisesRegex(ValueError,'canvas differs'):tool.make_candidate(self.manifest,self.base,self.output)
 def test_geometry_can_travel_with_manifest(self):
  self.job['geometry']='scene.svg';self.manifest.write_text(json.dumps(self.job))
  tool.make_candidate(self.manifest,self.base,self.output)
  self.assertTrue(self.output.exists())
 def test_existing_report_is_preserved(self):
  self.output.with_suffix('.json').write_text('Keep me')
  with self.assertRaises(FileExistsError):tool.make_candidate(self.manifest,self.base,self.output)
  self.assertEqual(self.output.with_suffix('.json').read_text(),'Keep me')
 def test_native_dashes_arrow_and_standard_shapes(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g id="plane" data-name="Editable plane"><rect id="cell" x="10" y="10" width="15" height="20" fill="#ff0000"/><ellipse id="node" cx="70" cy="30" rx="8" ry="10" fill="#00ff00"/><line id="relation" x1="10" y1="60" x2="85" y2="60" fill="none" stroke="#000000" stroke-width="2" stroke-dasharray="6 4" data-line-end="triangle"/></g><text id="label">ABC</text></svg>')
  report=tool.make_candidate(self.manifest,self.base,self.output)
  self.assertEqual(report['native_presets'],2)
  self.assertEqual(report['native_dashed_lines'],1)
  with zipfile.ZipFile(self.output) as z:r=E.fromstring(z.read('ppt/slides/slide1.xml'))
  self.assertEqual([e.get('prst') for e in r.iter('{'+A+'}prstGeom')],['rect','ellipse'])
  self.assertEqual(len(list(r.iter('{'+A+'}custGeom'))),1)
  self.assertEqual(next(r.iter('{'+A+'}ds')).attrib,{'d':'300000','sp':'200000'})
  self.assertEqual(next(r.iter('{'+A+'}tailEnd')).get('type'),'triangle')
  self.assertEqual(next(r.iter('{'+P+'}grpSp')).find('.//{'+P+'}cNvPr').get('name'),'Editable plane')
 def test_decorated_transform_is_not_silently_misrendered(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g transform="scale(2)"><path id="d" d="M1 1 L30 30" stroke="black" stroke-dasharray="4 2"/></g></svg>')
  with self.assertRaisesRegex(ValueError,'untransformed'):tool.make_candidate(self.manifest,self.base,self.output)
 def test_same_color_cells_remain_individually_editable(self):
  spec=importlib.util.spec_from_file_location('semantic_grid',ROOT/'experiments/semantic_grid.py');grid=importlib.util.module_from_spec(spec);spec.loader.exec_module(grid)
  svg=E.Element('{'+tool.S+'}svg',viewBox='0 0 100 100')
  grid.matrix_plane(svg,name='matrix',origin=[10,25],u=[60,-15],v=[0,60],values=[[0,0,0],[0,0,0]],palette=['#bb88cc'])
  E.SubElement(svg,'{'+tool.S+'}text',id='label').text='ABC'
  E.ElementTree(svg).write(self.svg)
  tool.make_candidate(self.manifest,self.base,self.output)
  with zipfile.ZipFile(self.output) as z:r=E.fromstring(z.read('ppt/slides/slide1.xml'))
  cells=[s for s in r.iter('{'+P+'}sp') if '-r' in s.find('.//{'+P+'}cNvPr').get('name','')]
  self.assertEqual(len(cells),6)
  self.assertEqual(len(list(r.iter('{'+P+'}grpSp'))),2)
  for s in cells:
   self.assertEqual(len(list(s.iter('{'+A+'}moveTo'))),1)
   self.assertEqual(len(list(s.iter('{'+A+'}close'))),1)
  cells[0].find('.//{'+A+'}srgbClr').set('val','FF0000')
  self.assertEqual(sum(s.find('.//{'+A+'}srgbClr').get('val')=='FF0000' for s in cells),1)
 def test_cell_number_moves_with_its_face_group(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g id="cell-r1-c1"><rect id="face" x="10" y="10" width="30" height="30" fill="#aaeeaa"/><text id="label" x="25" y="30">ABC</text></g><rect id="neighbor" x="40" y="10" width="30" height="30" fill="#aaeeaa"/></svg>')
  self.job['texts']=[dict(id='label',content='ABC',group_id='cell-r1-c1',x=25,baseline=30,advance=20,ascent=15,descent=4,anchor='middle')]
  self.manifest.write_text(json.dumps(self.job));tool.make_candidate(self.manifest,self.base,self.output)
  with zipfile.ZipFile(self.output) as z:r=E.fromstring(z.read('ppt/slides/slide1.xml'))
  group=next(r.iter('{'+P+'}grpSp'))
  self.assertEqual([e.get('name') for e in group.iter('{'+P+'}cNvPr')],['cell-r1-c1','face','label'])
  self.assertEqual([e.text for e in group.iter('{'+A+'}t')],['ABC'])
  self.assertEqual(len(list(r.iter('{'+A+'}t'))),1)
  neighbor=next(s for s in r.iter('{'+P+'}sp') if s.find('.//{'+P+'}cNvPr').get('name')=='neighbor')
  before=E.tostring(neighbor)
  group.find('{'+P+'}grpSpPr/{'+A+'}xfrm/{'+A+'}off').set('x','500000')
  self.assertEqual(E.tostring(neighbor),before)
 def test_fitted_live_text_contributes_its_visible_frame_to_group_bounds(self):
  self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g id="wordmark"><rect id="face" x="10" y="10" width="10" height="10" fill="#ffffff"/><text id="label" x="0" y="0">ABC</text></g></svg>')
  self.job['texts']=[dict(id='label',content='ABC',group_id='wordmark',wordart=True,frame=[20,25,60,30])]
  self.manifest.write_text(json.dumps(self.job));tool.make_candidate(self.manifest,self.base,self.output)
  with zipfile.ZipFile(self.output) as z:r=E.fromstring(z.read('ppt/slides/slide1.xml'))
  ext=next(r.iter('{'+P+'}grpSp')).find('{'+P+'}grpSpPr/{'+A+'}xfrm/{'+A+'}ext')
  self.assertEqual(ext.attrib,{'cx':str(70*9525),'cy':str(45*9525)})
if __name__=='__main__':unittest.main()
