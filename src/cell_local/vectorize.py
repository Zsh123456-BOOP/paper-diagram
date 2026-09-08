"""Local raster tracing for scientific figures, with no network or API key.

The output contains SVG paths, not an embedded copy of the input bitmap.
Tracing preserves appearance; it does not identify semantic objects or turn
outlined glyphs into editable text. Alpha is composited onto white explicitly
so partially transparent edges render consistently in SVG and PowerPoint.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import os
from pathlib import Path
import tempfile
import time
from typing import Any
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps, UnidentifiedImageError


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

# Faithful uses a 4x fitting grid so a two-pixel speckle threshold removes
# isolated antialias fragments while retaining longer one-pixel lines.
# Polygon fitting avoids spline overshoot at small arrowheads and line joins.
# Upsampling changes contour fitting resolution, never the output canvas size.
PRESETS: dict[str, dict[str, Any]] = {
    "faithful": {
        "upsample": 4,
        "mode": "polygon",
        "color_precision": 8,
        "layer_difference": 8,
        "filter_speckle": 2,
    },
    "balanced": {
        "upsample": 2,
        "mode": "polygon",
        "color_precision": 6,
        "layer_difference": 32,
        "filter_speckle": 2,
    },
}


def _read_image(source: Path) -> tuple[Image.Image, dict[str, Any]]:
    try:
        with Image.open(source) as opened:
            if opened.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError(
                    f"Unsupported image format {opened.format!r}; use PNG, JPEG, or WebP."
                )
            if getattr(opened, "n_frames", 1) != 1:
                raise ValueError("Animated or multi-frame images are not supported; export one frame.")
            original_size = opened.size
            source_format = opened.format
            exif_orientation = opened.getexif().get(274, 1)
            rgba = ImageOps.exif_transpose(opened).convert("RGBA")
            alpha_min, _ = rgba.getchannel("A").getextrema()
            # A fixed matte also removes hidden RGB data under transparent pixels.
            white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            rgb = Image.alpha_composite(white, rgba).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Cannot decode input image {source}: {exc}") from exc
    return rgb, {
        "input_format": source_format,
        "original_size": list(original_size),
        "width": rgb.width,
        "height": rgb.height,
        "input_has_transparency": alpha_min < 255,
        "alpha_handling": "composited-on-white" if alpha_min < 255 else "opaque",
        "matte_color": "#ffffff",
        "exif_orientation_applied": exif_orientation not in (None, 1),
    }


def vectorize_image(
    input_path: str | os.PathLike[str],
    output_svg: str | os.PathLike[str],
    preset: str = "faithful",
) -> dict[str, Any]:
    """Trace a PNG/JPEG/WebP into a standalone SVG and return JSON metadata.

    ``faithful`` fits polygon contours at four times the input resolution;
    ``balanced`` uses twice the resolution and fewer color layers, producing
    fewer paths with greater loss of tiny details. Both use stacked, nonzero
    filled contours. Upsampling is reduced for large images to keep the working
    raster at or below 16 million pixels (unless the input itself exceeds that).
    Canvas dimensions follow the decoded image after EXIF orientation.

    The destination is replaced atomically only after parsing and validating
    the generated SVG. The input can never be used as the output destination.
    No OCR, generative model, external service, or Adobe installation is used.
    """
    started = time.perf_counter()
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r}; choose from {', '.join(PRESETS)}.")
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_svg).expanduser().resolve()
    if source == destination:
        raise ValueError("Input and output must be different files; the source image is never overwritten.")
    if destination.suffix.lower() != ".svg":
        raise ValueError("The vector output path must end in .svg.")
    if not source.is_file():
        raise FileNotFoundError(f"Input image does not exist or is not a file: {source}")
    if destination.exists() and source.samefile(destination):
        raise ValueError("Input and output refer to the same file; the source image is never overwritten.")
    if destination.exists() and destination.is_dir():
        raise ValueError(f"The output path is a directory: {destination}")

    rgb, metadata = _read_image(source)
    try:
        import vtracer
    except ImportError as exc:
        raise RuntimeError("VTracer is not installed; install the project's declared dependencies.") from exc

    settings = dict(PRESETS[preset])
    scale = settings.pop("upsample")
    requested_scale = scale
    while scale > 1 and rgb.width * rgb.height * scale * scale > 16_000_000:
        scale //= 2
    if scale != 1:
        rgb = rgb.resize((rgb.width * scale, rgb.height * scale), Image.Resampling.BICUBIC)
    encoded = io.BytesIO()
    rgb.save(encoded, format="PNG")
    parameters = {
        "colormode": "color",
        "hierarchical": "stacked",
        "mode": "spline",
        "corner_threshold": 60,
        "length_threshold": 3.5,
        "max_iterations": 10,
        "splice_threshold": 45,
        "path_precision": 3,
        **settings,
    }
    try:
        svg_text = vtracer.convert_raw_image_to_svg(
            encoded.getvalue(), img_format="png", **parameters
        )
    except Exception as exc:
        raise RuntimeError(f"Local VTracer conversion failed: {exc}") from exc

    root = ET.fromstring(svg_text)
    if root.tag != f"{{{SVG_NS}}}svg":
        raise RuntimeError("VTracer did not return an SVG document.")
    # VTracer 0.6 emits empty d attributes for some tiny color clusters. These
    # have no visible geometry and break strict downstream SVG path parsers.
    empty_path_count = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag == f"{{{SVG_NS}}}path" and not child.get("d", "").strip():
                parent.remove(child)
                empty_path_count += 1
    paths = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in {"svg", "g", "path"}:
            raise RuntimeError(f"Unexpected element in the path-only SVG: {tag}")
        if tag == "path":
            paths.append(node)
    if not paths:
        raise RuntimeError("VTracer returned no paths for the normalized image.")

    width, height = metadata["width"], metadata["height"]
    root.set("width", str(width))
    root.set("height", str(height))
    root.set("viewBox", f"0 0 {width} {height}")
    if scale != 1:
        group = ET.Element(f"{{{SVG_NS}}}g", {"transform": f"scale({1 / scale:g})"})
        for child in list(root):
            root.remove(child)
            group.append(child)
        root.append(group)
    # Stable IDs make individual contours selectable in later editing stages.
    for index, path in enumerate(paths, start=1):
        path.set("id", f"contour-{index:05d}")
    result_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".svg", prefix=".cell-local-", dir=destination.parent, delete=False
        ) as handle:
            temporary_path = handle.name
            handle.write(result_bytes)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)

    return {
        **metadata,
        "input_path": str(source),
        "output_svg": str(destination),
        "preset": preset,
        "engine": "vtracer",
        "engine_version": importlib.metadata.version("vtracer"),
        "upsample": scale,
        "requested_upsample": requested_scale,
        "working_raster_size": [rgb.width, rgb.height],
        "parameters": parameters,
        "path_count": len(paths),
        "discarded_empty_path_count": empty_path_count,
        "embedded_raster_count": 0,
        "editable_text_count": 0,
        "output_bytes": len(result_bytes),
        "output_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "limitations": [
            "Contours are editable paths; they are not semantic shapes or connected arrows.",
            "Text present in the input is traced as outlines, not editable text.",
            "Tiny marks and antialiased edges may change; visually review scientific notation.",
            "Transparent pixels are composited onto a white background.",
        ],
    }
