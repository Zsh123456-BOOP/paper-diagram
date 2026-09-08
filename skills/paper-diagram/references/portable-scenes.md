# Portable, Agent-authored scenes

Use this route when editing units matter: cell/value pairs, modules, formulas,
arrows, surfaces or continuous strands. Interpretation happens in the Agent's
current session. These scripts contain no image-understanding model or paid API.

## Install and move

From a source checkout:

```sh
python install_skill.py --copy --destination /your/skills-directory
```

Move the resulting whole `paper-diagram` folder to another host. It includes the
MIT source and an Artifact Tool authored blank PPTX. Installation refuses to
replace an existing skill. No API key is required.

For a minimal scene environment, using Python 3.10 or later:

```sh
python -m venv /your/skills-directory/paper-diagram/runtime/.venv
# Activate this venv using the target system's normal command.
python -m pip install 'fonttools==4.61.1' 'Pillow>=10,<13'
python /your/skills-directory/paper-diagram/scripts/run.py scene scene.json --output result.pptx
```

`scene.json` and the SVG named by its relative `geometry` field travel together.
Measured scenes export with fonttools alone. For legacy `convert` tracing,
install the full package with `pip install <skill>/runtime`. Optional centerline
experiments additionally need the `structure` extras. No Adobe, Office, Node,
external binary or platform-specific font path is required for scene export.
Matching text appearance requires the chosen fonts on the viewing system.
Proprietary fonts are not bundled.

## Author with the helper

Add `<skill>/runtime/src` (copied skill) or `<checkout>/src` (source installation)
to Python's import path and import `Scene` from `cell_local.scene`.
Supply `fonts={family: {regular: local_font_path, bold: ..., italic: ...}}`.
Use fonts that exist on the current host. Pillow measures text and records
metrics in the scene; font file paths do not enter the portable manifest.

```python
from cell_local.scene import Scene
s = Scene('example', 400, 200, fonts=fonts)
with s.group('matrix-r1-c1'):
    s.poly([(50,30),(90,50),(50,70),(10,50)], '#AAE3BF', '#000000', 1)
    s.centered_text('2.3', 50, 50, 20)
with s.group('relationship'):
    s.line([(100,50),(150,50)], arrow=True, dash=[6,3])
s.models.append({'type':'cell','row':1,'column':1,'value':'2.3'})
s.save('example', source='user-reference.png')
```

The helper supports named groups, rectangles, ellipses, polygons, cubic paths,
single-object dashed lines and triangle arrow ends. Text supports font,
baseline, anchor, bold/italic and separate sub/superscript objects. SVG text and
native PPTX text remain inside their semantic groups. Groups can move together
and ungroup. Native lines are not attached smart connectors.

The Agent may instead author SVG directly. Export deliberately supports a
limited SVG subset. Masks, raster images, use-elements, filters and transformed
decorated lines are rejected rather than silently flattened. For an existing
text base, `experiments/svg_scene_to_pptx.py` remains available.

## Record methods and check edits

- Preserve visible values as source strings. Never recalculate a displayed
  matrix or normalize an unusual label without an explicit request.
- Name logical components. Use one face per cell, one value per text object,
  and a cell group for common movement. Preserve source topology.
- Photos can remain named raster assets in an explicitly mixed route, or
  become appearance traces in an all-vector route. This exporter supports the
  latter. Record their methods in `assets`. A same-color compound path may
  contain many disconnected contours; it is not a semantic photo object.
- Agent-drawn strands and knots are approximate geometry. Retain centerlines
  and width parameters; disclose inferred depth and hidden sections.
- Inspect a render of the saved PPTX. Count geometry, live text, groups, image
  assets and stroke-only paths separately. Test a meaningful edit such as
  recoloring one matrix cell or moving its face with its number on a copy.
  High pixel similarity alone is not editability.

The blank template is infrastructure generated with Artifact Tool, not a
journal cover. Font files, source photos, credentials and binaries are not part
of this skill. Scene generation can use the current Agent's judgment and visual
revisions; an automatic one-click image-to-semantic conversion is not claimed.

For render probes, glyph centering, gradient strokes and explicit renderer calibration,
read [object-aware QA](render-qa.md).
