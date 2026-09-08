"""Experimental visual centerlines for isolated bright filament artwork.

Requires numpy, Pillow, scipy and scikit-image. No model or network calls.
This extracts image-plane branches; crossings do not establish biological
connectivity. Endpoints are never connected across an unobserved gap.
"""
from pathlib import Path
import argparse,json,hashlib,time,math,re
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, map_coordinates
from skimage.filters import sato
from skimage.morphology import skeletonize, remove_small_objects
from skimage.measure import approximate_polygon
import xml.etree.ElementTree as ET
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)

def graph_chains(skeleton):
    """Visit each undirected skeleton edge once; retain loops and junctions."""
    pixels=set(map(tuple,np.argwhere(skeleton)))
    neighbors={}
    for y,x in sorted(pixels):
        out=[]
        for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            q=(y+dy,x+dx)
            if q not in pixels:continue
            # Do not introduce a diagonal shortcut around a present orthogonal corner.
            if dy and dx and ((y+dy,x) in pixels or (y,x+dx) in pixels):continue
            out.append(q)
        neighbors[(y,x)]=out
    used=set();chains=[]
    def edge(a,b):return (a,b) if a<b else (b,a)
    def walk(start,next_point):
        chain=[start,next_point];used.add(edge(start,next_point));previous=start;current=next_point
        while len(neighbors[current])==2 and current!=start:
            nxt=next(x for x in neighbors[current] if x!=previous)
            if edge(current,nxt) in used:break
            used.add(edge(current,nxt));chain.append(nxt);previous,current=current,nxt
        return np.array(chain,dtype=float)
    for p in sorted(pixels):
        if len(neighbors[p])==2:continue
        for q in neighbors[p]:
            if edge(p,q) not in used:chains.append(walk(p,q))
    for p in sorted(pixels):
        for q in neighbors[p]:
            if edge(p,q) not in used:chains.append(walk(p,q))
    return chains, {'skeleton_pixels':len(pixels),'junction_pixels':sum(len(x)>2 for x in neighbors.values()),
                    'endpoint_pixels':sum(len(x)==1 for x in neighbors.values()),'visited_edges':len(used)}

def curve(points):
    """Bounded Catmull-Rom cubic interpolation of a simplified observed chain."""
    p=np.asarray(points);f=lambda v:format(float(v),'.3f').rstrip('0').rstrip('.')
    xy=lambda q:f(q[0])+','+f(q[1])
    result=['M'+xy(p[0])]
    for i in range(len(p)-1):
        a=p[max(0,i-1)];b=p[i];c=p[i+1];d=p[min(len(p)-1,i+2)]
        # A quarter-strength tangent limits overshoot around short corners.
        cp1=b+(c-a)/8;cp2=c-(d-b)/8
        result.append('C'+xy(cp1)+' '+xy(cp2)+' '+xy(c))
    return ' '.join(result)

def join_straight_chains(chains):
    """Join clear geometric continuations only at an already shared node.

    No endpoint snapping and no gap filling. Ambiguous best-angle matches stay
    separate. This changes editing units, not the set of observed graph edges.
    """
    ends={}
    for i,c in enumerate(chains):
        if len(c)<3 or np.array_equal(c[0],c[-1]):continue
        for end in (0,1):
            pts=c if end==0 else c[::-1];v=pts[min(4,len(pts)-1)]-pts[0];n=np.linalg.norm(v)
            if n:ends.setdefault(tuple(pts[0]),[]).append((i,end,v/n))
    links={}
    for node,items in ends.items():
        choices=[]
        for a in range(len(items)):
            for b in range(a+1,len(items)):
                if items[a][0]==items[b][0]:continue
                score=float(items[a][2]@items[b][2])
                if score<-.88:choices.append((score,items[a][:2],items[b][:2]))
        choices.sort()
        for score,a,b in choices:
            if a in links or b in links:continue
            rivals=[s for s,u,v in choices if (u,v)!=(a,b) and (a in (u,v) or b in (u,v))]
            if rivals and min(rivals)-score<.06:continue
            links[a]=b;links[b]=a
    visited=set();result=[]
    starts=[(i,e) for i in range(len(chains)) for e in (0,1) if (i,e) not in links]
    starts += [(i,0) for i in range(len(chains))]
    for i,e in starts:
        if i in visited:continue
        pieces=[]
        while i not in visited:
            visited.add(i);c=chains[i] if e==0 else chains[i][::-1]
            pieces.append(c if not pieces else c[1:])
            if (i,1-e) not in links:break
            i,e=links[(i,1-e)]
        result.append(np.concatenate(pieces))
    return result,len(links)//2

def trace(image, threshold=.006, scale=2, minimum_length=1.5, tolerance=.18,
          background='#000000', minimum_chroma=5):
    rgba=np.array(image.convert('RGBA'));h,w=rgba.shape[:2]
    bg=np.array([int(background[i:i+2],16) for i in (1,3,5)],dtype=float)
    rgb=rgba[:,:,:3].astype(float);alpha=rgba[:,:,3:4]/255
    rgb=rgb*alpha+bg*(1-alpha)
    enlarged=np.array(Image.fromarray(rgb.astype('uint8')).resize((w*scale,h*scale),Image.Resampling.BICUBIC)).astype(float)
    intensity=np.maximum(0,enlarged@np.array([.2126,.7152,.0722])-float(bg@np.array([.2126,.7152,.0722])))/255
    chroma=np.ptp(enlarged,axis=2)
    response=sato(intensity,sigmas=[.4*scale,.7*scale],black_ridges=False)
    color_mask=(chroma>minimum_chroma) if minimum_chroma else np.ones(chroma.shape,dtype=bool)
    mask=(response>threshold)&color_mask&(intensity>.018)
    mask=remove_small_objects(mask,min_size=max(4,round(minimum_length*scale)),connectivity=2)
    skeleton=skeletonize(mask);dist=distance_transform_edt(mask)
    chains,stats=graph_chains(skeleton)
    stats['raw_graph_chains']=len(chains)
    chains,stats['joins_at_existing_nodes']=join_straight_chains(chains)
    root=ET.Element('{'+NS+'}svg',width=str(w),height=str(h),viewBox=f'0 0 {w} {h}')
    items=[]
    for c in chains:
        length=np.linalg.norm(np.diff(c,axis=0),axis=1).sum()/scale
        if length<minimum_length:continue
        # Keep a branch intact as a group; paint segments allow local color changes.
        pts=(c[:,::-1]+.5)/scale-.5
        stride=max(3,round(9*scale));segments=[]
        for start in range(0,len(c)-1,stride):
            sample=c[start:min(len(c),start+stride+1)]
            orig=pts[start:min(len(c),start+stride+1)]
            small=approximate_polygon(orig,tolerance=tolerance)
            if len(small)<2:continue
            # Use source centerline colors, never a synthetic global palette.
            vals=np.array([map_coordinates(enlarged[:,:,k],sample.T,order=1) for k in range(3)]).T
            color=np.clip(np.mean(vals,axis=0),0,255)
            width=float(np.clip(np.median(dist[sample[:,0].astype(int),sample[:,1].astype(int)])*1.25/scale,.4,1.45))
            segments.append({'d':curve(small),'color':color.tolist(),'width':width,'points':small.tolist()})
        if segments:items.append({'id':f'branch-{len(items)+1:05d}','length_px':round(length,2),'segments':segments})
    # The dim support stroke suggests line softness without a raster/filter.
    for kind,weight,width_scale in [('support',.46,1.85),('core',1,1.0)]:
        layer=ET.SubElement(root,'{'+NS+'}g',id=kind)
        for item in items:
            group=ET.SubElement(layer,'{'+NS+'}g',id=item['id']+'-'+kind)
            for j,s in enumerate(item['segments']):
                width=s['width']*width_scale
                color=np.clip(bg+(np.array(s['color'])-bg)*weight,0,255).astype(int)
                ET.SubElement(group,'{'+NS+'}path',id=f"{item['id']}-{j}-{kind}",d=s['d'],fill='none',
                  stroke='#'+''.join(f'{v:02x}' for v in color),**{'stroke-width':f'{width:.3f}','stroke-linecap':'round','stroke-linejoin':'round'})
    stats.update({'branches':len(items),'paint_paths':sum(len(x['segments'])*2 for x in items),
                  'total_observed_length_px':round(sum(x['length_px'] for x in items),2),'threshold':threshold,
                  'scale':scale,'minimum_length':minimum_length,'tolerance':tolerance,
                  'background':background,'minimum_chroma':minimum_chroma,
                  'method':'Sato ridge response, skeleton graph, observed branch curves',
                  'limitations':['Not a recovered biological fiber graph.','No inference behind lettering or across gaps.',
                    'Fine texture and diffuse light are omitted; isolated speckles may be lost.'],
                  'embedded_images':0,'network_requests':0})
    return root,items,stats

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--threshold',type=float,default=.006);p.add_argument('--scale',type=int,default=2)
    p.add_argument('--minimum-length',type=float,default=1.5);p.add_argument('--tolerance',type=float,default=.18)
    p.add_argument('--background',default='#000000',help='Background for compositing alpha: #RRGGBB')
    p.add_argument('--minimum-chroma',type=float,default=5,help='RGB range must exceed this threshold; 0 disables the color filter')
    p.add_argument('--roi',nargs=4,type=int,metavar=('LEFT','TOP','RIGHT','BOTTOM'))
    a=p.parse_args()
    if a.output.suffix.lower()!='.svg':p.error('Output must have .svg suffix')
    if any(q.exists() for q in (a.output,a.output.with_suffix('.json'),a.output.with_suffix('.branches.json'))):
        p.error('Choose new output and companion report paths; existing files are preserved')
    if not 0<a.threshold<1 or a.scale not in (1,2,3,4):p.error('Invalid threshold or scale')
    if not all(math.isfinite(v) and v>=0 for v in (a.minimum_length,a.tolerance,a.minimum_chroma)) or a.minimum_chroma>255:
        p.error('Length, tolerance and chroma must be finite nonnegative values; chroma <= 255')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',a.background):p.error('Background must be #RRGGBB')
    im=Image.open(a.input).convert('RGBA')
    if a.roi:
        l,t,r,b=a.roi
        if not 0<=l<r<=im.width or not 0<=t<b<=im.height:p.error('ROI must lie inside input')
        im=im.crop(a.roi)
    if im.width*im.height*a.scale*a.scale>8_000_000:p.error('Limit working image to 8 megapixels')
    start=time.perf_counter();root,items,report=trace(im,a.threshold,a.scale,a.minimum_length,a.tolerance,a.background,a.minimum_chroma)
    a.output.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(a.output,encoding='utf-8',xml_declaration=True)
    report.update({'elapsed_seconds':round(time.perf_counter()-start,3),'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'roi':a.roi,'canvas':[im.width,im.height]})
    a.output.with_suffix('.json').write_text(json.dumps(report,indent=2))
    a.output.with_suffix('.branches.json').write_text(json.dumps(items,separators=(',',':')))
    print(json.dumps(report))
if __name__=='__main__':main()
