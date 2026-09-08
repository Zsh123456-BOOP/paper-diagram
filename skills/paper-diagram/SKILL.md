---
name: paper-diagram
description: Draw or faithfully reconstruct editable scientific diagrams for LLM, machine learning and computer vision papers as SVG and PPTX. Use for “帮我复刻这张图”, model architecture diagrams, attention blocks, CNN feature maps, matrices and training pipelines. Preserve supplied reference layout, text, contours and connections; no paid vectorization API.
---

# Paper Diagram

Preserve scientific content and the original canvas. Choose editing units before choosing a vectorization algorithm. No account, key, balance check, remote synchronization or watermark service is part of the local conversion workflow. Agent-assisted interpretation uses the current session and its normal usage.

The Agent is the visual interpreter. Use the scripts to preserve decisions and export them reliably; they do not automatically discover semantic objects. Adapt the decomposition, algorithm and number of visual revisions to the image and the user's request. Carry drawing rules and helpers, not fixed coordinates for one paper.

## Default: “帮我复刻这张图”

A supplied image plus this sentence is sufficient. Default to a faithful, editable
SVG + PPTX and a preview, keeping the original canvas, composition, scientific
labels and relationships. Use session preferences and an explicit format request
when present. Do not require the user to supply a long prompt or repeat these
constraints. Automatic invocation is appropriate for this request.

Read [faithful reconstruction](references/faithful-reconstruction.md) before
authoring a supplied-image reconstruction. Its source inventory and reference
comparison are part of the task, not optional polish. Read the reference image
at full size and enlarge uncertain regions; make the inventory from the image
before constructing the output. Existing generated code is not the source of truth.
Freeze the source image and reference contract using `scripts/reference_evidence.py`
before drawing; the builder reads this snapshot and must not write expected values
or reviewed states. After rendering, run its `compare` command on the actual final
artifact preview and inspect the produced difference images. See
[reference evidence](references/reference-evidence.md) for the commands and limits.
Create a unique output directory for each task; concurrent tasks must not share
`preview.png`, scene files or reference snapshots.

No Image Generation is needed to reconstruct an existing reference. Use the
Agent to interpret it and local geometry, contour fitting and text tools to
rebuild it. Image Generation belongs to a separately requested creative or
inpainting task; its bitmap output does not recover editable reference objects.

Editable does not mean simplified. Preserve perspective, repeated planes,
handwriting/mask silhouettes, stroke density and relative typography. Do not
replace a detailed shape with a generic icon, redraw a diagram in a new layout,
or silently change mathematical notation. Choose editing units independently
of the detail needed inside each unit. Prefer contour fitting or centerlines
from the source for irregular details; all-vector output is not a reason to
invent replacement detail. Record unavoidable approximations and unresolved
content instead of claiming faithful completion.

## Choose the appropriate route

- For a new model diagram from text or code, first record the supplied modules, tensor dimensions and connections; distinguish explicit facts from assumptions. Use named Scene geometry and live text. Reference-image freezing and pixel comparison apply only when a reference image exists; otherwise validate the result against this specification and inspect the final rendered PPTX. Do not fabricate a reference image merely to run the reference checks. Use the user's stated model design as the source of truth.
- For a mixed figure or journal cover, separate text, layout, repeated geometry and detailed imagery first. Read [structured reconstruction](references/structured-reconstruction.md). Rebuild ordinary text as text and meaningful shapes as geometry; identify any preserved raster assets explicitly. Do not turn every pixel region into a separate editable object by default.
- For a user-selected all-vector appearance trace, trace the original bitmap. Explain that lettering is editable as paths, not as text content, and that many paths do not imply meaningful object separation.
- For live editable lettering, inspect the original, create a reviewed text manifest following [the schema](references/text-manifest.md), and use `--text-manifest`. Only use rectangular text removal on explicitly verified flat backgrounds; do not erase an intersecting arrow, grid, border or icon. Leave uncertain formulas and tiny labels as original paths, and disclose that choice.
- For an existing SVG, export it directly. Do not rasterize an available vector source.
- For a diagram that needs crisp editable labels and independently adjustable relationships, reconstruct it directly as SVG following [the reconstruction workflow](references/direct-svg.md). Use measured coordinates and verify relationships. For photographic artwork, compare an original-pixel baseline with any requested procedural experiment; do not claim invented texture is recovered detail. The Agent performs interpretation in the current session; the converter does not invoke a model service.

## Run

For an explicit request to draw live inside PowerPoint or record the drawing
process, read [native live drawing](references/live-powerpoint.md). This optional
mode creates native objects through VBA in a new PowerPoint document. Check its
supported subset before choosing it; do not reduce reference fidelity for a video.

For named components and portable native PPTX export, read [portable scenes](references/portable-scenes.md). Keep each matrix cell and its value in a group while leaving neighboring cells independent. Use same-color compound contours only inside explicitly named appearance assets, never across unrelated semantic objects.

`scripts/run.py` resolves the project environment and launches the local CLI. Use the Python executable available in the current environment:

```text
python <skill>/scripts/run.py convert <image-or-svg> --output-dir <new-directory>
python <skill>/scripts/run.py convert <image> --text-manifest <reviewed.json> --output-dir <new-directory>
python <skill>/scripts/run.py scene <reviewed-scene.json> --output <new-file.pptx>
```

The project must have the route's dependencies installed. The wrapper prefers the project's `.venv` and supports `CELL_LOCAL_ROOT` / `CELL_LOCAL_PYTHON` overrides. A portable copy includes source under `runtime` and needs no `CELL_LOCAL_ROOT`. Scene export needs fonttools; scene authoring also needs Pillow and a caller-supplied font map. The tracing CLI uses the full project dependencies. Read [portable scenes](references/portable-scenes.md) for installation. Do not install another proprietary API as a fallback.

For the tracing route, use `faithful` initially. If file complexity is excessive, compare `balanced` on the same source and retain the version that preserves details. This CLI default does not override the structure-first routing above. Existing outputs require an explicit `--overwrite`; prefer a new directory during revisions.

## Check and deliver

First run the source contract check from faithful-reconstruction.md. It can report
internal consistency only; `contract_status: pass` is not reconstruction approval.
Do not stop at this check or a builder-generated `reviewed` flag. Run the image
evidence comparison and verify its final-file bindings, then inspect
the exact final SVG and rendered PPTX against the reference, including all named
regions. Export probes below are additional checks, not fidelity acceptance.
Report coverage (checked / total), unresolved items and the exact checked file;
do not report an earlier candidate's QA as validation of a later delivery.


For alignment, gradient seams or missing arrows, read [object-aware render QA](references/render-qa.md). Bind labels to containers and inspect rendered arrow tips; object counts alone do not establish visibility.

1. Inspect the SVG preview at the original size and zoom in on thin lines, arrowheads, holes, dashed relationships and mathematical labels.
2. For reviewed live text, compare every restored label and its location. Keep unresolved text as paths rather than guessing content.
3. Read the conversion record: verify the expected aspect ratio and object types. For an all-vector route, confirm zero raster images; for a mixed route, inventory every raster asset and its provenance. Count live text, semantic groups and paint paths separately. A group is an editing convenience, not automatic semantic understanding; native paths are not smart connectors.
4. Open or render the final PPTX in the available target application before claiming application validation. An SVG preview alone does not establish PPTX visual correctness.
5. Deliver the requested files and name any material difference. State whether text content is editable or remains outlined; do not claim a perfect reconstruction or a scientific accuracy percentage from pixel metrics.

Illustrator can open the resulting SVG. Do not write into or rearrange an existing user document unless that is part of the user's request. No Adobe automation is required to generate these files.
