# Object-aware render QA

Use this when labels drift, arrows disappear, or smooth paint develops seams.
Separate three questions: reference → reconstructed scene, scene → exported
PPTX, and PPTX → target application's rendering. A good export score does not
prove that the reconstructed scene faithfully reproduces the reference.

## Authoring constraints

- Keep source pixels as the common coordinate system; avoid repeated scale and
  rounding. Convert to slide units only at export. Record any deliberate layout
  adaptation. Do not align each ROI independently to hide its displacement.
- A label inside a node is a bound text block. Use `Scene.centered_text` or
  `scene_qa.center_block` on the union of all its runs, including subscripts.
  Center actual glyph bounds rather than advance width or `baseline + k*size`.
  Choose the target explicitly: bounding-box center, polygon centroid, or a
  reviewed optical offset. External captions keep their reference baseline.
- Text and its container belong to the same semantic group. A matrix face/value
  pair stays separate from neighboring cells even when colors match.
- Compute arrow tips from the final node boundary after layout changes. Review
  drawing order, head size and local contrast. Native lines are currently not
  smart attached connectors. Degenerate arrow paths must fail export.
- Use continuous multi-stop gradients on continuous centerlines rather than
  stacking hard-ended fixed-opacity segments. The exporter supports axis-aligned
  object-box gradient fills/strokes. Native PowerPoint supports the tested
  gradient stroke; the bundled LibreOffice renderer used in this project drops
  it. Treat a missing stroke as a failed renderer check, not proof the SVG lacks
  the object. Use PowerPoint export for that preview. Do not rasterize silently.

## Text and arrow probes

Add reviewed bindings to `scene.json`:

```json
{"qa":{"alignment_constraints":[
  {"id":"cell-1","shape_id":"cell-face","texts":["value"],
   "box":[10,20,90,60],"target":[50,40]}
]}}
```

Each text ID belongs to at most one binding. `box` encloses the label's container;
`target` is the chosen visible-ink center. Do not infer every label from proximity.

From a source checkout or `<skill>/runtime`:

```sh
python experiments/inspect_scene_render.py prepare scene.json result.pptx --output probes
# Open/export probes/text.pptx, arrows-only.pptx and arrows-visible.pptx
# to PDFs with matching names in probes/pdf using the target application.
python experiments/inspect_scene_render.py measure probes --pdf-dir probes/pdf --renderer 'PowerPoint version / platform'
```

`prepare` makes diagnostic copies, preserving group transforms. Unique colors
isolate a compound label from neighboring labels, which prevents a nearby number
or asterisk contaminating its measured box. Arrow probes paint line ends magenta,
once alone and once in their original stacking context. The report matches arrow
IDs one-to-one and flags poor head visibility in the same endpoint ROI.
`measure` uses 4 rendered pixels per source pixel (0.25 px sampling), checks the
canvas, and reports each label's dx/dy and each head's visible-pixel ratio.
The default 0.5 px label threshold and 0.6 head ratio are review flags, not quality
certificates. Overlapping heads and very thin strokes require a visual check.
A passed ID contract cannot detect an arrow never authored from the source.

Dependencies for measurement: Pillow, NumPy and pypdfium2; preparation/export
needs fonttools. Install the `qa` extra or these optional packages only when
render measurement is needed. Actual PDF export requires a separate renderer.

Use `scene_qa.calibrate_block` only with a probe of the exact text runs. It records
`pptx_offset` and renderer provenance without changing SVG geometry. In a measured 57-label example, LibreOffice residuals were at most 0.25 source px
while PowerPoint reached 1.375 px on the same file. Do not transfer a calibration
claim between renderers. Re-export
and remeasure; invalidate calibration when fonts, text, size or renderer change.
Do not report the same calibration input as a successful verification render.

## Reference checks and limits

Review named reference anchors (cell corners, endpoints, label baselines) and
source content independently. A useful extension is a per-region edge-distance
map and gradient profile; neither is currently an automatic semantic recognizer.
For a reference/scene comparison, report the region, pixel scale, registration,
font substitution, and intentional differences. Whole-page pixel MSE is dominated
by background and anti-aliasing; it can miss a single lost scientific relation.

Always inspect the final saved PPTX visually. Check for text overflow, clipped
strokes, intersections, layer order and meaningful editability. A photographic
appearance trace still differs from semantic reconstruction after passing these
checks. Cross-platform zero-pixel drift is not promised.

## Coverage and connectivity gates

A head can be fully visible while pointing into empty space. Use the independent
source contract in [faithful reconstruction](faithful-reconstruction.md) to check
edge presence, text content and endpoint positions in the actual SVG. Keep it
separate from export/render probes. Every source relationship must have an output
edge ID or a documented unresolved exception. Compute endpoints from final ports;
when the application does not support attached connectors, preserve bindings in
the builder and recompute on any layout change.

Cover every in-container text block with a binding or a specific reviewed
exception; external captions require source baseline/box comparison rather than
forced centering. Report groups and text-run counts separately. Sparse probe
coverage cannot establish whole-page alignment. Check path direction, continuous
shaft visibility and intended source/target as well as head visibility visually.
A final file change invalidates any affected probe results.


## Original-image evidence is required for reference fidelity

Follow [reference evidence](reference-evidence.md) to freeze the reference before
building and compare actual final render pixels. Contract checks report internal
consistency only, even when all authored text and arrows are covered. Never use
`101/101` to mean all original labels were found unless completeness was separately
checked against the source. Inspect flagged tiles and all named source regions.
Store review findings separately; drawing helpers cannot mark their output reviewed.
Hash verification detects changed/stale files but does not establish that a claimed
render really came from PowerPoint; retain the actual renderer command/result too.
