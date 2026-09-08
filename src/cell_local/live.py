"""Compile reviewed Scene geometry into readable PowerPoint VBA drawing steps.

Compilation does not operate Office. The generated module creates a NEW native
presentation in PowerPoint, using AddShape, AddTextbox and BuildFreeform. It
never imports a finished slide, reveals hidden objects, or substitutes pictures.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path


def number(value):
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError('Expected a finite coordinate')
    return format(float(value), '.8f').rstrip('0').rstrip('.') or '0'


def vb_string(value):
    """ASCII .bas source, preserving quotes, Unicode and UTF-16 surrogate pairs."""
    parts, run = [], ''
    encoded = value.encode('utf-16-le')
    for unit in [int.from_bytes(encoded[i:i+2], 'little') for i in range(0, len(encoded), 2)]:
        if 32 <= unit < 127:
            run += chr(unit)
        else:
            if run:
                parts.append('"' + run.replace('"', '""') + '"'); run = ''
            parts.append(f'ChrW({unit if unit < 32768 else unit - 65536})')
    if run or not parts:
        parts.append('"' + run.replace('"', '""') + '"')
    return ' & '.join(parts)


def color(value):
    if value == 'none':
        return None
    aliases = {'black': '#000000', 'white': '#FFFFFF'}
    value = aliases.get(value, value)
    if re.fullmatch(r'#[0-9a-fA-F]{3}', value):
        value = '#' + ''.join(c*2 for c in value[1:])
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('Live mode supports solid RGB paints only: ' + value)
    return [int(value[i:i+2], 16) for i in (1, 3, 5)]


def path_segments(d):
    pen = RecordingPen(); parse_path(d, pen)
    segments, start, current, closed = [], None, None, False
    for op, points in pen.value:
        if op == 'moveTo':
            if start is not None:
                raise ValueError('Live freeforms support one contour; use the normal exporter for compound paths')
            start = current = points[0]
        elif op == 'lineTo':
            segments.append(['line', *points[0]]); current = points[0]
        elif op == 'curveTo':
            segments.append(['cubic', *[v for p in points for v in p]]); current = points[-1]
        elif op == 'qCurveTo':
            control, end = points
            c1 = [current[i]+2/3*(control[i]-current[i]) for i in (0, 1)]
            c2 = [end[i]+2/3*(control[i]-end[i]) for i in (0, 1)]
            segments.append(['cubic', *c1, *c2, *end]); current = end
        elif op == 'closePath':
            if current != start:
                segments.append(['line', *start])
            current = start; closed = True
        elif op != 'endPath':
            raise ValueError('Unsupported path operation: ' + op)
    if start is None or not segments or all(all(v == start[i % 2] for i, v in enumerate(s[1:])) for s in segments):
        raise ValueError('Live path has no drawable geometry')
    for v in [*start, *[v for s in segments for v in s[1:]]]:
        number(v)
    return list(start), segments, closed


def compile_scene(scene_path):
    scene_path = Path(scene_path)
    manifest = json.loads(scene_path.read_text(encoding='utf-8'))
    geometry = scene_path.parent / manifest['geometry']
    root = ET.parse(geometry).getroot()
    width, height = manifest['width'], manifest['height']
    scale = manifest.get('scale', 1) * .75
    if any(float(number(v)) <= 0 for v in (width, height, scale)):
        raise ValueError('Canvas and scale must be positive')
    if max(width*scale, height*scale) > 4032:
        raise ValueError('PowerPoint canvas exceeds 56 inches')
    if [float(x) for x in root.get('viewBox', '').split()] != [0, 0, width, height]:
        raise ValueError('SVG canvas differs from the scene')
    texts = {t['id']: t for t in manifest['texts']}
    if len(texts) != len(manifest['texts']):
        raise ValueError('Duplicate text IDs')
    events, ids, seen_text = [], set(), set()
    defaults = {'fill': '#000000', 'stroke': 'none', 'stroke-width': '1'}

    def visit(el, inherited, alpha=1):
        tag = el.tag.rsplit('}', 1)[-1]
        if tag == 'defs':
            return None
        for attribute in ('transform', 'style', 'mask', 'clip-path', 'filter', 'display', 'visibility'):
            if attribute in el.attrib:
                raise ValueError(f'Live mode does not support {attribute}: {el.get("id", tag)}')
        alpha *= float(el.get('opacity', 1))
        if not 0 <= alpha <= 1:
            raise ValueError('Invalid opacity')
        styles = {**inherited, **{k: v for k, v in el.attrib.items() if k in
                  ['fill', 'stroke', 'stroke-width', 'fill-opacity', 'stroke-opacity', 'stroke-dasharray']}}
        if el.get('fill-rule', 'nonzero') != 'nonzero':
            raise ValueError('Live mode does not support evenodd fills')
        eid = el.get('id')
        if tag != 'svg':
            if not eid or eid in ids:
                raise ValueError('Every visible object and group needs a unique ID')
            ids.add(eid)
        if tag in ('svg', 'g'):
            members = [key for ch in el if (key := visit(ch, styles, alpha)) is not None]
            if tag == 'svg' or not members:
                return None
            events.append(dict(kind='group', id=eid, members=members))
            return eid
        event = dict(id=eid)
        if tag == 'text':
            t = texts.get(eid)
            if not t or t['content'] != ''.join(el.itertext()):
                raise ValueError('Live text differs from the reviewed manifest: ' + eid)
            if t.get('wordart') or t.get('rotation') or t.get('pptx_offset'):
                raise ValueError('Live mode does not yet support fitted/rotated/calibrated text: ' + eid)
            if len(el) or alpha != 1 or float(styles.get('fill-opacity', 1)) != 1:
                raise ValueError('Live text needs separate opaque runs, without tspan children')
            if color(t['fill']) is None:
                raise ValueError('Live text requires a visible solid fill')
            seen_text.add(eid)
            advance, ascent, descent = (t[k] for k in ('advance', 'ascent', 'descent'))
            anchor = t.get('anchor', 'start')
            if anchor not in ('start', 'middle', 'end'):
                raise ValueError('Unsupported text anchor')
            x = t['x'] - (advance/2 if anchor == 'middle' else advance if anchor == 'end' else 0)
            event.update(kind='text', content=t['content'], font=t['font'], size=t['size'],
                         bold=bool(t.get('bold')), italic=bool(t.get('italic')),
                         bounds=[x, t['baseline']-ascent, advance+3, ascent+descent+2],
                         fill=color(t['fill']), alpha=alpha)
            if t['size'] <= 0 or advance < 0 or ascent < 0 or descent < 0:
                raise ValueError('Invalid text metrics')
        else:
            fill, stroke = color(styles['fill']), color(styles['stroke'])
            sw = float(styles['stroke-width'])
            if not math.isfinite(sw) or sw < 0:
                raise ValueError('Invalid line width')
            fa = alpha*float(styles.get('fill-opacity', 1)); sa = alpha*float(styles.get('stroke-opacity', 1))
            if not all(0 <= v <= 1 for v in (fa, sa)):
                raise ValueError('Invalid paint opacity')
            dash = styles.get('stroke-dasharray', 'none')
            # Native msoLineDash is not an exact arbitrary SVG dash pattern.
            if dash != 'none':
                raise ValueError('Live mode does not yet support exact dash patterns')
            if el.get('marker-start') or el.get('marker-mid'):
                raise ValueError('Unsupported SVG marker')
            arrow = el.get('data-line-end')
            if el.get('marker-end') and arrow != 'triangle' or arrow not in (None, 'triangle'):
                raise ValueError('Live mode needs an explicit triangular arrow mapping')
            event.update(fill=fill, stroke=stroke, width=sw, fill_alpha=fa, stroke_alpha=sa, arrow=bool(arrow))
            if tag == 'rect':
                x, y, w, h = [float(el.get(k, 0)) for k in ('x', 'y', 'width', 'height')]
                if min(w, h) <= 0:
                    raise ValueError('Rectangle dimensions must be positive')
                rx = min(float(el.get('rx', el.get('ry', 0))), w/2)
                ry = min(float(el.get('ry', el.get('rx', 0))), h/2)
                if min(rx, ry) < 0:
                    raise ValueError('Invalid corner radius')
                if rx and ry:
                    k = .5522847498307936
                    d = (f'M{x+rx},{y} H{x+w-rx} C{x+w-rx+k*rx},{y} {x+w},{y+ry-k*ry} {x+w},{y+ry} '
                         f'V{y+h-ry} C{x+w},{y+h-ry+k*ry} {x+w-rx+k*rx},{y+h} {x+w-rx},{y+h} '
                         f'H{x+rx} C{x+rx-k*rx},{y+h} {x},{y+h-ry+k*ry} {x},{y+h-ry} '
                         f'V{y+ry} C{x},{y+ry-k*ry} {x+rx-k*rx},{y} {x+rx},{y} Z')
                    start, segments, closed = path_segments(d)
                    event.update(kind='path', start=start, segments=segments, closed=closed)
                else:
                    event.update(kind='rect', bounds=[x, y, w, h])
            elif tag in ('circle', 'ellipse'):
                x, y = float(el.get('cx', 0)), float(el.get('cy', 0))
                rx, ry = (float(el.get('r', 0)),)*2 if tag == 'circle' else (float(el.get('rx', 0)), float(el.get('ry', 0)))
                if min(rx, ry) <= 0:
                    raise ValueError('Ellipse radii must be positive')
                event.update(kind='ellipse', bounds=[x-rx, y-ry, 2*rx, 2*ry])
            elif tag in ('path', 'polygon', 'polyline', 'line'):
                if tag == 'path':
                    d = el.get('d', '')
                elif tag == 'line':
                    d = f'M{el.get("x1",0)},{el.get("y1",0)} L{el.get("x2",0)},{el.get("y2",0)}'
                else:
                    values = [float(v) for v in re.split(r'[\s,]+', el.get('points', '').strip())]
                    if len(values) < 4 or len(values) % 2:
                        raise ValueError('Invalid polygon points')
                    d = 'M' + ' L'.join(f'{x},{y}' for x, y in zip(values[::2], values[1::2])) + (' Z' if tag == 'polygon' else '')
                start, segments, closed = path_segments(d)
                event.update(kind='path', start=start, segments=segments, closed=closed)
            else:
                raise ValueError('Unsupported live SVG element: ' + tag)
            if arrow and (event['kind'] != 'path' or event['closed'] or stroke is None or sw <= 0):
                raise ValueError('Arrow needs an open stroked path')
        for key in ('bounds', 'start'):
            for value in event.get(key, []):
                number(value)
        events.append(event)
        return eid

    visit(root, defaults)
    if seen_text != set(texts):
        raise ValueError('Manifest text is missing from the SVG')
    return dict(schema='paper-diagram.live/1', mode='native-powerpoint-creation',
                width=width, height=height, points_per_unit=scale,
                source_sha256=hashlib.sha256(scene_path.read_bytes()).hexdigest(),
                geometry_sha256=hashlib.sha256(geometry.read_bytes()).hexdigest(), events=events)


def vba_module(plan, interval=.2):
    if not 0 <= interval <= 10:
        raise ValueError('Interval must be between 0 and 10 seconds')
    factor = plan['points_per_unit']
    n = lambda v: number(v*factor)
    rgb = lambda c: 'RGB(' + ', '.join(str(v) for v in c) + ')'
    lines = ['Attribute VB_Name = "PaperDiagramLive"', 'Option Explicit', '',
             "' Generated local native drawing code. No network, shell, or file overwrite.",
             'Private pdDeck As Presentation', 'Private pdSlide As Slide',
             'Private pdIndex As Long', 'Private pdPlaying As Boolean', 'Private pdFailed As Boolean',
             f'Private Const PD_COUNT As Long = {len(plan["events"])}',
             f'Private Const PD_INTERVAL As Double = {number(interval)}', '',
             'Public Sub PaperDiagramStart()',
             '    If pdPlaying Then Exit Sub',
             '    Set pdDeck = Presentations.Add(msoTrue)',
             f'    pdDeck.PageSetup.SlideWidth = {n(plan["width"])}',
             f'    pdDeck.PageSetup.SlideHeight = {n(plan["height"])}',
             '    Set pdSlide = pdDeck.Slides.Add(1, ppLayoutBlank)',
             '    pdDeck.Windows(1).Activate', '    pdDeck.Windows(1).ViewType = ppViewNormal',
             '    pdDeck.Windows(1).View.GotoSlide 1',
             '    pdIndex = 0', '    pdFailed = False', '    pdPlaying = False',
             '    pdSlide.Tags.Add "PD_MODE", "native-powerpoint-creation"',
             f'    pdSlide.Tags.Add "PD_SOURCE_SHA256", "{plan["source_sha256"]}"',
             f'    pdSlide.Tags.Add "PD_GEOMETRY_SHA256", "{plan["geometry_sha256"]}"',
             '    DoEvents', 'End Sub', '',
             'Public Sub PaperDiagramDraw()',
             '    If pdPlaying Then Exit Sub',
             '    PaperDiagramStart', '    PaperDiagramPlay', 'End Sub', '',
             'Public Sub PaperDiagramNext()',
             '    If pdSlide Is Nothing Then PaperDiagramStart',
             '    If pdFailed Then Err.Raise vbObjectError + 500, , "Previous step failed. Run PaperDiagramStart for a fresh document."',
             '    If pdIndex >= PD_COUNT Then Exit Sub', '    On Error GoTo Failed',
             '    Select Case pdIndex',
             *[f'        Case {i}: PDStep{i:04d}' for i in range(len(plan['events']))],
             '    End Select', '    pdIndex = pdIndex + 1',
             '    pdSlide.Tags.Add "PD_COMPLETED_STEPS", CStr(pdIndex)',
             '    pdSlide.Tags.Add "PD_TOTAL_STEPS", CStr(PD_COUNT)',
             '    Debug.Print "paper-diagram step=" & pdIndex & " time=" & Format$(Timer, "0.000")',
             '    DoEvents', '    Exit Sub', 'Failed:',
             '    pdPlaying = False', '    pdFailed = True',
             '    MsgBox "Drawing stopped at step " & (pdIndex + 1) & ": " & Err.Description, vbExclamation',
             'End Sub', '',
             'Public Sub PaperDiagramPlay()',
             '    Dim started As Double, elapsed As Double',
             '    If pdPlaying Then Exit Sub',
             '    If pdSlide Is Nothing Then PaperDiagramStart',
             '    If pdFailed Then Exit Sub',
             '    pdPlaying = True',
             '    Do While pdIndex < PD_COUNT And pdPlaying And Not pdFailed',
             '        PaperDiagramNext', '        started = Timer',
             '        Do', '            DoEvents', '            elapsed = Timer - started',
             '            If elapsed < 0 Then elapsed = elapsed + 86400',
             '        Loop While elapsed < PD_INTERVAL And pdPlaying And Not pdFailed',
             '    Loop', '    pdPlaying = False', 'End Sub', '',
             'Public Sub PaperDiagramPause()', '    pdPlaying = False', 'End Sub', '']
    for i, event in enumerate(plan['events']):
        lines += [f'Private Sub PDStep{i:04d}()', '    Dim s As Shape, ff As FreeformBuilder']
        kind = event['kind']
        if kind == 'group':
            members = event['members']
            if len(members) == 1:
                lines += [f'    Set s = pdSlide.Shapes({vb_string(members[0])})']
            else:
                lines += [f'    Dim members(0 To {len(members)-1}) As Variant']
                lines += [f'    members({j}) = {vb_string(key)}' for j, key in enumerate(members)]
                lines += ['    Set s = pdSlide.Shapes.Range(members).Group']
        elif kind in ('rect', 'ellipse'):
            shape_type = 'msoShapeRectangle' if kind == 'rect' else 'msoShapeOval'
            lines += [f'    Set s = pdSlide.Shapes.AddShape({shape_type}, ' + ', '.join(n(v) for v in event['bounds']) + ')']
        elif kind == 'text':
            lines += ['    Set s = pdSlide.Shapes.AddTextbox(msoTextOrientationHorizontal, ' + ', '.join(n(v) for v in event['bounds']) + ')',
                      '    s.Fill.Visible = msoFalse', '    s.Line.Visible = msoFalse',
                      '    With s.TextFrame', '        .MarginLeft = 0', '        .MarginRight = 0',
                      '        .MarginTop = 0', '        .MarginBottom = 0',
                      '        .WordWrap = msoFalse', '        .AutoSize = ppAutoSizeNone',
                      '        .VerticalAnchor = msoAnchorTop', '    End With',
                      '    With s.TextFrame.TextRange', '        .Text = ""']
            for start in range(0, len(event['content']), 40):
                lines += [f'        .Text = .Text & {vb_string(event["content"][start:start+40])}']
            lines += [f'        .Font.Name = {vb_string(event["font"])}', f'        .Font.Size = {n(event["size"])}',
                      f'        .Font.Bold = {"msoTrue" if event["bold"] else "msoFalse"}',
                      f'        .Font.Italic = {"msoTrue" if event["italic"] else "msoFalse"}',
                      f'        .Font.Color.RGB = {rgb(event["fill"])}',
                      '        .ParagraphFormat.Bullet.Visible = msoFalse',
                      '        .ParagraphFormat.Alignment = ppAlignLeft',
                      '        .ParagraphFormat.SpaceBefore = 0', '        .ParagraphFormat.SpaceAfter = 0', '    End With']
        elif kind == 'path':
            lines += ['    Set ff = pdSlide.Shapes.BuildFreeform(msoEditingCorner, ' + ', '.join(n(v) for v in event['start']) + ')']
            for segment in event['segments']:
                segment_type = 'msoSegmentLine, msoEditingAuto' if segment[0] == 'line' else 'msoSegmentCurve, msoEditingCorner'
                lines += ['    ff.AddNodes ' + segment_type + ', ' + ', '.join(n(v) for v in segment[1:])]
            lines += ['    Set s = ff.ConvertToShape']
        if kind not in ('text', 'group'):
            if event['fill'] is None:
                lines += ['    s.Fill.Visible = msoFalse']
            else:
                lines += ['    s.Fill.Visible = msoTrue', '    s.Fill.Solid',
                          f'    s.Fill.ForeColor.RGB = {rgb(event["fill"])}',
                          f'    s.Fill.Transparency = {number(1-event["fill_alpha"])}']
            if event['stroke'] is None or event['width'] == 0:
                lines += ['    s.Line.Visible = msoFalse']
            else:
                lines += ['    s.Line.Visible = msoTrue', f'    s.Line.ForeColor.RGB = {rgb(event["stroke"])}',
                          f'    s.Line.Weight = {n(event["width"])}',
                          f'    s.Line.Transparency = {number(1-event["stroke_alpha"])}']
                if event['arrow']:
                    lines += ['    s.Line.EndArrowheadStyle = msoArrowheadTriangle']
        lines += [f'    s.Name = {vb_string(event["id"])}',
                  f'    s.Tags.Add "PD_STEP", "{i+1}"',
                  f'    s.Tags.Add "PD_OBJECT", {vb_string(event["id"])}',
                  'End Sub', '']
    if max(map(len, lines)) > 1000:
        raise ValueError('VBA line too long; shorten object IDs or font names')
    return '\r\n'.join(lines) + '\r\n'


def export_live(scene, output_dir, interval=.2):
    plan = compile_scene(scene)
    code = vba_module(plan, interval)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('Choose a new live output directory')
    output_dir.mkdir(parents=True)
    (output_dir/'PaperDiagramLive.bas').write_bytes(code.encode('ascii'))
    (output_dir/'live-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return dict(module=str(output_dir/'PaperDiagramLive.bas'), events=len(plan['events']),
                shapes=sum(e['kind'] != 'group' for e in plan['events']),
                groups=sum(e['kind'] == 'group' and len(e['members']) > 1 for e in plan['events']),
                mode=plan['mode'], interval_seconds=interval)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('scene', type=Path)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--interval', type=float, default=.2)
    args = p.parse_args()
    print(json.dumps(export_live(args.scene, args.output_dir, args.interval)))


if __name__ == '__main__':
    main()
