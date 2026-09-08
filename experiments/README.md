# Experimental curve vectorization

This standalone prototype leaves the stable `cell-local convert` presets unchanged. It requires Pillow and an independently supplied **VTracer 1.0.0-alpha.4** executable. The official release is at https://github.com/visioncortex/vtracer/releases/tag/1.0.0-alpha.4 . CairoSVG and system Cairo are optional for previews.

```sh
python experiments/curve_vectorize.py reference.png --vtracer /path/to/vtracer --preset detail --output result.svg --preview
```

`detail` preserves small color regions at a 2x contour fitting grid, fits cubic curves, and omits speckle removal. `compact` removes regions below two working pixels. `flat` additionally limits the palette to 27 colors. `--palette-file` can supply a measured palette for controlled experiments; it is not needed for normal use. Upsampling does not create new observed detail.

The prototype uses local segmentation and curve fitting, not image generation. Its output is geometry without embedded images, but does not identify fibers, infer connectivity, or recover covered content. Text remains outlines. All images are composited on white. Existing output files are refused.

On the 440×584 cover used in this experiment, detail mode retained visibly more filament texture than the one paid-service sample, at the cost of about 80,000 paths and an 11 MB SVG. It did not establish a material general improvement over the existing faithful preset. This alpha backend is therefore **not promoted to the stable workflow**.

Verification for this change is the actual reference conversion, XML/path inspection, and rendered comparison. No external API is called by the script.
