"""Experimental local curve tracing; does not change the stable cell-local CLI.

Requires Pillow and a separately installed VTracer 1.0.0-alpha.4 executable.
No network, credentials, generative image model, or embedded raster output.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess, tempfile, time
import xml.etree.ElementTree as ET
from PIL import Image, ImageOps

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
PRESETS = {
    'detail': {'scale': 2, 'speckle': 0, 'gradient': 8, 'simplify': .2},
    'compact': {'scale': 2, 'speckle': 2, 'gradient': 8, 'simplify': .2},
    'flat': {'scale': 2, 'speckle': 4, 'gradient': 0, 'simplify': .4, 'max_colors': 27},
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--vtracer', required=True, type=Path)
    p.add_argument('--preset', choices=PRESETS, default='detail')
    p.add_argument('--palette-file', type=Path, help='Optional measured palette; useful for controlled comparisons')
    p.add_argument('--preview', action='store_true', help='Requires CairoSVG and the Cairo system library')
    args = p.parse_args()
    source, output, binary = args.input.resolve(), args.output.resolve(), args.vtracer.resolve()
    metadata = output.with_suffix('.json')
    preview = output.with_suffix('.png')
    if output.suffix.lower() != '.svg': p.error('Output must be SVG')
    targets = [output, metadata] + ([preview] if args.preview else [])
    if any(t.exists() for t in targets): p.error('Choose new output paths; existing files are preserved')
    if args.palette_file and not args.palette_file.is_file(): p.error('Palette file not found')
    version = subprocess.run([str(binary), '--version'], check=True, capture_output=True, text=True).stdout.strip()
    if '1.0.0-alpha.4' not in version: p.error('This prototype was validated with VTracer 1.0.0-alpha.4')
    start = time.perf_counter()
    with Image.open(source) as opened:
        if opened.format not in ('PNG', 'JPEG', 'WEBP'): p.error('Supported inputs: PNG, JPEG, WebP')
        if getattr(opened, 'n_frames', 1) != 1: p.error('Use a single-frame image')
        image = ImageOps.exif_transpose(opened).convert('RGBA')
        image = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image).convert('RGB')
    width, height = image.size
    config = dict(PRESETS[args.preset])
    scale = config['scale']
    if width * height * scale * scale > 16_000_000:
        p.error('This bounded prototype supports up to 4 megapixel inputs at 2x fitting resolution')
    options = ['--clustering','color-cluster','--hierarchical','stacked','--mode','spline',
               '--color-precision','8','--gradient-step',str(config['gradient']),
               '--filter-speckle',str(config['speckle']),'--simplify',str(config['simplify']),
               '--path-precision','3','--optimize','1']
    if args.palette_file: options += ['--palette-file', str(args.palette_file.resolve())]
    elif config.get('max_colors'): options += ['--max-colors',str(config['max_colors'])]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='local-curve-', dir=output.parent) as temp:
        temp = Path(temp)
        image.resize((width*scale,height*scale), Image.Resampling.BICUBIC).save(temp/'input.png')
        subprocess.run([str(binary),str(temp/'input.png'),str(temp/'raw.svg'),*options],
                       check=True,capture_output=True,text=True,timeout=120)
        root = ET.parse(temp/'raw.svg').getroot()
        permitted = {'svg','g','path','rect','circle','ellipse','polygon','polyline','line','title','desc','metadata'}
        for node in root.iter():
            if node.tag.rsplit('}',1)[-1] not in permitted: raise ValueError('Unexpected vector element')
            if any(k.rsplit('}',1)[-1]=='href' or k.lower().startswith('on') for k in node.attrib):
                raise ValueError('Referenced or active content is not permitted')
        root.set('width',str(width));root.set('height',str(height));root.set('viewBox',f'0 0 {width} {height}')
        group = ET.Element(f'{{{NS}}}g',{'transform':f'scale({1/scale})'})
        for child in list(root): root.remove(child); group.append(child)
        root.append(group)
        paths = [n for n in root.iter() if n.tag.rsplit('}',1)[-1]=='path']
        for i,node in enumerate(paths): node.set('id',f'curve-{i+1:06d}')
        ET.ElementTree(root).write(temp/'final.svg',encoding='utf-8',xml_declaration=True)
        (temp/'final.svg').replace(output)
    if args.preview:
        import cairosvg
        cairosvg.svg2png(bytestring=output.read_bytes(),write_to=str(preview),output_width=width,output_height=height)
    report = {'engine':version,'preset':args.preset,'parameters':options,'scale':scale,
              'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
              'canvas':[width,height],'paths':len(paths),'embedded_images':0,'editable_text_nodes':0,
              'output_bytes':output.stat().st_size,'elapsed_seconds':round(time.perf_counter()-start,3),
              'network_requests':0,'limitations':['Experimental outline tracing, not semantic reconstruction.',
                  'No guarantee of exact fiber connectivity or hidden structures.',
                  'Input lettering becomes outlines; detail mode can create many small paths.']}
    metadata.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__ == '__main__':
    main()
