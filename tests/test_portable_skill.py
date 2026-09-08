"""A copied Skill must export from a new directory without source-root settings."""
import json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'

class PortableSkillTest(unittest.TestCase):
 def test_relocated_copy_exports_live_grouped_text_without_original_root(self):
  with tempfile.TemporaryDirectory(prefix='portable-scene-test-') as tmp:
   d=Path(tmp)
   subprocess.run([sys.executable,str(ROOT/'install_skill.py'),'--copy','--destination',str(d/'install')],check=True,capture_output=True)
   installed=d/'install/paper-diagram';moved=d/'relocated';installed.rename(moved)
   scene=d/'input';scene.mkdir()
   (scene/'scene.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100"><g id="Cell"><rect id="cell-fill" x="30" y="20" width="70" height="40" fill="#aaddaa"/><text id="number" x="50" y="45">2.3</text></g></svg>')
   j=dict(width=200,height=100,geometry='scene.svg',texts=[dict(id='number',content='2.3',x=50,baseline=45,size=20,font='Arial',fill='#000000',advance=28,ascent=19,descent=5,group_id='Cell')])
   j['notes']='Source provenance supplied by the scene author.'
   (scene/'scene.json').write_text(json.dumps(j))
   env={k:v for k,v in os.environ.items() if k not in ['CELL_LOCAL_ROOT','CELL_LOCAL_PYTHON','PYTHONPATH']}
   result=subprocess.run([sys.executable,str(moved/'scripts/run.py'),'scene',str(scene/'scene.json'),'--output',str(d/'result.pptx')],cwd=d,env=env,check=True,capture_output=True,text=True)
   report=json.loads(result.stdout);self.assertTrue(report['no_embedded_media'])
   with zipfile.ZipFile(d/'result.pptx') as z:
    r=E.fromstring(z.read('ppt/slides/slide1.xml'))
    notes=E.fromstring(z.read('ppt/notesSlides/notesSlide1.xml'))
    self.assertEqual([e.text for e in notes.iter('{'+A+'}t')],[j['notes']])
   group=next(r.iter('{'+P+'}grpSp'));self.assertEqual([e.text for e in group.iter('{'+A+'}t')],['2.3'])
   self.assertFalse(any(p.is_symlink() for p in moved.rglob('*')))
   retry=subprocess.run([sys.executable,str(ROOT/'install_skill.py'),'--copy','--destination',str(d/'install')],check=True,capture_output=True)
   conflict=subprocess.run([sys.executable,str(ROOT/'install_skill.py'),'--copy','--destination',str(d/'install')],capture_output=True)
   self.assertNotEqual(conflict.returncode,0)
if __name__=='__main__':unittest.main()
