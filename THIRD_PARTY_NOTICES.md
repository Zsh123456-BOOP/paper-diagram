# Third-party notices

## Cell SU7 offline SVG to PowerPoint backend

Source repository: https://github.com/yrui-cmd/cell_su7

Exact upstream commit: [`518dbc2ff929fa5500221dc2c5ffb94a7f60a657`](https://github.com/yrui-cmd/cell_su7/tree/518dbc2ff929fa5500221dc2c5ffb94a7f60a657)

Files copied unchanged from `plugins/cell_su7/skills/cell_su7/scripts/` into
`src/cell_local/_vendor/cell_su7/`:

- `prepare_geometry_cache.py`: SVG parsing, geometry and paint-order cache.
- `canvas_clip.py`: validation of a redundant full-canvas clip.
- `run_cell_ppt_ooxml.py`: native editable PowerPoint shapes and text.

Local integration: `src/cell_local/export.py` calls these offline scripts in
the current Python runtime and validates the package before saving the final
file. SVG groups are flattened while paint order and nonzero compound
contours are preserved. Existing text is editable, but text metrics are
approximate. The renderer rejects evenodd fills rather than silently changing
their holes. It also rejects unsupported masks, gradients and dashed strokes.
Stroke caps/joins and very thin stroke widths have upstream fidelity limits;
filled-outline paths are preferred. PowerPoint shapes are not semantic graph
nodes or smart connectors.

No upstream web-service client, API key storage, auto-update/synchronization,
or watermark-processing code is redistributed here. Dependencies such as
`python-pptx` and `fonttools` retain their own licenses; they are installed as
dependencies rather than copied into this source tree.

### Upstream license

MIT License

Copyright (c) 2026 yrui-cmd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
