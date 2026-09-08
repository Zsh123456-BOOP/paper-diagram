# Native PowerPoint live drawing (experimental)

Use when the user explicitly wants to watch or record real object creation in
PowerPoint. Ordinary image reconstruction keeps the existing SVG/PPTX workflow.
This mode compiles an Agent-authored Scene into readable VBA. The macro creates
a new presentation and calls PowerPoint's own AddShape, AddTextbox,
BuildFreeform / AddNodes / ConvertToShape and ShapeRange.Group methods.
It does not import a completed slide, reveal hidden objects, or paste screenshots.

## Prepare

Author and review the Scene as usual, then:

```sh
python <skill>/scripts/run.py live <scene.json> --output-dir <new-directory> --interval 0.2
```

This produces `PaperDiagramLive.bas` and `live-plan.json`. The plan keeps source
hashes, shape geometry, text metrics, group membership and execution order.
Compilation is local and does not open Office. The copied skill includes the
compiler in its runtime; it requires fonttools, with Pillow for Scene authoring.

The initial native subset covers rectangles, ellipses, rounded rectangles,
perspective polygons, single-contour cubic/quadratic paths, triangular arrow
ends, solid fills, shape opacity, measured live text and nested groups.
Single-member groups are represented by a named shape. Each matrix cell and
its value can be grouped independently before grouping the matrix.

Transforms, compound contours/holes, gradients, arbitrary dash patterns, masks,
images, fitted/rotated text and mixed text runs currently fail compilation.
Use the ordinary exporter when those details are required. Do not silently
simplify the figure just to make a live video. Text and arrow rendering must
still be checked in the actual PowerPoint version; the live renderer is not
assumed pixel-identical to the OOXML renderer.

## Execute in PowerPoint

1. Open a new blank presentation as the macro host. Keep user documents intact.
2. Open Tools → Macro → Visual Basic Editor (or the host's Developer/VBA entry).
3. In the editor, File → Import File, select `PaperDiagramLive.bas`.
4. Return to PowerPoint, open the macro dialog and run `PaperDiagramDraw` from
   the macro host. It creates another new presentation and draws there.

Other public entry points:

- `PaperDiagramStart`: create a fresh blank output without drawing.
- `PaperDiagramNext`: create the next object or group.
- `PaperDiagramPlay`: continue drawing at the configured interval.
- `PaperDiagramPause`: stop the loop after the current step.

Start recording with the editor closed so the slide canvas stays visible.
Use the host's allowed UI automation or document interface to import and run
the module. Do not change global macro-security settings or enable trusted
VBProject access to automate import. Stop and explain any required permission
that the current session does not authorize. This module contains no network
calls, shell commands, external code loading, deletion or automatic SaveAs.

Save the newly drawn presentation as `.pptx` using PowerPoint's normal Save
dialog. Save the separate macro host as `.pptm` only if a rerunnable host is
useful to the user. The generated output does not need to contain macros.

## Verification and recording

Observe an intermediate state as well as the final state; a final screenshot
alone does not establish live refresh. Each completed step records its index
and Timer timestamp in VBA's Immediate window. The slide stores completed/total
step tags and source hashes; shapes store step and object tags. These tags are
execution records, not independent proof of fidelity or editability.

Inspect the saved PPTX for native shapes, text, groups, curves and visible arrow
ends. On a demo copy, edit text, recolor a cell, and move a group. A shape count
alone does not establish that a native command worked or rendered correctly.

Preserve the full screen recording before making a 30-second cut. Mark speedup
and omit idle waiting if needed. This visualizes execution of reviewed drawing
code, not the Agent's hidden reasoning or continuous image understanding.
The compiler does not yet capture or edit video itself. Use an explicitly
authorized screen recorder; keep unrelated windows and notifications out of
the capture area. Never label a reconstruction replay as a first-run capture.

Native API references: [BuildFreeform](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.shapes.buildfreeform),
[AddTextbox](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.shapes.addtextbox),
[VBA file import](https://learn.microsoft.com/en-us/office/vba/language/reference/user-interface-help/file-menu).
