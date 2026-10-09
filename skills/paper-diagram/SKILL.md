---
name: paper-diagram
description: Create editable scientific model and method diagrams from text, code or a specified design, especially ML architectures, attention blocks, matrices and training pipelines. Also supports explicitly requested diagram reconstruction; use cell-local by default for general supplied-image replication or journal covers.
---

# Paper Diagram

Create editable SVG, PPTX and a preview unless the user requests other formats. Use one primary drawing workflow per task, honoring an explicitly selected skill. Choose the mode from the actual source material before reading its references.

## New diagram from text or code

- Record the supplied modules, labels, tensor dimensions and connections. Separate explicit facts from assumptions; ask only for missing information that materially affects scientific meaning. Preserve experimental values and mathematical notation.
- Author named components, live text and meaningful relationships. Choose layout to explain the specified method; do not treat an illustrative layout as a scientific fact.
- Read [portable scenes](references/portable-scenes.md) for the Scene helper, font requirements and native PPTX export. Use [direct SVG](references/direct-svg.md) when direct geometry is appropriate, adapting its source measurements to the supplied design.
- Validate completeness and relationships against the user's description or code and inspect the final render. Reference-image freezing, pixel comparison and source-image contracts apply only to reconstruction; do not fabricate an image merely to run them.

## Reconstruction when explicitly requested

- Preserve the reference canvas, labels, geometry and connections. Inspect the original and uncertain crops before drawing. Do not simplify detail, guess formulas or replace irregular objects with generic icons.
- Read [faithful reconstruction](references/faithful-reconstruction.md) and [reference evidence](references/reference-evidence.md). Freeze source observations before authoring; the builder must not write expected values or reviewed states. Use their contract and final-render evidence checks for this mode.
- For mixed figures, read [structured reconstruction](references/structured-reconstruction.md). For live lettering, read [text manifest](references/text-manifest.md); text removal requires a verified flat background and must preserve crossing objects. Keep unresolved labels as paths and disclose them.
- Preserve an existing vector source. For requested appearance tracing, distinguish paint paths from semantic editing units and start with `faithful`; compare `balanced` only when complexity warrants it. Identify raster assets and their provenance; do not invent recovered photographic detail.

## Export and optional modes

- Use separate task directories for sources, candidates and previews. Group a matrix cell with its value while keeping neighboring cells independent; compound contours must not merge unrelated semantic objects.
- `scripts/run.py` resolves the source checkout or bundled runtime and prefers its `.venv`; `CELL_LOCAL_ROOT` / `CELL_LOCAL_PYTHON` select an existing environment. Dependencies and exporter limits are documented in [portable scenes](references/portable-scenes.md). No paid vectorization API is needed.

```text
python <skill>/scripts/run.py scene <reviewed-scene.json> --output <new-file.pptx>
python <skill>/scripts/run.py convert <image-or-svg> --output-dir <new-directory>
python <skill>/scripts/run.py convert <image> --text-manifest <reviewed.json> --output-dir <new-directory>
```

- For an explicit request to draw live in PowerPoint or record the process, read [live PowerPoint](references/live-powerpoint.md); check its supported subset and use a new document unless editing an existing document is authorized.
- For alignment, gradients, labels and arrows, read [render QA](references/render-qa.md). A requested bitmap edit or generated image follows the applicable image tool workflow; this workflow is for editable diagrams.

## Verify and deliver

- Check labels, dimensions, arrow directions and scientific relationships against the selected source: the supplied design for new diagrams, or the original image for reconstruction.
- Inspect the exact final SVG and rendered PPTX. For reconstruction, also review the reference comparison and named regions. Internal consistency checks, object counts and image scores are supporting evidence, not fidelity approval.
- Verify meaningful editability and disclose live text, outlined text, raster assets and material approximations. An SVG preview does not validate PPTX rendering; report application validation only after opening or rendering the final PPTX in the available target application.
- Repair relevant defects and validate the changed final files before delivery. Report unresolved content or missing validation plainly; never use earlier-candidate QA or claim scientific accuracy percentages from pixel metrics.
