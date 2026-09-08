"""Replace one explicitly selected PPTX picture with grouped native curves.

Experimental companion to trace_centerlines.py. Accepts only its plain,
untransformed, round-stroked SVG subset. Preserves unrelated slide objects,
text, z-order and media. Does not author a presentation from scratch.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import math
import posixpath
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/cell_local/_vendor/cell_su7'))
from prepare_geometry_cache import collect_atoms, parse_canvas

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
SVG = 'http://www.w3.org/2000/svg'
for prefix, uri in [('a', A), ('p', P), ('r', R)]:
    ET.register_namespace(prefix, uri)


def child(parent, tag, **attrs):
    prefix, name = tag.split(':')
    return ET.SubElement(parent, '{' + {'a': A, 'p': P}[prefix] + '}' + name,
                         {key: str(value) for key, value in attrs.items()})


def solid(parent, color, opacity):
    rgb = child(child(parent, 'a:solidFill'), 'a:srgbClr',
                val=''.join(f'{round(c):02X}' for c in color))
    if opacity < 100:
        child(rgb, 'a:alpha', val=round(opacity * 1000))


def replace_picture(source, svg_path, output, picture_index, expected_frame, slide_number=1):
    if output.exists() or output.with_suffix('.json').exists():
        raise ValueError('Choose unused output and report paths')
    root = ET.parse(svg_path).getroot()
    allowed = {'svg', 'g', 'path'}
    for elem in root.iter():
        if elem.tag.removeprefix('{' + SVG + '}') not in allowed:
            raise ValueError('Only plain SVG groups and paths are supported')
        if any(k in elem.attrib for k in ('transform', 'style', 'filter', 'clip-path', 'mask')):
            raise ValueError('Expand transforms/styles/filters before export')
        if elem.tag == '{' + SVG + '}path':
            if elem.get('fill') != 'none' or elem.get('stroke-linecap') != 'round' or elem.get('stroke-linejoin') != 'round':
                raise ValueError('This experimental exporter requires round, unfilled strokes')
    canvas = parse_canvas(root)
    if len(canvas) == 4:
        vx, vy, width, height = canvas
    else:
        width, height = canvas
        vx = vy = 0
    if vx or vy or width <= 0 or height <= 0:
        raise ValueError('Use a positive canvas starting at 0,0')
    atoms = collect_atoms(root)
    if not atoms or any(atom['kind'] != 'path' for atom in atoms):
        raise ValueError('No path-only geometry found')
    by_id = {atom['sourceId']: atom for atom in atoms}
    if len(by_id) != len(atoms):
        raise ValueError('Every path needs a unique id')
    with zipfile.ZipFile(source) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP entries')
        entries = {name: z.read(name) for name in z.namelist()}
    slide_name = f'ppt/slides/slide{slide_number}.xml'
    slide = ET.fromstring(entries[slide_name])
    tree = slide.find('{' + P + '}cSld/{' + P + '}spTree')
    pictures = tree.findall('{' + P + '}pic')
    if not 0 <= picture_index < len(pictures):
        raise ValueError('Picture index outside the top-level picture list')
    picture = pictures[picture_index]
    xf = picture.find('{' + P + '}spPr/{' + A + '}xfrm')
    if any(xf.get(k) not in (None, '0') for k in ('rot', 'flipH', 'flipV')) or picture.find('.//{' + A + '}srcRect') is not None:
        raise ValueError('Cropped, rotated or flipped pictures are unsupported')
    off = xf.find('{' + A + '}off'); ext = xf.find('{' + A + '}ext')
    frame = [int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))]
    if any(abs(actual - round(expected * 9525)) > 1 for actual, expected in zip(frame, expected_frame)):
        raise ValueError(f'Picture frame did not match the reviewed frame: {frame}')
    sx, sy = frame[2] / width, frame[3] / height
    if not math.isclose(sx, sy, rel_tol=1e-5):
        raise ValueError('SVG aspect ratio must match the picture')
    before_text = [t.text for t in slide.iter('{' + A + '}t')]
    next_id = max(int(n.get('id', 0)) for n in slide.iter('{' + P + '}cNvPr')) + 1
    stats = {'native_curves': 0, 'native_groups': 0}

    def new_id():
        nonlocal next_id
        value = next_id; next_id += 1
        return value

    def group(parent, name, top=False):
        group = child(parent, 'p:grpSp'); nv = child(group, 'p:nvGrpSpPr')
        child(nv, 'p:cNvPr', id=new_id(), name=name)
        child(nv, 'p:cNvGrpSpPr'); child(nv, 'p:nvPr')
        transform = child(child(group, 'p:grpSpPr'), 'a:xfrm')
        x, y, w, h = frame if top else [0, 0, round(width * 10000), round(height * 10000)]
        child(transform, 'a:off', x=x, y=y); child(transform, 'a:ext', cx=w, cy=h)
        child(transform, 'a:chOff', x=0, y=0)
        child(transform, 'a:chExt', cx=round(width * 10000), cy=round(height * 10000))
        stats['native_groups'] += 1
        return group

    def add_curve(parent, atom):
        parts = atom['paintParts']
        if len(parts) != 1 or parts[0]['filled'] or not parts[0]['stroked']:
            raise ValueError('Expected one unfilled stroke per path')
        part = parts[0]
        coords = [q for sub in atom['subpaths'] for pt in sub['points'] for q in (pt['a'], pt['l'], pt['r'])]
        x = min(q[0] for q in coords); y = min(q[1] for q in coords)
        w = max(.001, max(q[0] for q in coords) - x)
        h = max(.001, max(q[1] for q in coords) - y)
        def xy(q): return {'x': round((q[0] - x) * 10000), 'y': round((q[1] - y) * 10000)}
        sp = child(parent, 'p:sp'); nv = child(sp, 'p:nvSpPr')
        child(nv, 'p:cNvPr', id=new_id(), name=atom['sourceId'])
        child(nv, 'p:cNvSpPr'); child(nv, 'p:nvPr')
        pr = child(sp, 'p:spPr'); transform = child(pr, 'a:xfrm')
        child(transform, 'a:off', x=round(x * 10000), y=round(y * 10000))
        child(transform, 'a:ext', cx=round(w * 10000), cy=round(h * 10000))
        geom = child(pr, 'a:custGeom')
        for tag in ('avLst', 'gdLst', 'ahLst', 'cxnLst'): child(geom, 'a:' + tag)
        child(geom, 'a:rect', l='0', t='0', r='r', b='b')
        path = child(child(geom, 'a:pathLst'), 'a:path', w=round(w * 10000), h=round(h * 10000), fill='none', stroke='1', extrusionOk='0')
        for sub in atom['subpaths']:
            pts = sub['points']; child(child(path, 'a:moveTo'), 'a:pt', **xy(pts[0]['a']))
            pairs = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if sub['closed'] else [])
            for prev, cur in pairs:
                if prev['r'] == prev['a'] and cur['l'] == cur['a']:
                    child(child(path, 'a:lnTo'), 'a:pt', **xy(cur['a']))
                else:
                    cubic = child(path, 'a:cubicBezTo')
                    for point in (prev['r'], cur['l'], cur['a']): child(cubic, 'a:pt', **xy(point))
            if sub['closed']: child(path, 'a:close')
        child(pr, 'a:noFill')
        line = child(pr, 'a:ln', w=round(part['strokeWidth'] * sx), cap='rnd')
        solid(line, part['strokeColor'], part['opacity']); child(line, 'a:round')
        stats['native_curves'] += 1

    detached = ET.Element('temporary')
    top = group(detached, 'Microscopy — experimental observed curves', top=True)
    def emit(elem, parent):
        if elem.tag == '{' + SVG + '}path':
            add_curve(parent, by_id[elem.get('id')]); return
        children = list(elem)
        target = group(parent, elem.get('id', 'Curve group')) if elem is not root and len(children) > 1 else parent
        for item in children: emit(item, target)
    emit(root, top)
    index = list(tree).index(picture); tree.remove(picture); tree.insert(index, top)
    assert before_text == [t.text for t in slide.iter('{' + A + '}t')]
    entries[slide_name] = ET.tostring(slide, encoding='utf-8', xml_declaration=True)

    # Remove the selected image relationship only if nothing else uses it.
    blip = picture.find('.//{' + A + '}blip')
    rid = blip.get('{' + R + '}embed')
    rels_name = f'ppt/slides/_rels/slide{slide_number}.xml.rels'
    rels = ET.fromstring(entries[rels_name]); removed_media = None
    still_used = any(rid in elem.attrib.values() for elem in slide.iter())
    if not still_used:
        for rel in list(rels):
            if rel.get('Id') == rid:
                removed_media = posixpath.normpath(posixpath.join('ppt/slides', rel.get('Target'))).lstrip('/')
                rels.remove(rel)
        entries[rels_name] = ET.tostring(rels, encoding='utf-8', xml_declaration=True)
    if removed_media:
        referenced = False
        for name, data in entries.items():
            if not name.endswith('.rels'): continue
            owner_dir = str(PurePosixPath(name).parent.parent)
            for rel in ET.fromstring(data):
                resolved = posixpath.normpath(posixpath.join(owner_dir, rel.get('Target', ''))).lstrip('/')
                if resolved == removed_media: referenced = True
        if not referenced: entries.pop(removed_media, None)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items(): z.writestr(name, data)
    stats.update({'text_runs_preserved': len(before_text), 'replaced_picture_index': picture_index,
                  'slide_xml_bytes': len(entries[slide_name]),
                  'embedded_media': [name for name in entries if name.startswith('ppt/media/')],
                  'limitations': 'Experimental visual branches; not recovered biological connectivity. Original texture is not retained.'})
    output.with_suffix('.json').write_text(json.dumps(stats, indent=2))
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path); parser.add_argument('svg', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--picture-index', type=int, required=True)
    parser.add_argument('--frame', nargs=4, type=float, required=True, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    parser.add_argument('--slide', type=int, default=1)
    args = parser.parse_args()
    if not all(math.isfinite(v) for v in args.frame) or min(args.frame[2:]) <= 0:
        parser.error('Frame values must be finite, with positive dimensions')
    if args.output.suffix.lower() != '.pptx': parser.error('Output must be .pptx')
    print(json.dumps(replace_picture(args.input, args.svg, args.output, args.picture_index, args.frame, args.slide)))


if __name__ == '__main__':
    main()
