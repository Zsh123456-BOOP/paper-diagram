"""Public local-only command line interface."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .qa import inspect_svg, render_preview


def convert(args):
    from .vectorize import vectorize_image
    source = args.input.resolve()
    if not source.is_file():
        raise ValueError(f'Input does not exist: {source}')
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    svg, pptx, png = [output / (stem + ext) for ext in ('.svg', '.pptx', '.png')]
    report_path = output / (stem + '.conversion.json')
    manifest_copy = output / (stem + '.text.json')
    targets = [svg, report_path]
    if args.format == 'both': targets.append(pptx)
    if args.preview: targets.append(png)
    if args.text_manifest: targets.append(manifest_copy)
    if source in targets:
        raise ValueError('Output must not replace the input file')
    if not args.overwrite:
        existing = [str(p) for p in targets if p.exists()]
        if existing:
            raise ValueError('Output already exists; choose a new directory or pass --overwrite: ' + ', '.join(existing))
    started = time.perf_counter()
    report = {'version': __version__, 'network_requests': 0, 'input': str(source),
              'preset': args.preset, 'text_mode': 'paths', 'outputs': {'svg': str(svg)}}
    with tempfile.TemporaryDirectory(prefix='cell-local-') as temp:
        temp = Path(temp)
        if source.suffix.lower() == '.svg':
            if args.text_manifest:
                raise ValueError('For SVG input, restore text before export; the image text mask option does not apply')
            inspect_svg(source)
            shutil.copyfile(source, svg)
            report['text_mode'] = 'existing_svg'
        else:
            trace_input = source
            if args.text_manifest:
                from .text import prepare_text_image, restore_text
                trace_input = temp / 'cleaned.png'
                report['text_preparation'] = prepare_text_image(source, args.text_manifest, trace_input)
                report['text_preparation'].pop('cleaned_path', None)
            raw = temp / 'raw.svg'
            report['vectorization'] = vectorize_image(trace_input, raw, preset=args.preset)
            report['vectorization'].pop('input_path', None)
            report['vectorization'].pop('output_svg', None)
            if args.text_manifest:
                report['text_restoration'] = restore_text(raw, args.text_manifest, svg)
                shutil.copyfile(args.text_manifest, manifest_copy)
                report['text_mode'] = 'reviewed_live_text_plus_remaining_paths'
                report['outputs']['text_manifest'] = str(manifest_copy)
            else:
                shutil.copyfile(raw, svg)
        report['svg'] = inspect_svg(svg)
        if args.format == 'both':
            from .export import export_svg_to_pptx
            report['pptx'] = export_svg_to_pptx(svg, pptx)
            report['outputs']['pptx'] = str(pptx)
        if args.preview:
            report['preview'] = render_preview(svg, png, source if source.suffix.lower() != '.svg' else None)
            report['outputs']['preview'] = str(png)
    report['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local image → vector SVG / editable PPTX. No account or API key.')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('convert', help='Trace a bitmap, or export an existing SVG')
    p.add_argument('input', type=Path)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--preset', choices=['faithful', 'balanced'], default='faithful')
    p.add_argument('--format', choices=['both', 'svg'], default='both')
    p.add_argument('--text-manifest', type=Path, help='Reviewed pixel-coordinate text manifest; never auto-accepted OCR')
    p.add_argument('--preview', action='store_true', help='Render SVG and measure pixel differences (requires preview extra / Cairo)')
    p.add_argument('--overwrite', action='store_true', help='Replace matching generated outputs')
    p.set_defaults(handler=convert)
    p = commands.add_parser('ocr-draft', help='Optional local Tesseract draft; review before use')
    p.add_argument('input', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--lang', default='eng')
    def draft(args):
        from .text import generate_ocr_draft
        if args.output.exists(): raise ValueError('OCR draft output already exists')
        print(json.dumps(generate_ocr_draft(args.input, args.output, lang=args.lang), ensure_ascii=False, indent=2))
        return 0
    p.set_defaults(handler=draft)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'cell-local: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
