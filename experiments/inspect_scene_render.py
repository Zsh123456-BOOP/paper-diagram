"""Prepare non-destructive PPTX probes, then measure externally rendered PDFs.

prepare: scene.json saved.pptx --output new-directory
measure: probe-directory --pdf-dir rendered-pdfs
Requires reviewed qa.alignment_constraints for text checks. Rendering is a
separate step in the actual target application; this script never launches it.
"""
from pathlib import Path
import sys,json,zipfile,itertools,math,argparse
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cell_local.scene_qa import color_ink_box,center_error,arrow_contract,visibility_ratio
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
A='http://schemas.openxmlformats.org/drawingml/2006/main';P='http://schemas.openxmlformats.org/presentationml/2006/main';S='http://www.w3.org/2000/svg'

def hide(pr):
 for e in list(pr):
  if e.tag.split('}')[-1] in ('solidFill','gradFill','pattFill','noFill'):pr.remove(e)
 E.SubElement(pr,'{'+A+'}noFill')
 line=pr.find('{'+A+'}ln')
 if line is not None:
  for e in list(line):line.remove(e)
  E.SubElement(line,'{'+A+'}noFill')

def prepare(scene,pptx,out):
 out.mkdir(parents=True,exist_ok=False);j=json.loads(scene.read_text());sv=scene.parent/j['geometry'];root=E.parse(sv).getroot()
 palette=['%02X%02X%02X'%c for c in itertools.product(range(28,225,28),repeat=3)]
 bindings=j.get('qa',{}).get('alignment_constraints',[])
 if len(bindings)>len(palette):raise ValueError('Split large scenes into probe batches')
 colors={}
 known={t['id'] for t in j['texts']}
 for k,b in enumerate(bindings):
  b['probe_color']=palette[k]
  for tid in b['texts']:
   if tid not in known or tid in colors:raise ValueError('Bindings need unique known text IDs: '+tid)
   colors[tid]=palette[k]
 heads=[]
 for e in root.iter():
  if e.get('data-line-end')!='triangle':continue
  if e.tag.endswith('path'):
   pen=RecordingPen();parse_path(e.get('d'),pen);pts=[q for op,qs in pen.value if op in ('moveTo','lineTo','curveTo','qCurveTo') for q in qs if q is not None]
  elif e.tag.endswith('line'):pts=[tuple(float(e.get(a)) for a in ('x1','y1')),tuple(float(e.get(a)) for a in ('x2','y2'))]
  else:raise ValueError('Arrow probe currently requires path or line')
  end=pts[-1];prev=next((q for q in reversed(pts[:-1]) if q!=end),None)
  if prev is None:raise ValueError('Arrow has no tangent: '+e.get('id'))
  dx,dy=end[0]-prev[0],end[1]-prev[1];length=math.hypot(dx,dy);dx/=length;dy/=length;sw=float(e.get('stroke-width','1'))
  corners=[(end[0]-dx*t*sw-dy*n*sw,end[1]-dy*t*sw+dx*n*sw) for t in (.5,3.5) for n in (-1.7,1.7)]
  heads.append(dict(id=e.get('data-name',e.get('id')),endpoint=list(end),roi=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]))
 with zipfile.ZipFile(pptx) as z:original={n:z.read(n) for n in z.namelist()}
 exported=[]
 for mode in ['text','arrows-only','arrows-visible']:
  entries=original.copy();r=E.fromstring(entries['ppt/slides/slide1.xml']);slide=r.find('{'+P+'}cSld');bg=slide.find('{'+P+'}bg')
  if bg is not None:slide.remove(bg)
  bg=E.Element('{'+P+'}bg');pr=E.SubElement(bg,'{'+P+'}bgPr');E.SubElement(E.SubElement(pr,'{'+A+'}solidFill'),'{'+A+'}srgbClr',val='FFFFFF');slide.insert(0,bg)
  for sp in r.iter('{'+P+'}sp'):
   pr=sp.find('{'+P+'}spPr');tx=sp.find('{'+P+'}txBody');name=sp.find('.//{'+P+'}cNvPr').get('name');arrow=pr.find('{'+A+'}ln/{'+A+'}tailEnd') is not None
   if mode=='text':
    if arrow:exported.append(name)
    if tx is None:hide(pr)
    else:
     for fill in tx.iter('{'+A+'}solidFill'):
      for c in list(fill):fill.remove(c)
      E.SubElement(fill,'{'+A+'}srgbClr',val=colors.get(name,'FFFFFF'))
   elif arrow:
    line=pr.find('{'+A+'}ln')
    for e in list(line):
     if e.tag.split('}')[-1] in ('solidFill','gradFill','noFill'):line.remove(e)
    fill=E.Element('{'+A+'}solidFill');E.SubElement(fill,'{'+A+'}srgbClr',val='FF00FF');line.insert(0,fill)
   elif mode=='arrows-only':
    hide(pr)
    if tx is not None:sp.remove(tx)
  entries['ppt/slides/slide1.xml']=E.tostring(r,encoding='utf-8',xml_declaration=True)
  with zipfile.ZipFile(out/(mode+'.pptx'),'w',zipfile.ZIP_DEFLATED) as z:
   for n,data in entries.items():z.writestr(n,data)
 spec=dict(canvas=[j['width'],j['height']],bindings=bindings,heads=heads,arrow_contract=arrow_contract([h['id'] for h in heads],exported),source=str(pptx))
 (out/'probe.json').write_text(json.dumps(spec,indent=2));return spec

def measure(directory,pdf_dir,renderer):
 import numpy as np
 import pypdfium2 as pdfium
 spec=json.loads((directory/'probe.json').read_text());w,h=spec['canvas'];images={}
 for mode in ['text','arrows-only','arrows-visible']:
  doc=pdfium.PdfDocument(pdf_dir/(mode+'.pdf'));page=doc[0]
  if len(doc)!=1 or abs(page.get_width()/page.get_height()-w/h)>1e-4:raise ValueError('Probe page/canvas mismatch')
  images[mode]=page.render(scale=4*w/page.get_width()).to_pil().convert('RGB');doc.close()
 text=[]
 for b in spec['bindings']:
  x0,y0,x1,y1=b['box'];box=color_ink_box(images['text'],b['probe_color'],[x0-5,y0-5,x1+5,y1+5],pixels_per_unit=4)
  error=center_error(box,b['target']) if box else None
  text.append(dict(id=b['id'],text_ids=b['texts'],target=b['target'],ink_box=box,error=error,within_half_pixel=error is not None and max(map(abs,error))<=.5))
 def magenta(im):
  a=np.array(im);return (a[:,:,0]>200)&(a[:,:,1]<80)&(a[:,:,2]>200)
 a=magenta(images['arrows-only']);v=magenta(images['arrows-visible']);heads=[]
 for tip in spec['heads']:
  x0,y0,x1,y1=[round(x*4) for x in tip['roi']];x0=max(0,x0);y0=max(0,y0);x1=min(a.shape[1],x1);y1=min(a.shape[0],y1)
  result=visibility_ratio(a[y0:y1,x0:x1],v[y0:y1,x0:x1]);heads.append({**tip,**result,'needs_review':result['ratio'] is None or result['ratio']<.6})
 report=dict(renderer=renderer,pixels_per_source_pixel=4,scope='Export/render alignment, not proof of source reconstruction',text=text,arrows=heads,arrow_contract=spec['arrow_contract'])
 (directory/'render-qa.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
 q=sub.add_parser('prepare');q.add_argument('scene',type=Path);q.add_argument('pptx',type=Path);q.add_argument('--output',required=True,type=Path)
 q=sub.add_parser('measure');q.add_argument('directory',type=Path);q.add_argument('--pdf-dir',required=True,type=Path);q.add_argument('--renderer',required=True)
 args=p.parse_args()
 if args.mode=='prepare':r=prepare(args.scene,args.pptx,args.output);print(json.dumps({'bindings':len(r['bindings']),'arrows':len(r['heads']),'contract':r['arrow_contract']}))
 else:
  r=measure(args.directory,args.pdf_dir,args.renderer);print(json.dumps({'labels':len(r['text']),'labels_outside_half_pixel':sum(not t['within_half_pixel'] for t in r['text']),'arrows_to_review':sum(t['needs_review'] for t in r['arrows']),'contract':r['arrow_contract']}))
