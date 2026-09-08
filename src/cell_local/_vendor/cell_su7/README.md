# Vendored Cell SU7 offline renderer

Source: https://github.com/yrui-cmd/cell_su7

Commit: `518dbc2ff929fa5500221dc2c5ffb94a7f60a657`

The following files are copied without modification from
`plugins/cell_su7/skills/cell_su7/scripts/` at that commit:

- `prepare_geometry_cache.py`
- `canvas_clip.py`
- `run_cell_ppt_ooxml.py`

The upstream MIT license is preserved in `LICENSE`. Only the offline SVG
parser and editable OOXML backend are vendored. No paid API adapter,
credential handler, dependency synchronizer, or watermark code is included.

The parent `export.py` provides a local-only function wrapper and checks the
saved file before publishing it. It does not invoke hidden-geometry culling,
so input paths and their paint order are retained.
