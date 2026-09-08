#!/usr/bin/env python3
"""Check an independent source contract against actual SVG geometry and text.

No model, network, optional package or source-image access. Does not certify
visual similarity. Unsupported requested geometry is an error, never a pass.
"""
import argparse
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NUM = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'

def numbers(value):
    return [float(v) for v in re.findall(NUM, value)]

def vertices(e):
    tag = e.tag.split('}')[-1]
    if tag == 'line':
        return [(float(e.get('x1',0)),float(e.get('y1',0))),
                (float(e.get('x2',0)),float(e.get('y2',0)))]
    if tag in ('polygon','polyline'):
        v=numbers(e.get('points',''))
        if len(v)<4 or len(v)%2: raise ValueError('invalid points')
        return list(zip(v[::2],v[1::2]))
    if tag != 'path': raise ValueError('unsupported edge geometry: '+tag)
    d=e.get('d','');tokens=re.findall(NUM+r'|[A-Za-z]',d)
    if re.sub(NUM+r'|[MLCQ]|[\s,]','',d):
        raise ValueError('only absolute M/L/C/Q edge commands supported')
    arity={'M':2,'L':2,'C':6,'Q':4};i=0;cmd=None;points=[]
    while i<len(tokens):
        if tokens[i] in arity:cmd=tokens[i];i+=1
        if cmd is None or i+arity[cmd]>len(tokens):raise ValueError('invalid edge path')
        vals=[float(x) for x in tokens[i:i+arity[cmd]]];i+=arity[cmd]
        if cmd=='M' and points:raise ValueError('multiple edge subpaths')
        points.append(tuple(vals[-2:]));cmd='L' if cmd=='M' else cmd
    if len(points)<2:raise ValueError('degenerate edge')
    return points

def box(e):
    tag=e.tag.split('}')[-1]
    if tag=='rect':return [float(e.get(k,0)) for k in ('x','y','width','height')]
    if tag in ('ellipse','circle'):
        x,y=float(e.get('cx',0)),float(e.get('cy',0))
        rx=float(e.get('rx',e.get('r',0)));ry=float(e.get('ry',e.get('r',0)))
        return [x-rx,y-ry,2*rx,2*ry]
    if tag=='path' and re.search('[CQ]',e.get('d','')):
        raise ValueError('curve bounds require visual review')
    v=vertices(e);xs,ys=zip(*v);return [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]

def check(reference, scene, base):
    root=ET.parse(base/scene['geometry']).getroot();ids={};transformed=set();errors=[]
    def walk(e, inherited=False):
        dirty=inherited or bool(e.get('transform'));eid=e.get('id')
        if eid:
            if eid in ids:errors.append({'id':eid,'error':'duplicate SVG ID'})
            ids[eid]=e
            if dirty:transformed.add(eid)
        for child in e:walk(child,dirty)
    walk(root)
    tol=float(reference.get('tolerance_px',2))
    if not math.isfinite(tol) or tol<0:raise ValueError('invalid tolerance')
    vb=numbers(root.get('viewBox',''))
    if reference['canvas'] != [scene['width'],scene['height']] or vb != [0,0,*reference['canvas']]:
        errors.append({'error':'canvas mismatch'})
    def element(eid):
        if eid not in ids:raise ValueError('missing SVG ID '+eid)
        if eid in transformed:raise ValueError('transform requires explicit review: '+eid)
        return ids[eid]
    objects={o['id']:o for o in reference.get('objects',[])}
    def endpoint(spec):
        if 'point' in spec:return spec['point']
        b=box(element(objects[spec['object']]['svg_id']));x,y,w,h=b
        f=spec.get('fraction',.5)
        p={'left':(x,y+f*h),'right':(x+w,y+f*h),
           'top':(x+f*w,y),'bottom':(x+f*w,y+h)}[spec['side']]
        off=spec.get('offset',[0,0]);return [p[0]+off[0],p[1]+off[1]]
    for kind in ('objects','texts','edges'):
        for item in reference.get(kind,[]):
            try:
                if kind=='objects':
                    e=element(item['svg_id'])
                    if 'bbox' in item:
                        actual=box(e)
                        if max(abs(a-b) for a,b in zip(actual,item['bbox']))>tol:
                            raise ValueError('source bbox mismatch: '+str(actual))
                elif kind=='texts':
                    actual=item.get('separator','').join(''.join(element(eid).itertext()) for eid in item['svg_ids'])
                    if actual != item['content']:raise ValueError('text mismatch: '+repr(actual))
                else:
                    e=element(item['svg_id']);v=vertices(e)
                    for end,p in [('start',v[0]),('end',v[-1])]:
                        expected=endpoint(item[end])
                        if math.dist(p,expected)>tol:
                            raise ValueError(end+' detached: actual='+str(p)+' expected='+str(expected))
                    if not(e.get('marker-end') or e.get('data-line-end')):
                        raise ValueError('missing end arrow decoration')
            except (ValueError,KeyError,TypeError) as ex:
                errors.append({'id':item.get('id'),'kind':kind,'error':str(ex)})
    text_ids={e.get('id') for e in root.iter() if e.tag.split('}')[-1]=='text'}
    edge_ids={e.get('id') for e in root.iter() if e.get('marker-end') or e.get('data-line-end')}
    covered_text={eid for t in reference.get('texts',[]) for eid in t['svg_ids']}
    covered_edges={e['svg_id'] for e in reference.get('edges',[])}
    exceptions=reference.get('exceptions',[])
    for e in exceptions:
        if e.get('kind') not in ('text','edge','object') or not e.get('reason') or e.get('svg_id') not in ids:
            errors.append({'error':'invalid exception','item':e})
    for kind,actual,covered in [('text',text_ids,covered_text),('edge',edge_ids,covered_edges)]:
        excluded={e.get('svg_id') for e in exceptions if e.get('kind')==kind and e.get('reason')}
        for eid in sorted(actual-covered-excluded,key=str):errors.append({'id':eid,'error':'uncovered '+kind})
    regions=reference.get('regions',[])
    pending=[r.get('id') for r in regions if r.get('status')!='reviewed']
    if not regions:pending=['no reference regions recorded']
    return {'status':'fail' if errors else 'review',
            'contract_status':'fail' if errors else 'pass_with_exceptions' if exceptions else 'pass',
            'visual_fidelity':'not_evaluated',
            'reference_independence':'not_verified_by_this_checker',
            'endpoint_checks':{'object_bound':sum('object' in e.get(k,{}) for e in reference.get('edges',[]) for k in ('start','end')),
                               'literal_points':sum('point' in e.get(k,{}) for e in reference.get('edges',[]) for k in ('start','end'))},
            'scope':'Source-contract geometry/text coverage; visual fidelity requires independent image review.',
            'coverage':{'text_runs':[len(text_ids&covered_text),len(text_ids)],
                        'arrow_edges':[len(edge_ids&covered_edges),len(edge_ids)]},
            'errors':errors,'exceptions':exceptions,'pending_regions':pending}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('reference',type=Path);p.add_argument('scene',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--snapshot',type=Path);a=p.parse_args()
    try:
        if a.snapshot:
            from reference_evidence import verify, sha
            meta,_,_=verify(a.snapshot)
            if sha(a.reference)!=meta['reference']['sha256']:
                raise ValueError('reference no longer matches frozen snapshot')
        result=check(json.loads(a.reference.read_text()),json.loads(a.scene.read_text()),a.scene.parent)
        result['snapshot_integrity']='verified' if a.snapshot else 'not_checked'
    except Exception as e:result={'status':'fail','errors':[{'error':str(e)}]}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
    # Successful execution means the internal contract is consistent, not fidelity approval.
    return 0 if result.get('contract_status')=='pass' else 1

if __name__=='__main__':raise SystemExit(main())
