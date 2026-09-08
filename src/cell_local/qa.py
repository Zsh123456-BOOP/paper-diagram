"""Structural checks and optional local preview; no calls to external services."""
from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ET


def inspect_svg(path) -> dict:
    root = ET.parse(path).getroot()
    if root.tag.rsplit('}', 1)[-1] != 'svg':
        raise ValueError('Expected an SVG root')
    permitted = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line',
                 'polyline', 'polygon', 'text', 'title', 'desc', 'metadata'}
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] not in permitted:
            raise ValueError('Unsupported SVG element; use plain geometry and text without images, styles or external resources')
        if any(k.rsplit('}', 1)[-1] == 'href' for k in node.attrib):
            raise ValueError('External or referenced content is not supported')
        if any(k.lower().startswith('on') for k in node.attrib):
            raise ValueError('SVG event handlers are not supported')
        if any('url(' in v.lower() for v in node.attrib.values()):
            raise ValueError('SVG URL paints and external resources are not supported')
    raw = root.get('viewBox')
    if raw:
        box = [float(v) for v in raw.replace(',', ' ').split()]
    else:
        box = [0, 0, float(root.get('width', '0')), float(root.get('height', '0'))]
    if len(box) != 4 or not all(math.isfinite(v) for v in box) or min(box[2:]) <= 0:
        raise ValueError('SVG requires a positive finite canvas')
    tags = [n.tag.rsplit('}', 1)[-1] for n in root.iter()]
    return {'canvas': box, 'path_count': tags.count('path'),
            'live_text_count': tags.count('text'), 'embedded_images': tags.count('image')}


def render_preview(svg, png, reference=None) -> dict:
    info = inspect_svg(svg)
    try:
        import cairosvg
    except (ImportError, OSError) as exc:
        raise RuntimeError('Preview needs the preview extra and the Cairo system library; conversion itself does not. ' + str(exc)) from exc
    width, height = [max(1, round(v)) for v in info['canvas'][2:]]
    cairosvg.svg2png(bytestring=Path(svg).read_bytes(), write_to=str(png),
                     output_width=width, output_height=height)
    result = {'preview': str(Path(png).resolve()), 'width': width, 'height': height}
    if reference:
        import numpy as np
        from PIL import Image, ImageOps
        def pixels(path):
            image = ImageOps.exif_transpose(Image.open(path)).convert('RGBA')
            bg = Image.new('RGBA', image.size, 'white')
            return np.asarray(Image.alpha_composite(bg, image).convert('RGB')).astype(float)
        a, b = pixels(reference), pixels(png)
        if a.shape != b.shape:
            raise ValueError('Reference and preview dimensions differ')
        error = abs(a - b)
        result['comparison'] = {
            'mean_absolute_rgb_error_0_255': round(float(error.mean()), 4),
            'fraction_pixels_any_channel_error_gt_32': round(float((error.max(axis=2) > 32).mean()), 6),
            'note': 'Pixel measurements are diagnostics, not semantic accuracy scores.'}
    return result
