# Reference evidence and final-render comparison

Use for faithful reconstruction of a supplied image. The goal is to reduce
circular self-checking: frozen observations plus actual reference pixels.
Hashes are change detection, not proof that the Agent measured independently.
A source crop, overlay or difference map is evidence for review, not automatically
correct OCR, semantic segmentation or a guarantee of faithful reconstruction.

## 1. Snapshot before drawing

In a unique task output directory, record `reference.json` as described in
faithful-reconstruction.md. Read the original image and enlarged crops first.
Every named region starts with `status: pending`; source boxes use x/y/width/height.
Do not create the expected answers by echoing `Scene` function arguments.

```sh
python <skill>/scripts/reference_evidence.py freeze input.png reference.json --output evidence-v1
```

This copies the original image and reference contract, records their SHA256 hashes
and canvas, and refuses to overwrite an existing snapshot. The drawing script
reads `evidence-v1/reference.json`; it must not write into this directory. Place
scene objects, ID mappings, outputs and review reports in separate candidate
folders. A legitimate corrected observation gets a new snapshot and a note of
which crop/measurement justified it. Do not overwrite evidence to clear a failure.

```sh
python <skill>/scripts/check_reference.py evidence-v1/reference.json candidate/scene.json \
  --snapshot evidence-v1/evidence.json --output candidate/contract.json
```

This checks snapshot integrity plus object/text/edge consistency. Its overall
status remains `review` even when `contract_status` is `pass`. Literal endpoint
checks are weaker than source/target port bindings; their counts are reported.
Neither a `reviewed` field nor matched output IDs proves source fidelity.

## 2. Compare the actual final render with source pixels

Export a preview of the exact final PPTX using the available target renderer.
Record the executed command or app action. SVG and PPTX previews are separate;
a correct SVG is not proof of a correct PPTX. Then run:

```sh
python <skill>/scripts/reference_evidence.py compare evidence-v1/evidence.json \
  --render candidate/final-pptx.png --artifact candidate/final.pptx \
  --scene candidate/scene.json --renderer 'Actual application/version and export method' \
  --output comparison-v1
```

Dependencies: Pillow, NumPy and SciPy (`pip install '<runtime>[qa]'` in the chosen
Python environment also installs the QA dependencies). Existing scene export still
works without SciPy; no library is installed by these scripts. No API key needed.

The comparison uses the original canvas. It permits only resolution normalization
and rejects aspect-ratio distortion beyond rounding tolerance. It does not shift,
warp, crop or independently register a region to make the output look closer.

Outputs:
- `comparison.png`: source left, rendered output right at the same scale.
- `overlay.png`: 50% overlap to expose coordinate drift.
- `edge-differences.png`: unmatched source edges in red; unmatched output edges in blue.
- `review-regions.png`: automatic full-canvas tiles with substantial differences boxed.
- `pixel-evidence.json`: named-region and tile measurements, exact-file hashes,
  renderer declaration, flags and limits.

Default flags use a 2-source-pixel edge tolerance, >20% unmatched edges in a region
with at least 12 edge pixels, or >15% changed pixels (max-channel difference >.12).
They are review heuristics, not acceptance thresholds. Antialiasing, fonts and
shading can trigger flags. Tiny important errors can escape them. Inspect the
images and formulas even when no flag fires. Do not report these fractions as
“scientific accuracy” or “percentage faithfully reconstructed”.

## 3. Review, repair locally, rebind

Review each named region plus flagged full-canvas tiles. Compare silhouettes,
perspective corners, text content/baselines, line density and graph relations.
Repair inaccurate objects; do not improve a score by changing reference data or
relaxing tolerance without a measured reason. Rerender after edits and generate a
new comparison directory. No fixed number of retries guarantees fidelity.

Write `visual-review.json` separately with the pixel report path/hash, artifact
hash and a list of region-specific findings: fixed errors, accepted differences,
uncertain symbols, and remaining blockers. Do not populate review statements in
the scene builder. A model's review remains judgment; state its limits candidly.

Before delivery:

```sh
python <skill>/scripts/reference_evidence.py verify comparison-v1/pixel-evidence.json
```

A changed artifact, preview, scene, SVG or frozen reference makes the old evidence
stale. `bindings_valid` only establishes those files have not changed. The script
cannot authenticate which application produced an image; the executed rendering
step is separate evidence. Pixel comparison always says `needs_visual_review`;
it never automatically pronounces the reconstruction correct.

Deliver the editable outputs and preview with meaningful remaining differences.
If checking is unavailable or incomplete, state what was actually verified.
Normal local reconstruction and repair need no extra user approval.
