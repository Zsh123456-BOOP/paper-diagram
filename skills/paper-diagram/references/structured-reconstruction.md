# Reconstruct editable structure

Use for mixed scientific figures, journal covers, or requests to avoid thousands of tiny unrelated paths. This is an Agent-guided workflow with local deterministic helpers, not a universal one-click inverse-rendering model.

## Represent objects before drawing

Inspect the reference and measure its original canvas. Create a small scene manifest in the task workspace. Record each object's role, bounding box, z-order, content or source asset, intended editing unit, reconstruction method and uncertainties. For example:

```json
{
  "canvas": [440, 584],
  "objects": [
    {"id":"background", "type":"rect", "fill":"#29282A", "bbox":[0,0,440,584]},
    {"id":"headline", "type":"text", "content":"CHEMICAL", "bbox":[23,351,143,44], "font_status":"substitute, needs visual check"},
    {"id":"microscopy", "type":"image", "bbox":[0,120,440,327], "asset":"hero.png", "provenance":"visible source pixels; occluded content unknown"}
  ]
}
```

This is a planning schema; no general scene compiler is provided. Use the available presentation workflow to author the layout and text, or use the direct SVG route for diagrams. In Codex, follow the installed presentation skill when creating PPTX. Keep the generated builder alongside the scene manifest so edits can be reproduced.

- Ordinary labels, headlines and captions: reviewed live text; preserve text content independently from font fitting. Match baselines, line spacing and width. When WordArt is used to fit condensed lettering, verify it in the actual target application.
- Wordmarks or unknown logo lettering: one named compound vector object if outline accuracy matters. This is not live text.
- Lines, nodes, panels and repeated cells: native geometry grouped by what the user will move or restyle together. Preserve separate connectors when useful.
- Photographic or microscopy imagery: an explicitly identified source-image asset is often the most faithful baseline. An algorithmic vector experiment is a separate output when requested, not an undisclosed replacement.
- Unreadable microprint: preserve the original appearance as a named exception, rather than invent text. Report its representation.

Text over detailed artwork is an occlusion problem. A rectangular erase destroys the underlying visible fibers, edges or gradients. A verified letter mask can preserve visible pixels around letters, but cannot recover hidden content. Record any blank occlusion regions; generated/inpainted content must be identified as estimated. Reusing source pixels, extracting centerlines and generating a new image are distinct methods and must not be confused.

## Test filament reconstruction on a crop first

The repository's `experiments/trace_centerlines.py` is for **bright narrow filaments on a known dark background**. It is not a general photograph vectorizer. It composites alpha, measures Sato ridge response, builds a skeleton graph, joins clear continuations at existing nodes, simplifies chains and writes cubic strokes with sampled source colors. It never bridges an unobserved gap. Geometric crossings do not establish biological connections.

Optional dependencies: install `.[structure]` in the project's environment. The helpers run locally without a model or network call.

```bash
python experiments/trace_centerlines.py hero.png --output trial/roi.svg \
  --background '#29282A' --roi 40 65 220 190 \
  --threshold .012 --minimum-length .5
```

These parameters and coordinates were a cover-specific experiment, not defaults for unrelated images. Use `--minimum-chroma 0` for grayscale filaments. Threshold, scale, pruning and simplification must be chosen against the actual crop. Output includes SVG, a method/count report, and a branch manifest. Existing outputs and companion reports are refused.

Compare the crop at source size and enlarged: continuous fine lines, junctions, crossings, small holes, dark fibers, linewidth and local color. Reject a result that turns bright speckles into beads, creates spurious loops or loses important branches. Overlaying each branch's dark support stroke after an earlier bright core can erase intersections; paint all support strokes before all core strokes. Joining disconnected endpoints to make the image look smoother is not a fidelity repair.

If the crop remains different, label the output a structural experiment and keep the source-image baseline for appearance. Do not spend an arbitrary path budget merely to claim a smaller file. Curve interpolation and simplification can still change geometry; graph construction does not prove physical connectivity. Diffuse glow and granular texture are omitted by this experiment.

## Preserve groups in PPTX

The legacy SVG-to-PPTX CLI flattens SVG groups. Putting paths inside `<g>` alone therefore does not guarantee corresponding PowerPoint groups.

For centerline output, first create a layout deck with a picture in the reviewed microscopy frame and live text elsewhere. The experimental replacement helper replaces only that selected top-level picture, keeps its z-order, and maps SVG strokes to native DrawingML cubics. It preserves multi-path SVG groups and named single-path branches. Support/core layers are separate to retain paint order; they are two representations of the same branch IDs, not distinct fibers.

```bash
python experiments/trace_centerlines.py hero.png --output trial/network.svg \
  --background '#29282A' --threshold .012 --minimum-length .5
python experiments/replace_picture_with_curves.py layout.pptx trial/network.svg \
  --output trial/structured.pptx --picture-index 0 --frame 0 240 880 654
```

`--frame` is x/y/width/height in CSS pixels at 96 dpi; `--picture-index` is zero-based among top-level pictures on `--slide` (default 1). The helper requires a matching frame and aspect ratio and refuses rotated/cropped pictures. Only the tracer's plain untransformed, unfilled, round-stroked SVG subset is supported. It removes the replaced image's media only when no relationship still references it. It preserves other text, pictures and notes; update copied notes separately if they no longer describe the result.

An object group makes selection easier but does not reduce internal path count. Combine shapes only when fill, stroke, z-order and editing intent permit; keep holes and distinct relations intact. In Illustrator, use SVG paths/groups or a script that creates them. In Photoshop, report whether layers contain pixels, paths or smart objects. Never label an SVG renamed `.ai` as an Illustrator-native document or claim software execution from a file-only export.

### Mixed geometry scenes

For a reviewed scene containing text, solid geometry and vertical two-stop gradients, `experiments/svg_scene_to_pptx.py` can insert native grouped paths into a separately authored, single-slide text-only base. It checks matching canvas dimensions and text IDs/content, preserves compound contours, retains groups, supports cubic curves and the bounded gradient subset, and turns explicitly marked condensed headlines into editable WordArt. It is experimental and does not accept bitmap, mask or filter content.

```bash
python experiments/svg_scene_to_pptx.py scene.json base.pptx --output scene-candidate.pptx
```

The scene manifest contains `width`, `height`, optional `scale` (default 1), `geometry` (SVG path), and `texts`. Each text entry has `id` matching its named native base textbox and `content`; optional `wordart: true` fits text to its existing box, and `rotation` is in degrees. The SVG must have a matching `viewBox="0 0 width height"`. SVG text is replaced by the already reviewed native text; it is not OCRed or independently fit by this helper. Finalize and render the resulting candidate using the available presentation workflow.

For locally traced photographic panels, a cutout tessellation can allow same-fill regions to become compound paths. Do not apply that merge across a stacked painting sequence: overlapping different colors can change appearance. Shared-edge gaps can arise from independent curve fitting and antialiasing; inspect them at source scale. A very small same-color stroke can close seams, but also changes boundaries and must be checked against fine lines. A compact object count may still hide hundreds of thousands of control points. Such objects represent color regions, not individual trees, organelles or other recognized scientific entities.

### Matrices and editable relationships

When the user wants to select a plane, recolor a cell, or adjust a line, use those actions as the editing contract. A lower object count is not the objective: a compound containing hundreds of disconnected cells is harder to edit than a group containing named individual cells.

`experiments/semantic_grid.py` provides `matrix_plane(parent, name=..., origin=..., u=..., v=..., values=..., palette=...)`. It emits a named plane group, palette subgroups and one four-corner polygon per cell, named by row/column. `values` contains palette indices, not inferred scientific measurements. Store this parameter data alongside the generated SVG so another Agent can revise the geometry without tracing it again. Same-color cells stay individually selectable; palette groups permit collective restyling.

Determine row/column counts and plane corners against the reference. When recovering a discrete schematic palette, sample cell interiors and reconcile near-identical colors instead of treating antialiasing as additional categories. Continuous heatmaps require their continuous color scale; an arbitrary discrete palette must not replace encoded data. Occluded cells and unverified tensor dimensions remain estimates.

The mixed-scene exporter now preserves explicit, untransformed `stroke-dasharray` geometry as native dashed strokes. It maps `data-line-end="triangle"` to a native end arrow; use a matching SVG marker for the SVG preview. Nonzero dash offsets and transformed decorated lines are rejected rather than silently changed. Untransformed plain rectangles, circles and ellipses become native PowerPoint preset shapes. Other geometry retains editable native paths.

Check the saved package for one shape per intended cell, real nested groups, and one path per dashed relationship. A native line end stays with its path, but this does not provide automatic attachment to other shapes; do not call such paths smart connectors. Test an isolated edit and confirm unrelated objects do not change.

## Inspect and report

Validate the final saved file, not just the source SVG. Render it and inspect it in the requested application when available. Check that live text stays text, the wordmark/group can be selected as intended, curves stay native, only declared raster assets remain, and the package has no unused original-image payload after replacement. Report app validation separately from structural XML checks.

Deliver the requested baseline/experiment with a compact method record: source, dimensions, text count, group count, paint-path count, embedded-image inventory, fonts/substitutions and unresolved details. Provide a paired preview when useful. Do not call source tracing “entirely generated from scratch,” claim inferred details are 1:1 recovered, or interpret a pixel similarity score as scientific accuracy.
