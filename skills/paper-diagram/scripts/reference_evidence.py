#!/usr/bin/env python3
"""Freeze reference evidence and compare actual image pixels, never certify fidelity.

Freeze uses Pillow; compare additionally uses NumPy and SciPy. No model/API call.
Hashes detect changes, not whether the author honestly measured the reference.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
from datetime import datetime, timezone


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def read_image(path):
    from PIL import Image
    with Image.open(path) as src:
        im=src.convert('RGBA')
        bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im)
        return bg.convert('RGB')


def freeze(source, reference, output):
    source,reference,output=map(Path,(source,reference,output))
    if output.exists():raise ValueError('refusing to overwrite reference snapshot')
    im=read_image(source);contract=json.loads(reference.read_text())
    if contract.get('canvas')!=list(im.size):raise ValueError('reference canvas must equal original image dimensions')
    regions=contract.get('regions',[])
    if not regions:raise ValueError('record reference regions before drawing')
    names=set()
    for r in regions:
        if r.get('id') in names or not r.get('id'):raise ValueError('region IDs must be unique')
        names.add(r['id'])
        if r.get('status','pending')!='pending':raise ValueError('freeze before review; keep review results in a separate report')
        x,y,w,h=r['bbox']
        if not all(math.isfinite(v) for v in (x,y,w,h)) or min(x,y)<0 or min(w,h)<=0 or x+w>im.width or y+h>im.height:
            raise ValueError('invalid region bounds: '+r['id'])
    output.mkdir(parents=True)
    saved_source=output/('source'+source.suffix.lower());shutil.copyfile(source,saved_source)
    saved_reference=output/'reference.json';shutil.copyfile(reference,saved_reference)
    manifest={'schema':'cell-local.reference-evidence.v1','created_utc':datetime.now(timezone.utc).isoformat(),
              'source':{'file':saved_source.name,'sha256':sha(saved_source),'size':list(im.size)},
              'reference':{'file':saved_reference.name,'sha256':sha(saved_reference)},
              'claim_boundary':'Snapshot detects subsequent changes; it does not prove independent measurement or complete transcription.'}
    write_json(output/'evidence.json',manifest)
    return manifest


def verify(snapshot):
    snapshot=Path(snapshot);meta=json.loads(snapshot.read_text());base=snapshot.parent
    for key in ('source','reference'):
        path=base/meta[key]['file']
        if sha(path)!=meta[key]['sha256']:raise ValueError('frozen '+key+' changed; create a reasoned new snapshot, do not overwrite')
    return meta,base/meta['source']['file'],base/meta['reference']['file']


def edge_map(a):
    import numpy as np
    from scipy.ndimage import gaussian_filter
    smooth=gaussian_filter(a.astype(float)/255,(.55,.55,0))
    dx=np.max(np.abs(np.diff(smooth,axis=1)),axis=2)
    dy=np.max(np.abs(np.diff(smooth,axis=0)),axis=2)
    e=np.zeros(a.shape[:2],bool);e[:,1:]|=dx>.08;e[1:,:]|=dy>.08
    return e


def compare(snapshot, render, artifact, output, renderer, scene=None, edge_tolerance=2.0):
    import numpy as np
    from PIL import Image,ImageDraw
    from scipy.ndimage import distance_transform_edt
    snapshot,render,artifact,output=map(Path,(snapshot,render,artifact,output))
    if output.exists():raise ValueError('use a new comparison directory for each candidate')
    if not math.isfinite(edge_tolerance) or edge_tolerance<0:raise ValueError('invalid edge tolerance')
    meta,source,reference=verify(snapshot)
    ref=read_image(source);got=read_image(render)
    if abs(got.width/got.height-ref.width/ref.height)/(ref.width/ref.height)>.002:
        raise ValueError('render aspect ratio differs; do not stretch it to fit')
    if not renderer.strip():raise ValueError('record the renderer and how this exact artifact was exported')
    original_render_size=list(got.size)
    # Resolution normalization only; no translation, local registration or crop warps.
    if got.size!=ref.size:got=got.resize(ref.size,Image.Resampling.LANCZOS)
    a,b=np.asarray(ref),np.asarray(got)
    ea,eb=edge_map(a),edge_map(b)
    maximum=float(math.hypot(*ref.size))
    da=distance_transform_edt(~ea) if ea.any() else np.full(ea.shape,maximum)
    db=distance_transform_edt(~eb) if eb.any() else np.full(eb.shape,maximum)
    difference=np.max(np.abs(a.astype(float)-b.astype(float)),axis=2)/255
    contract=json.loads(reference.read_text())
    def stats(identifier,bbox,kind):
        x,y,w,h=bbox;x0,y0=int(math.floor(x)),int(math.floor(y));x1,y1=int(math.ceil(x+w)),int(math.ceil(y+h))
        sl=np.s_[y0:y1,x0:x1];ar,br=ea[sl],eb[sl];n1,n2=int(ar.sum()),int(br.sum())
        distances1=db[sl][ar];distances2=da[sl][br]
        lost=float(np.mean(distances1>edge_tolerance)) if n1 else 0.
        added=float(np.mean(distances2>edge_tolerance)) if n2 else 0.
        changed=float(np.mean(difference[sl]>.12));mae=float(difference[sl].mean())
        review=((n1>=12 and lost>.2) or (n2>=12 and added>.2) or changed>.15)
        return {'id':identifier,'kind':kind,'bbox':[x0,y0,x1-x0,y1-y0],
                'source_edge_pixels':n1,'render_edge_pixels':n2,
                'source_edges_without_match_fraction':round(lost,4),'render_edges_without_match_fraction':round(added,4),
                'changed_pixel_fraction':round(changed,4),'mean_max_channel_difference':round(mae,4),
                'needs_review':bool(review)}
    regions=[stats(r['id'],r['bbox'],'named') for r in contract['regions']]
    # Full-canvas tiles make omitted/unregistered regions visible too.
    tiles=[stats(f'tile-{x}-{y}',[x,y,min(128,ref.width-x),min(128,ref.height-y)],'tile')
           for y in range(0,ref.height,128) for x in range(0,ref.width,128)]
    output.mkdir(parents=True)
    side=Image.new('RGB',(ref.width*2,ref.height),'white');side.paste(ref,(0,0));side.paste(got,(ref.width,0));side.save(output/'comparison.png')
    Image.blend(ref,got,.5).save(output/'overlay.png')
    # Color only mismatched edges, not a synthesized replacement for the figure.
    marked=got.copy();pixels=np.asarray(marked).copy();pixels[ea&(db>edge_tolerance)]=[240,30,70];pixels[eb&(da>edge_tolerance)]=[0,120,240]
    Image.fromarray(pixels).save(output/'edge-differences.png')
    draw=ImageDraw.Draw(marked)
    for t in tiles:
        if t['needs_review']:
            x,y,w,h=t['bbox'];draw.rectangle((x,y,x+w-1,y+h-1),outline='#EA2348',width=2)
    marked.save(output/'review-regions.png')
    # Exact-file binding prevents accidental stale reviews; no claim of authenticated rendering.
    bindings={'artifact':{'path':str(artifact.resolve()),'sha256':sha(artifact)},
              'render':{'path':str(render.resolve()),'sha256':sha(render)},
              'evidence':{'path':str(snapshot.resolve()),'sha256':sha(snapshot)},
              'reference_sha256':meta['reference']['sha256'],'source_sha256':meta['source']['sha256']}
    if scene:
        scene=Path(scene);s=json.loads(scene.read_text());geo=scene.parent/s['geometry']
        bindings.update(scene={'path':str(scene.resolve()),'sha256':sha(scene)},geometry={'path':str(geo.resolve()),'sha256':sha(geo)})
    result={'schema':'cell-local.pixel-evidence.v1','status':'needs_visual_review',
            'bindings':bindings,'renderer':renderer,'source_size':list(ref.size),'render_size':original_render_size,
            'registration':'resolution normalization only; no position adjustment',
            'edge_tolerance_source_px':edge_tolerance,'regions':regions,'tiles':tiles,
            'flagged_regions':[r['id'] for r in regions if r['needs_review']],
            'flagged_tiles':sum(t['needs_review'] for t in tiles),
            'claim_boundary':'Pixel differences flag review, not scientific correctness. Even zero flags is not fidelity approval. Renderer provenance is caller-supplied.'}
    write_json(output/'pixel-evidence.json',result)
    return result


def verify_report(path):
    report=json.loads(Path(path).read_text());bindings=report['bindings']
    for key,item in bindings.items():
        if isinstance(item,dict) and 'path' in item:
            if sha(item['path'])!=item['sha256']:raise ValueError('stale evidence: '+key+' changed')
    meta,_,_=verify(bindings['evidence']['path'])
    if meta['reference']['sha256']!=bindings['reference_sha256'] or meta['source']['sha256']!=bindings['source_sha256']:
        raise ValueError('reference binding mismatch')
    return {'status':'bindings_valid','visual_fidelity':'not_certified'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='command',required=True)
    f=sp.add_parser('freeze');f.add_argument('source',type=Path);f.add_argument('reference',type=Path);f.add_argument('--output',required=True,type=Path)
    c=sp.add_parser('compare');c.add_argument('snapshot',type=Path);c.add_argument('--render',required=True,type=Path);c.add_argument('--artifact',required=True,type=Path);c.add_argument('--output',required=True,type=Path);c.add_argument('--renderer',required=True);c.add_argument('--scene',type=Path);c.add_argument('--edge-tolerance',type=float,default=2)
    v=sp.add_parser('verify');v.add_argument('report',type=Path)
    a=p.parse_args()
    try:
        if a.command=='freeze':r=freeze(a.source,a.reference,a.output)
        elif a.command=='compare':
            r=compare(a.snapshot,a.render,a.artifact,a.output,a.renderer,a.scene,a.edge_tolerance)
            r={k:r[k] for k in ('status','flagged_regions','flagged_tiles','claim_boundary')}
        else:r=verify_report(a.report)
        print(json.dumps(r,ensure_ascii=False));return 0
    except Exception as e:print(json.dumps({'status':'error','error':str(e)},ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
