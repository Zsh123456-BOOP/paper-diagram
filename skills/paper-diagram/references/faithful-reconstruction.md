# Faithful reconstruction from a supplied image

The default request “帮我复刻这张图” means preserve appearance and content while
making meaningful objects editable. User-requested redesigns override this default.
Do not ask the user to specify the decomposition; the Agent performs it.

## Establish the reference before authoring

Save an unchanged reference copy and its actual dimensions. Inspect it at native
size and enlarged around small labels, arrow crossings and irregular shapes.
Build `reference.json` from the reference, not by copying the generated scene.
Record named regions, objects, text and relationships. For a multi-panel figure,
work panel by panel without losing connections across panels.

Freeze this source evidence before drawing using [reference evidence](reference-evidence.md).
Keep observations, output-ID mapping and review results conceptually distinct.
Assigning intended SVG IDs in advance is fine. Appending expected text/boxes/edge
endpoints inside the same `label`, `rect` or `arrow` helper that draws the output
is NOT an independent source contract. The builder may read the snapshot but may
not rewrite it. If measurement needs correction, preserve the old snapshot and
create a new revision with the crop and reason. Hashes detect changes, not honesty.

For each semantic object record its source box, perspective/contour, visible
subparts, style and editing unit. For matrices record corners, row/column counts,
cell colors and literal values. Record ordinary text verbatim with line breaks,
font size/weight and baseline estimates; formulas need grouped runs for fractions,
subscripts, superscripts and the complete scope of radicals. Do not replace a
legible numeral with a question mark or guess a different scientific symbol.
If the reference architecture itself looks wrong, flag it separately; a faithful
copy must not silently substitute an architecture inferred from outside context.

Record edges independently: source object/port or junction, target object/port,
direction, bends, solid/dashed style and layering. At crossings, follow both
lines in enlarged crops; do not infer a junction merely from an intersection.
Do not derive the expected edge list from the final SVG arrow IDs.

## Rebuild without redesigning

Use the original coordinate system throughout. Measure polygon corners and plane
angles; a generic rectangle or prism is not a substitute for a reference wedge.
Preserve the number of visible layers and the relative sizes/weights of labels.
Fit text inside the measured box rather than enlarging the box to fit a default
font. Choose the closest available font and document substitutions.

Use source-derived contour fitting for irregular filled masks and centerlines
for genuine strokes. A named mask may contain many curves while remaining one
editing unit. Do not substitute a few waves, stars or template scribbles for
source handwriting. For photographic material, identify preserved raster assets
explicitly when appropriate; if all-vector output is requested, use an identified
appearance trace and disclose that it does not recover semantic anatomy. Avoid
whole-page raster insertion or unreviewed pixel-region tracing for a diagram.

Keep node/port definitions in the builder. Compute connector endpoints from final
node boundaries; apply a small explicit gap only when visible in the reference.
Moving a node must recompute incident edges. Preserve junction branches and
residual bypasses, not just the existence of arrowheads. Use the existing portable
scene exporter; resolve its runtime relative to the installed skill rather than
hard-coding another machine's project directory.

## Source contract (standard-library checker)

Use `scripts/check_reference.py evidence/reference.json scene.json --snapshot evidence/evidence.json --output contract.json`.
The contract describes observed reference positions and content. Output IDs map
those observations to actual SVG objects. Units are source pixels; box format is
`[x, y, width, height]`. Set tolerances according to source resolution and measured
uncertainty, not to make a failing candidate pass.

```json
{
  "canvas": [200, 100],
  "regions": [{"id":"main", "bbox":[0,0,200,100], "status":"pending"}],
  "objects": [
    {"id":"encoder", "svg_id":"encoder-face", "bbox":[10,20,50,40]},
    {"id":"decoder", "svg_id":"decoder-face", "bbox":[100,20,80,40]}
  ],
  "texts": [{"id":"encoder-label", "svg_ids":["t1"], "content":"Encoder"}],
  "edges": [{"id":"encoder-to-decoder", "svg_id":"edge1",
    "start":{"object":"encoder", "side":"right"},
    "end":{"object":"decoder", "side":"left"}}],
  "tolerance_px": 2,
  "exceptions": []
}
```

Add each actual text object/run to a text entry. `svg_ids` are joined with the
entry's `separator` (default empty); text order is explicit. Use one entry per
formula/run when exact concatenation would be misleading. Compare its visual
layout separately. Nodes may name groups for existence coverage; a requested
bbox check supports untransformed rectangles, circles, ellipses, polygons and
M/L polylines. Complex paths/groups still need visual contour review.

For an edge endpoint, use `object`, `side` (`left/right/top/bottom`), optional
`fraction` along that side (default .5), and explicit `offset: [dx,dy]` when the
reference contains a gap. For nonrectangular ports, reference junctions or curve
endpoints use `point: [x,y]` measured from the reference. The checker compares
these with the actual start/end of the SVG edge. It supports absolute M/L/C/Q
paths, lines and polylines; unsupported transforms/path commands fail the check
instead of receiving a pass. Split other paths or review an explicit exception.

The checker reports missing/extra arrows, uncovered text, wrong strings, node
box shifts and detached endpoints. `exceptions` entries require `kind` (`text`,
`edge`, `object`), `svg_id`, and `reason`; they remain explicit review items. The overall status never becomes `pass`
from this script alone: `contract_status` reports internal consistency and
`visual_fidelity` remains `not_evaluated`. Successful exit means contract checks
completed without errors, not that the image matches the reference.
The checker is NOT an image recognizer and does not certify semantic accuracy.
Review completeness against the reference yourself, including non-arrow lines.

## Visual acceptance and delivery

Render the SVG and the final PPTX at the source aspect ratio. Run the pixel
comparison from [reference evidence](reference-evidence.md), which also checks
full-canvas tiles outside named regions. Produce a same-scale
side-by-side comparison and a 50% reference overlay; use image compositing only
for diagnostic comparison, never to substitute source pixels into the deliverable.
Use one global alignment at most, recorded explicitly. Do not shift individual
regions or stretch the output to conceal geometric displacement.

Inspect every recorded region for typography, perspective, contour, repeated
layers, color, arrow routing and formulas. Write a separate visual review only after
looking at that region in the reference and exact final output; record specific
residual differences and bind the review to the image-evidence report and hashes.
Keep the frozen reference's region status `pending`; never bulk-write `reviewed`
inside a drawing script. Agent-written review statements are not automated proof. Pixel/edge-distance maps may help locate displacement but
cannot establish scientific correctness. Fix discovered errors in the builder,
rerender affected output, and rerun relevant checks. Keep source boxes/content
unchanged unless reinspection proves the original measurement was wrong.

Use render-qa.md for final text bindings and arrowhead visibility as an additional
export check. Report three separate results: source coverage/fidelity, editable
object representation, and target-application rendering. A passed export or
three centered labels cannot establish that the entire reconstruction is correct.

Deliver SVG, PPTX, preview and a concise list of actual remaining differences.
Keep the builder and source contract beside them for reproducibility. If a
renderer or font is unavailable, finish what can be verified and state the exact
limit. Do not claim 1:1, full verification or a recovered original design file
from object counts or sparse measurements. No permission pause is required for
routine reconstruction, local checking or fixing the requested artifact.
