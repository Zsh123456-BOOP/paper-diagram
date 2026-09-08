"""Small agent-authored scene builder: named geometry, live text and provenance.

Coordinates and baselines use source-image pixels. Fonts are supplied by the
caller, never downloaded. This module does not recognize or invent diagram data.
"""
from contextlib import contextmanager
from pathlib import Path
import copy
import json
import math
import re
import xml.etree.ElementTree as E
from PIL import ImageFont

NS = 'http://www.w3.org/2000/svg'
E.register_namespace('', NS)

def f(v):
    if not math.isfinite(float(v)):
        raise ValueError('Scene coordinates must be finite')
    return f'{float(v):.3f}'.rstrip('0').rstrip('.')

def xy(p):
    return ','.join(f(v) for v in p)

class Scene:
    def __init__(self, name, width, height, *, fonts, background='#FFFFFF'):
        if min(width, height) <= 0:
            raise ValueError('Canvas dimensions must be positive')
        self.name, self.w, self.h = name, width, height
        self.fonts, self.texts, self.models, self.assets = fonts, [], [], []
        self.i, self.ids, self.markers = 0, set(), set()
        self.root = E.Element('{'+NS+'}svg', width=f(width), height=f(height), viewBox=f'0 0 {f(width)} {f(height)}')
        self.defs = E.SubElement(self.root, '{'+NS+'}defs')
        self.g = self.root
        with self.group('Background'):
            self.rect(0, 0, width, height, background, name='canvas')

    def ident(self, name=None):
        self.i += 1
        out = re.sub(r'[^A-Za-z0-9_.-]+', '-', name or f'{self.name}-{self.i}').strip('-')
        if out in self.ids:
            raise ValueError('Duplicate scene ID: '+out)
        self.ids.add(out)
        return out

    def el(self, tag, *, name=None, **attrs):
        eid = self.ident(name)
        return E.SubElement(self.g, '{'+NS+'}'+tag, id=eid, **{k:str(v) for k,v in attrs.items()})

    @contextmanager
    def group(self, name):
        previous = self.g
        self.g = self.el('g', name=name, **{'data-name':name})
        try:
            yield self.g
        finally:
            self.g = previous

    def path(self, d, fill='none', stroke='none', sw=1, *, name=None, dash=None, arrow=False, opacity=1):
        e = self.el('path', name=name, d=d, fill=fill, stroke=stroke, **{'stroke-width':f(sw), 'stroke-linecap':'round', 'stroke-linejoin':'round', 'opacity':f(opacity)})
        if dash:
            e.set('stroke-dasharray', ' '.join(f(x) for x in dash))
        if arrow:
            self.arrow_end(e, stroke)
        return e

    def poly(self, points, fill='none', stroke='none', sw=1, *, name=None):
        return self.el('polygon', name=name, points=' '.join(xy(p) for p in points), fill=fill, stroke=stroke, **{'stroke-width':f(sw), 'stroke-linejoin':'round'})

    def rect(self, x, y, w, h, fill='none', stroke='none', sw=1, *, radius=0, name=None):
        attrs = {'rx':f(radius), 'ry':f(radius)} if radius else {}
        return self.el('rect', name=name, x=f(x), y=f(y), width=f(w), height=f(h), fill=fill, stroke=stroke, **{'stroke-width':f(sw), **attrs})

    def ellipse(self, x, y, rx, ry=None, fill='none', stroke='none', sw=1, *, name=None):
        return self.el('ellipse', name=name, cx=f(x), cy=f(y), rx=f(rx), ry=f(rx if ry is None else ry), fill=fill, stroke=stroke, **{'stroke-width':f(sw)})

    def line(self, points, stroke='#000000', sw=1, *, arrow=False, dash=None, name=None):
        return self.path('M'+' L'.join(xy(p) for p in points), stroke=stroke, sw=sw, arrow=arrow, dash=dash, name=name)

    def arrow_end(self, elem, color):
        mid = 'arrow-'+color.replace('#','')
        if mid not in self.markers:
            self.markers.add(mid)
            m = E.SubElement(self.defs, '{'+NS+'}marker', id=mid, viewBox='0 0 5 4', refX='5', refY='2', markerWidth='5', markerHeight='4', orient='auto', markerUnits='strokeWidth')
            E.SubElement(m, '{'+NS+'}path', d='M0,0 L5,2 L0,4 Z', fill=color)
        elem.set('marker-end', 'url(#'+mid+')')
        elem.set('data-line-end', 'triangle')

    def text(self, content, x, baseline, size=18, *, font='Times New Roman', fill='#000000', bold=False, italic=False, anchor='start', name=None, sub=None, sup=None):
        variant = 'bolditalic' if bold and italic else 'bold' if bold else 'italic' if italic else 'regular'
        spec = self.fonts[font]
        file = spec.get(variant, spec['regular'])
        measured = ImageFont.truetype(str(file), round(size*100))
        ascent, descent = measured.getmetrics()
        advance = measured.getlength(content)/100
        ink_bbox = [v/100 for v in measured.getbbox(content, anchor='ls')]
        e = self.el('text', name=name, x=f(x), y=f(baseline), fill=fill, **{'font-family':font, 'font-size':f(size), 'font-weight':'bold' if bold else 'normal', 'font-style':'italic' if italic else 'normal', 'text-anchor':anchor})
        e.text = content
        item = dict(id=e.get('id'), content=content, x=x, baseline=baseline, size=size, font=font, fill=fill, bold=bold, italic=italic, anchor=anchor, advance=advance, ascent=ascent/100, descent=descent/100, ink_bbox=ink_bbox, group_id=self.g.get('id'))
        self.texts.append(item)
        end = x-advance/2 if anchor=='middle' else x-advance if anchor=='end' else x
        if sub is not None:
            self.text(str(sub), end+advance, baseline+size*.2, size*.64, font=font, fill=fill, italic=italic)
        if sup is not None:
            self.text(str(sup), end+advance, baseline-size*.45, size*.64, font=font, fill=fill, italic=italic)
        return item

    def centered_text(self, content, cx, cy, size=18, *, target_id=None, **style):
        """Center the visible glyph bounds, not the line box or baseline.

        For a formula with several text runs, center their union as a block.
        External annotations and captions should keep reference baselines.
        """
        if any(k in style for k in ('sub','sup','anchor')):
            raise ValueError('Center a compound formula as a block; do not center its base run alone')
        item=self.text(content,cx,cy,size,anchor='start',**style)
        l,t,r,b=item['ink_bbox'];item['x']=cx-(l+r)/2;item['baseline']=cy-(t+b)/2
        elem=list(self.g)[-1];elem.set('x',f(item['x']));elem.set('y',f(item['baseline']))
        item['alignment']={'mode':'ink-center','target':[cx,cy],'target_id':target_id}
        return item

    def linear_gradient(self, name, stops, *, axis='x'):
        """Continuous native-compatible stroke/fill gradient, with alpha stops."""
        if axis not in ('x','y'):
            raise ValueError('Gradient axis must be x or y')
        if len(stops)<2 or stops[0][0]!=0 or stops[-1][0]!=1 or any(a[0]>=b[0] for a,b in zip(stops,stops[1:])):
            raise ValueError('Stops must strictly increase from 0 to 1')
        if any(not math.isfinite(float(p)) or not 0<=p<=1 or not re.fullmatch(r'#[0-9a-fA-F]{6}',color) or not math.isfinite(float(alpha)) or not 0<=alpha<=1 for p,color,alpha in stops):
            raise ValueError('Invalid gradient stop')
        gid=self.ident(name)
        g=E.SubElement(self.defs,'{'+NS+'}linearGradient',id=gid,x1='0',y1='0',x2='1' if axis=='x' else '0',y2='0' if axis=='x' else '1',gradientUnits='objectBoundingBox')
        for offset,color,alpha in stops:
            E.SubElement(g,'{'+NS+'}stop',offset=f(offset),**{'stop-color':color,'stop-opacity':f(alpha)})
        return 'url(#'+gid+')'

    def import_svg(self, path, x, y, width, height, *, name, provenance):
        source = E.parse(path).getroot()
        w,h = float(source.get('width')), float(source.get('height'))
        with self.group(name):
            holder = self.el('g', transform=f'translate({f(x)} {f(y)}) scale({f(width/w)} {f(height/h)})')
            for ch in source:
                item = copy.deepcopy(ch)
                for e in item.iter():
                    if e.get('id'):
                        e.set('id', self.ident(name+'-'+e.get('id')))
                holder.append(item)
        self.assets.append(dict(name=name, kind='vector-appearance-trace', **provenance))

    def fitted_text(self, content, x, y, width, height, *, font='Times New Roman', fill='#000000', bold=False, name=None):
        """Explicitly fit a wordmark/headline; ordinary labels should use text()."""
        face = self.fonts[font].get('bold' if bold else 'regular', self.fonts[font]['regular'])
        measured = ImageFont.truetype(str(face), 10000)
        left,top,right,bottom = measured.getbbox(content, anchor='ls')
        if right<=left or bottom<=top:
            raise ValueError('Fitted text needs visible glyphs')
        sx,sy = width/((right-left)/100), height/((bottom-top)/100)
        item = self.text(content,0,0,100,font=font,fill=fill,bold=bold,name=name)
        elem = list(self.g)[-1]
        elem.set('transform',f'matrix({f(sx)} 0 0 {f(sy)} {f(x-left/100*sx)} {f(y-top/100*sy)})')
        item.update(wordart=True,frame=[x,y,width,height])
        return item

    def save(self, directory, *, source, notes=''):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        E.ElementTree(self.root).write(directory/'scene.svg', encoding='utf-8', xml_declaration=True)
        j = dict(schema='cell-local.scene/1', name=self.name, width=self.w, height=self.h, scale=1, geometry='scene.svg', texts=self.texts, models=self.models, assets=self.assets, source=source, notes=notes)
        (directory/'scene.json').write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding='utf-8')
        return j
