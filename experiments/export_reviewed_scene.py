"""Portable scene export from an Artifact Tool authored blank PPTX template.

No Office installation, Node runtime, model call or network request is required.
The scene has already been interpreted and measured by its author.
"""
from pathlib import Path
import argparse,json,tempfile,zipfile,math
import xml.etree.ElementTree as E
from svg_scene_to_pptx import make_candidate,A,P,node
ROOT=Path(__file__).resolve().parents[1]

def text_base(manifest,template,output):
 with zipfile.ZipFile(template) as z:entries={n:z.read(n) for n in z.namelist()}
 if any(n.startswith('ppt/media/') for n in entries):raise ValueError('Template must be blank, without media')
 pres=E.fromstring(entries['ppt/presentation.xml']);size=pres.find('{'+P+'}sldSz')
 unit=9525*manifest.get('scale',1)
 size.set('cx',str(round(manifest['width']*unit)));size.set('cy',str(round(manifest['height']*unit)))
 slide=E.fromstring(entries['ppt/slides/slide1.xml']);tree=slide.find('.//{'+P+'}spTree')
 if len(tree)>2:raise ValueError('Template slide must contain no shapes')
 for i,t in enumerate(manifest['texts'],2):
  vals=[t[k] for k in ['x','baseline','size','advance','ascent','descent']]
  if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vals) or t['size']<=0:raise ValueError('Invalid measured text')
  sp=node(tree,'p:sp');nv=node(sp,'p:nvSpPr');node(nv,'p:cNvPr',id=i,name=t['id']);node(nv,'p:cNvSpPr',txBox='1');node(nv,'p:nvPr')
  pr=node(sp,'p:spPr');tr=node(pr,'a:xfrm')
  x=t['x']-(t['advance']/2 if t.get('anchor')=='middle' else t['advance'] if t.get('anchor')=='end' else 0)
  frame=t['frame'] if t.get('wordart') else [x,t['baseline']-t['ascent'],t['advance']+3,t['ascent']+t['descent']+2]
  node(tr,'a:off',x=round(frame[0]*unit),y=round(frame[1]*unit));node(tr,'a:ext',cx=round(frame[2]*unit),cy=round(frame[3]*unit))
  node(node(pr,'a:prstGeom',prst='rect'),'a:avLst');node(pr,'a:noFill');node(node(pr,'a:ln'),'a:noFill')
  tx=node(sp,'p:txBody');body=node(tx,'a:bodyPr',wrap='none',lIns='0',rIns='0',tIns='0',bIns='0',anchor='t');node(body,'a:noAutofit');node(tx,'a:lstStyle')
  para=node(tx,'a:p');pp=node(para,'a:pPr',algn='l');node(node(pp,'a:spcBef'),'a:spcPts',val='0');node(node(pp,'a:spcAft'),'a:spcPts',val='0')
  run=node(para,'a:r');rp=node(run,'a:rPr',lang='en-US',sz=round(t['size']*manifest.get('scale',1)*75),b=int(t.get('bold',False)),i=int(t.get('italic',False)))
  node(node(rp,'a:solidFill'),'a:srgbClr',val=t['fill'].lstrip('#').upper());node(rp,'a:latin',typeface=t['font']);node(rp,'a:ea',typeface=t['font']);node(rp,'a:cs',typeface=t['font'])
  node(run,'a:t').text=t['content'];node(para,'a:endParaRPr',lang='en-US')
 entries['ppt/presentation.xml']=E.tostring(pres,encoding='utf-8',xml_declaration=True)
 entries['ppt/slides/slide1.xml']=E.tostring(slide,encoding='utf-8',xml_declaration=True)
 # If present, populate only the slide's source note, never existing user notes.
 note='ppt/notesSlides/notesSlide1.xml'
 if note in entries:
  nr=E.fromstring(entries[note])
  for sp in nr.iter('{'+P+'}sp'):
   ph=sp.find('.//{'+P+'}ph')
   if ph is not None and ph.get('type')=='body':
    body=sp.find('{'+P+'}txBody')
    for para in list(body.findall('{'+A+'}p')):body.remove(para)
    node(node(node(body,'a:p'),'a:r'),'a:t').text=manifest.get('notes','')
  entries[note]=E.tostring(nr,encoding='utf-8',xml_declaration=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for n,data in entries.items():z.writestr(n,data)

def export_scene(scene,output,template=None):
 scene=Path(scene);output=Path(output)
 template=Path(template) if template else ROOT/'skills/paper-diagram/assets/blank-scene.pptx'
 if not template.exists():
  # A copied skill keeps runtime code below its own root.
  template=ROOT.parent/'assets/blank-scene.pptx'
 with tempfile.TemporaryDirectory(prefix='cell-local-scene-') as d:
  base=Path(d)/'base.pptx';text_base(json.loads(scene.read_text(encoding='utf-8')),template,base)
  report=make_candidate(scene,base,output)
 output.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--template',type=Path);args=p.parse_args()
 print(json.dumps(export_scene(args.scene,args.output,args.template)))
