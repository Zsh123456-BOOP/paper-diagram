# Direct SVG reconstruction

Use for diagrams with repeated nodes, labels, panels and relationships. Reconstruct
what is visible; do not infer an unseen architecture or invent scientific values.

Read [faithful reconstruction](faithful-reconstruction.md) first for a supplied reference.

1. Record canvas, nodes, labels, states, arrow directions and source-to-target
   relationships. Follow each endpoint independently at crossings. Preserve
   ambiguity for review rather than making up an edge.
2. Measure in source pixel coordinates. Choose a shared palette, font family,
   line widths and repeated components. Vary their data and positions.
3. Use named groups and stable geometry IDs. Keep ordinary text live and formulas
   as separate text runs for sub/superscripts. Place edges behind nodes where the
   reference does. Use outlines only for genuinely unresolved lettering.
4. Prefer the [portable scene route](portable-scenes.md) for grouped output. It
   retains native text, groups, untransformed dashed paths, triangular line ends,
   rectangles and ellipses. Do not expand every dash or merge unrelated cells.
   The supported subset and backend limitations are documented in that reference.
5. When numerical chart data is unavailable, preserve visible plot coordinates
   without claiming that an approximation recovers measured values. Do not simplify icons by default. Record unavoidable approximations, hidden
   geometry assumptions and font substitutions, and inspect their source crops.
6. Inspect the SVG and the saved PPTX. Check labels, states, connectivity, clipping,
   layers and a meaningful edit. Connectors do not automatically follow moved
   nodes. A reconstruction does not recover the author's original design file.

The older `scripts/run.py convert existing.svg --output-dir <new-directory>`
route remains available but flattens groups. It requires arrowheads as geometry
and expanded dash segments; use the scene route when those limitations conflict
with the user's editing needs. Do not apply the legacy restrictions to the newer
scene exporter or rasterize an available vector source.
