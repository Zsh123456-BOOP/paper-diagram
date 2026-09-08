"""Insert a reviewed SVG scene as native grouped curves into an existing PPTX.

The base package is authored separately by the available presentation tool.
Its native text objects must match the companion scene manifest. SVG artwork
is limited to common geometry and axis-aligned object-box gradients.
No bitmap or python-pptx authoring is used by this helper.
"""
from pathlib import Path
import argparse,copy,json,sys,zipfile,math,re
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/cell_local/_vendor/cell_su7'))
from prepare_geometry_cache import collect_atoms,parse_canvas
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
A='http://schemas.openxmlformats.org/drawingml/2006/main';P='http://schemas.openxmlformats.org/presentationml/2006/main';S='http://www.w3.org/2000/svg'
E.register_namespace('a',A);E.register_namespace('p',P)
def node(parent,tag,**attrs):
 prefix,name=tag.split(':');return E.SubElement(parent,'{'+{'a':A,'p':P}[prefix]+'}'+name,{k:str(v) for k,v in attrs.items()})
def solid(parent,color,alpha=100):
 rgb=node(node(parent,'a:solidFill'),'a:srgbClr',val=''.join(f'{round(c):02X}' for c in color))
 if alpha<100:node(rgb,'a:alpha',val=round(alpha*1000))
def make_candidate(scene_path,base,output):
 if output.suffix.lower()!='.pptx':raise ValueError('Output must be PPTX')
 if output.exists() or output.with_suffix('.json').exists():raise FileExistsError('Choose new candidate and report paths')
 manifest=json.loads(scene_path.read_text());w=manifest['width'];h=manifest['height'];scale=manifest.get('scale',1);unit=9525*scale
 if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (w,h,scale)):raise ValueError('Canvas and scale must be finite positive numbers')
 geometry_path=Path(manifest['geometry'])
 if not geometry_path.is_absolute():geometry_path=scene_path.parent/geometry_path
 svg=E.parse(geometry_path).getroot();plain=copy.deepcopy(svg);gradients={};uses={};stroke_uses={};decorations={};presets={};names={}
 if parse_canvas(svg)!=[0,0,w,h]:raise ValueError('SVG canvas differs from the scene manifest')
 def inspect_geometry(el,transformed=False):
  transformed=transformed or bool(el.get('transform'));tag=el.tag.rsplit('}',1)[-1];eid=el.get('id')
  if tag=='defs':return
  if eid:names[eid]=el.get('data-name',eid)
  if transformed and el.get('stroke','').startswith('url(#'):raise ValueError('Gradient strokes must use untransformed geometry')
  dash=el.get('stroke-dasharray','none');arrow=el.get('data-line-end');marker=el.get('marker-end')
  if marker and arrow!='triangle':raise ValueError('SVG marker-end needs explicit data-line-end="triangle" mapping')
  if dash!='none' or arrow:
   if not eid or tag not in ('path','line','polyline') or transformed:raise ValueError('Decorated lines must be named, untransformed geometry')
   if float(el.get('stroke-dashoffset','0'))!=0:raise ValueError('Nonzero dash offset is not supported')
   values=[float(v) for v in re.split(r'[\s,]+',dash.strip())] if dash!='none' else []
   if values and (not all(math.isfinite(v) and v>0 for v in values)):raise ValueError('Dash lengths must be finite and positive')
   if len(values)%2:values*=2
   if arrow and arrow!='triangle':raise ValueError('Only triangular line ends are supported')
   decorations[eid]={'dash':values,'arrow':arrow}
   el.attrib.pop('stroke-dasharray',None)
  if eid and not transformed and (tag in ('circle','ellipse') or tag=='rect' and not el.get('rx') and not el.get('ry')):
   presets[eid]='ellipse' if tag in ('circle','ellipse') else 'rect'
  for ch in el:inspect_geometry(ch,transformed)
 inspect_geometry(plain)
 for g in svg.findall('.//{'+S+'}linearGradient'):
  coords=tuple(float(g.get(k,default)) for k,default in [('x1','0'),('y1','0'),('x2','0'),('y2','1')])
  if coords not in ((0,0,1,0),(0,0,0,1)) or g.get('gradientUnits','objectBoundingBox')!='objectBoundingBox' or g.get('gradientTransform') or g.get('spreadMethod','pad')!='pad':raise ValueError('Only untransformed axis-aligned object-box gradients are supported')
  stops=[(float(t.get('offset')),t.get('stop-color'),float(t.get('stop-opacity','1'))) for t in g]
  if len(stops)<2 or stops[0][0]!=0 or stops[-1][0]!=1 or any(a[0]>=b[0] for a,b in zip(stops,stops[1:])):raise ValueError('Gradient stops must strictly increase from 0 to 1')
  if any(not math.isfinite(p) or not 0<=p<=1 or not math.isfinite(alpha) or not 0<=alpha<=1 or not re.fullmatch(r'#[0-9a-fA-F]{6}',col or '') for p,col,alpha in stops):raise ValueError('Invalid gradient stop position, color or opacity')
  gradients[g.get('id')]={'stops':stops,'angle':0 if coords[2] else 5400000}
 discarded=0
 for parent in plain.iter():
  for ch in list(parent):
   if ch.tag=='{'+S+'}text' and not any(t['id']==ch.get('id') and t.get('group_id') for t in manifest['texts']):parent.remove(ch)
   elif ch.tag=='{'+S+'}path':
    pen=RecordingPen();parse_path(ch.get('d',''),pen);current=None;start=None;drawn=False
    for op,points in pen.value:
     if op=='moveTo':current=start=points[0]
     elif op in ('lineTo','curveTo','qCurveTo'):
      if any(p is not None and p!=current for p in points):drawn=True
      current=points[-1]
     elif op=='closePath' and current!=start:drawn=True
    if not drawn:
     if ch.get('data-line-end'):raise ValueError('Arrow has no drawable shaft: '+ch.get('id',''))
     parent.remove(ch);discarded+=1
  fill=parent.get('fill','')
  if fill.startswith('url(#'):
   gid=fill[5:-1];uses[parent.get('id')]=gradients[gid];parent.set('fill',gradients[gid]['stops'][0][1])
  stroke=parent.get('stroke','')
  if stroke.startswith('url(#'):
   gid=stroke[5:-1];stroke_uses[parent.get('id')]=gradients[gid];parent.set('stroke',gradients[gid]['stops'][0][1])
  if parent.tag.rsplit('}',1)[-1] in ('image','use','foreignObject') or any(x in parent.attrib for x in ('mask','clip-path','filter')):raise ValueError('Unsupported rendered SVG feature')
 atoms=[a for a in collect_atoms(plain) if a.get('kind')!='text'];by={a['sourceId']:a for a in atoms}
 if len(by)!=len(atoms):raise ValueError('Geometry IDs must be unique')
 with zipfile.ZipFile(base) as z:entries={n:z.read(n) for n in z.namelist()}
 presentation=E.fromstring(entries['ppt/presentation.xml']);size=presentation.find('{'+P+'}sldSz')
 if size is None or [int(size.get('cx')),int(size.get('cy'))]!=[round(w*unit),round(h*unit)]:raise ValueError('Base slide dimensions differ from the scene')
 if len(presentation.findall('.//{'+P+'}sldId'))!=1:raise ValueError('Use a single-slide scene base')
 slide=E.fromstring(entries['ppt/slides/slide1.xml']);tree=slide.find('.//{'+P+'}spTree')
 if list(slide.iter('{'+P+'}pic')):raise ValueError('Base scene must not contain embedded pictures')
 text_by_name={sp.find('.//{'+P+'}cNvPr').get('name'):sp for sp in tree.findall('{'+P+'}sp')}
 if set(text_by_name)!={t['id'] for t in manifest['texts']}:raise ValueError('Base objects must match the reviewed text IDs')
 for t in manifest['texts']:
  sp=text_by_name[t['id']];existing=''.join(x.text or '' for x in sp.iter('{'+A+'}t'))
  if existing!=t['content']:raise ValueError('Base text differs from reviewed manifest: '+t['id'])
  if t.get('wordart'):
   body=sp.find('.//{'+A+'}bodyPr');body.set('fromWordArt','1');body.set('wrap','none')
   for ch in list(body):body.remove(ch)
   node(node(body,'a:prstTxWarp',prst='textPlain'),'a:avLst');node(body,'a:noAutofit')
  if t.get('rotation'):sp.find('.//{'+A+'}xfrm').set('rot',str(round(t['rotation']*60000)))
  if t.get('pptx_offset'):
   offset=t['pptx_offset']
   if len(offset)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in offset):raise ValueError('Invalid PPTX render offset')
   off=sp.find('{'+P+'}spPr/{'+A+'}xfrm/{'+A+'}off')
   if off is None:raise ValueError('Calibrated text needs an explicit position')
   for axis,delta in zip(('x','y'),offset):off.set(axis,str(int(off.get(axis))+round(delta*unit)))
 next_id=max(int(n.get('id',0)) for n in slide.iter('{'+P+'}cNvPr'))+1
 stat={'native_paths':0,'native_groups':0,'control_points':0,'text_objects':len(manifest['texts']),'pictures':0,'discarded_degenerate_paths':discarded,'native_presets':0,'native_dashed_lines':0,'native_arrow_lines':0}
 def uid():
  nonlocal next_id
  n=next_id;next_id+=1;return n
 def gradient(parent,spec,opacity):
  grad=node(parent,'a:gradFill',rotWithShape='1');lst=node(grad,'a:gsLst')
  for pos,col,alpha in spec['stops']:
   stop=node(lst,'a:gs',pos=round(pos*100000));c=node(stop,'a:srgbClr',val=col.lstrip('#').upper())
   combined=opacity*alpha
   if combined<100:node(c,'a:alpha',val=round(combined*1000))
  node(grad,'a:lin',ang=spec['angle'],scaled='1')
 def atom_bounds(atom):
  coords=[p for sub in atom['subpaths'] for pt in sub['points'] for p in (pt['a'],pt['l'],pt['r'])]
  return [max(0,min(p[0] for p in coords)),max(0,min(p[1] for p in coords)),min(w,max(p[0] for p in coords)),min(h,max(p[1] for p in coords))]
 def bounds(elem):
  ids=[x.get('id') for x in elem.iter() if x.get('id') in by]
  boxes=[atom_bounds(by[i]) for i in ids]
  descendants={x.get('id') for x in elem.iter()}
  for t in manifest['texts']:
   if t.get('group_id') and t['id'] in descendants:
    if t.get('wordart'):
     x,y,ww,hh=t['frame'];boxes.append([x,y,x+ww,y+hh]);continue
    advance=t['advance'];x=t['x']-(advance/2 if t.get('anchor')=='middle' else advance if t.get('anchor')=='end' else 0)
    dx,dy=t.get('pptx_offset',[0,0])
    boxes.append([x+dx,t['baseline']-t['ascent']+dy,x+advance+3+dx,t['baseline']+t['descent']+2+dy])
  return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else [0,0,w,h]
 def group(parent,elem):
  b=bounds(elem);x,y=b[:2];ww=max(.001,b[2]-x);hh=max(.001,b[3]-y)
  g=node(parent,'p:grpSp');nv=node(g,'p:nvGrpSpPr');node(nv,'p:cNvPr',id=uid(),name=elem.get('data-name',elem.get('id','Scene group')));node(nv,'p:cNvGrpSpPr');node(nv,'p:nvPr')
  tr=node(node(g,'p:grpSpPr'),'a:xfrm')
  for off,ext in [('off','ext'),('chOff','chExt')]:node(tr,'a:'+off,x=round(x*unit),y=round(y*unit));node(tr,'a:'+ext,cx=max(1,round(ww*unit)),cy=max(1,round(hh*unit)))
  stat['native_groups']+=1;return g
 def curve(parent,atom):
  x,y,r,b=atom_bounds(atom);ww=max(.001,r-x);hh=max(.001,b-y)
  # Compact local path units retain 0.01 source-pixel precision.
  punit=100;px=lambda q:{'x':round((q[0]-x)*punit),'y':round((q[1]-y)*punit)}
  for part in atom['paintParts']:
   if part['fillRule']!='nonzero':raise ValueError('Normalize evenodd contours before native export')
   shape=node(parent,'p:sp');nv=node(shape,'p:nvSpPr');node(nv,'p:cNvPr',id=uid(),name=names.get(atom['sourceId'],atom['sourceId']));node(nv,'p:cNvSpPr');node(nv,'p:nvPr')
   pr=node(shape,'p:spPr');tr=node(pr,'a:xfrm');node(tr,'a:off',x=round(x*unit),y=round(y*unit));node(tr,'a:ext',cx=max(1,round(ww*unit)),cy=max(1,round(hh*unit)))
   geo=node(pr,'a:custGeom')
   for n in ('avLst','gdLst','ahLst','cxnLst'):node(geo,'a:'+n)
   node(geo,'a:rect',l='0',t='0',r='r',b='b');path=node(node(geo,'a:pathLst'),'a:path',w=max(1,round(ww*punit)),h=max(1,round(hh*punit)),fill='norm' if part['filled'] else 'none',stroke='1' if part['stroked'] else '0',extrusionOk='0')
   for sub in atom['subpaths']:
    pts=sub['points'];node(node(path,'a:moveTo'),'a:pt',**px(pts[0]['a']));stat['control_points']+=len(pts)
    pairs=list(zip(pts,pts[1:]))+([(pts[-1],pts[0])] if sub['closed'] else [])
    for prev,cur in pairs:
     if prev['r']==prev['a'] and cur['l']==cur['a']:node(node(path,'a:lnTo'),'a:pt',**px(cur['a']))
     else:
      c=node(path,'a:cubicBezTo')
      for q in (prev['r'],cur['l'],cur['a']):node(c,'a:pt',**px(q))
    if sub['closed']:node(path,'a:close')
   if atom['sourceId'] in presets:
    pr.remove(geo);node(node(pr,'a:prstGeom',prst=presets[atom['sourceId']]),'a:avLst');stat['native_presets']+=1
   if part['filled']:
    if atom['sourceId'] in uses:
     gradient(pr,uses[atom['sourceId']],part['opacity'])
    else:solid(pr,part['fillColor'],part['opacity'])
   else:node(pr,'a:noFill')
   line=node(pr,'a:ln',w=max(1,round(part['strokeWidth']*unit)),cap={'round':'rnd','square':'sq','butt':'flat'}.get(part['strokeCap'],'flat'))
   if part['stroked']:
    if atom['sourceId'] in stroke_uses:gradient(line,stroke_uses[atom['sourceId']],part['opacity'])
    else:solid(line,part['strokeColor'],part['opacity'])
   else:node(line,'a:noFill')
   decoration=decorations.get(atom['sourceId'],{})
   if decoration.get('dash'):
    if not part['stroked'] or part['strokeWidth']<=0:raise ValueError('Dashed line needs a positive stroke width')
    ds=node(line,'a:custDash');vals=decoration['dash'];sw=part['strokeWidth']
    for d,sp in zip(vals[::2],vals[1::2]):node(ds,'a:ds',d=max(1,round(d/sw*100000)),sp=max(1,round(sp/sw*100000)))
    stat['native_dashed_lines']+=1
   node(line,'a:round' if part['strokeJoin']=='round' else 'a:miter')
   if decoration.get('arrow'):
    node(line,'a:tailEnd',type='triangle',w='med',len='med');stat['native_arrow_lines']+=1
   stat['native_paths']+=1
 def walk(elem,parent):
  id=elem.get('id')
  if id in by:curve(parent,by[id]);return
  if elem.tag=='{'+S+'}text' and id in text_by_name:
   t=next(t for t in manifest['texts'] if t['id']==id)
   if t.get('group_id'):
    sp=text_by_name[id];tree.remove(sp);parent.append(sp)
   return
  if elem.tag.rsplit('}',1)[-1] in ('defs','text','title','desc','metadata'):return
  target=group(parent,elem) if elem.tag=='{'+S+'}g' and len(elem)>0 else parent
  for ch in elem:walk(ch,target)
 temporary=E.Element('temporary');walk(plain,temporary)
 for i,ch in enumerate(list(temporary)):tree.insert(i+2,ch)
 entries['ppt/slides/slide1.xml']=E.tostring(slide,encoding='utf-8',xml_declaration=True)
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for n,d in entries.items():z.writestr(n,d)
 stat.update({'slide_xml_bytes':len(entries['ppt/slides/slide1.xml']),'canvas':[w*scale,h*scale],'native_gradients':len(uses)+len(stroke_uses),'native_gradient_strokes':len(stroke_uses),'no_embedded_media':not any(n.startswith('ppt/media/') for n in entries)})
 return stat
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('scene',type=Path);p.add_argument('base',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 report=make_candidate(args.scene,args.base,args.output);args.output.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
