"""Object-aware alignment and render checks; coordinates stay in source pixels.

These checks require reviewed object bindings. They do not infer source semantics
or turn a similarity score into proof of scientific correctness.
"""
import math

def ink_box(text):
    if text.get('wordart'):
        x,y,w,h=text['frame'];return [x,y,x+w,y+h]
    if 'ink_bbox' not in text:
        raise ValueError('Measure this text with the selected font before alignment')
    x=text['x']-{'middle':.5,'end':1}.get(text.get('anchor'),0)*text['advance']
    l,t,r,b=text['ink_bbox']
    return [x+l,text['baseline']+t,x+r,text['baseline']+b]

def block_box(texts):
    if not texts:raise ValueError('A label block must contain text')
    boxes=[ink_box(t) for t in texts]
    return [min(q[0] for q in boxes),min(q[1] for q in boxes),max(q[2] for q in boxes),max(q[3] for q in boxes)]

def center_error(box,target):
    return [(box[i]+box[i+2])/2-target[i] for i in (0,1)]

def center_block(texts,target,*,target_id=None):
    """Move a compound label as one unit, retaining relative subscript positions."""
    if len(target)!=2 or not all(math.isfinite(v) for v in target):raise ValueError('Invalid center target')
    if any(t.get('wordart') for t in texts):raise ValueError('Do not recenter fitted wordmarks as ordinary labels')
    dx,dy=center_error(block_box(texts),target)
    for t in texts:
        t['x']-=dx;t['baseline']-=dy
        t['alignment']={'mode':'ink-center','target':list(target),'target_id':target_id,'block_ids':[q['id'] for q in texts]}
    return [-dx,-dy]

def calibrate_block(texts,observed_box,*,renderer):
    """Store an explicit PPTX-only render correction; never warp the SVG.

    observed_box must come from a rendered probe of these exact text runs.
    Recheck after export and whenever the renderer or installed fonts change.
    """
    if not renderer:raise ValueError('Name the renderer used for calibration')
    expected=block_box(texts);dx,dy=center_error(observed_box,[(expected[0]+expected[2])/2,(expected[1]+expected[3])/2])
    for t in texts:
        prev=t.get('pptx_offset',[0,0]);t['pptx_offset']=[prev[0]-dx,prev[1]-dy]
        t['render_calibration']={'renderer':renderer,'method':'isolated-label-ink-bounds','residual_before':[dx,dy]}
    return [-dx,-dy]

def color_ink_box(image,color,roi,*,pixels_per_unit=1,tolerance=8):
    """Measure a uniquely colored diagnostic label, excluding unrelated text.

    Pixel-edge bounding box at the recorded resolution. This is not an optical
    center or a centroid weighted by glyph darkness. Returns None for no ink.
    """
    import numpy as np
    if pixels_per_unit<=0:raise ValueError('Render scale must be positive')
    x0,y0,x1,y1=[round(v*pixels_per_unit) for v in roi]
    x0=max(0,x0);y0=max(0,y0);x1=min(image.width,x1);y1=min(image.height,y1)
    rgb=[int(color.lstrip('#')[i:i+2],16) for i in (0,2,4)]
    a=np.asarray(image.convert('RGB'))[y0:y1,x0:x1].astype(int)
    if not a.size:return None
    yy,xx=np.where(abs(a-rgb).max(axis=-1)<tolerance)
    if not len(xx):return None
    return [float(v)/pixels_per_unit for v in (x0+xx.min(),y0+yy.min(),x0+xx.max()+1,y0+yy.max()+1)]

def arrow_contract(expected_ids,exported_ids):
    """Count equality alone can hide a missing arrow plus a duplicate."""
    from collections import Counter
    expected,exported=Counter(expected_ids),Counter(exported_ids)
    return {'missing':list((expected-exported).elements()),'unexpected':list((exported-expected).elements()),'passed':expected==exported}

def visibility_ratio(isolated_mask,visible_mask):
    """Compare the same head ROI without moving or registering either render."""
    import numpy as np
    a=np.asarray(isolated_mask,dtype=bool);b=np.asarray(visible_mask,dtype=bool)
    if a.shape!=b.shape:raise ValueError('Visibility probes need identical canvases')
    total=int(a.sum());seen=int((a&b).sum())
    return {'isolated_pixels':total,'visible_pixels':seen,'ratio':seen/total if total else None}
