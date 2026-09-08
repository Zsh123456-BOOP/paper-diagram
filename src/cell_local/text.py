"""Reviewed, pixel-coordinate text removal and restoration, entirely offline.

This module deliberately does not infer a background or approve OCR output.
An agent or person must review each label before any pixels are removed.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a JSON number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _color(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        raise ValueError(f"{name} must be an explicit opaque #RGB or #RRGGBB color")
    return value


def _xml_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if any(not (c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF) for c in value):
        raise ValueError(f"{name} contains characters invalid in XML")
    return value


def _load_manifest(manifest_path: str | Path) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise ValueError("manifest schema_version must be '1.0'")
    width = _number(manifest.get("image_width"), "image_width")
    height = _number(manifest.get("image_height"), "image_height")
    if width <= 0 or height <= 0 or not width.is_integer() or not height.is_integer():
        raise ValueError("image_width and image_height must be positive pixel integers")
    items = manifest.get("text_elements")
    if not isinstance(items, list):
        raise ValueError("text_elements must be an array")
    used_ids: set[str] = set()
    clean_items = []
    for index, source in enumerate(items):
        prefix = f"text_elements[{index}]"
        if not isinstance(source, dict):
            raise ValueError(f"{prefix} must be an object")
        item = dict(source)
        if item.get("reviewed") is not True:
            raise ValueError(f"{prefix} requires reviewed:true before removal or restoration")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", item_id):
            raise ValueError(f"{prefix}.id must be an XML-safe identifier")
        item["content"] = _xml_string(item.get("content"), f"{prefix}.content")
        lines = item["content"].splitlines()
        if not lines or any(not line.strip() for line in lines):
            raise ValueError(f"{prefix}.content must have no empty lines")
        generated_ids = {item_id} if len(lines) == 1 else {f"{item_id}-line-{n + 1}" for n in range(len(lines))}
        # Reserve the manifest ID as well, even when only line IDs are emitted.
        reserved = generated_ids | {item_id}
        if used_ids & reserved:
            raise ValueError(f"duplicate text id: {item_id}")
        used_ids.update(reserved)
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"{prefix}.bbox must be [left, top, width, height]")
        left, top, box_width, box_height = [_number(v, f"{prefix}.bbox[{n}]") for n, v in enumerate(bbox)]
        if left < 0 or top < 0 or box_width <= 0 or box_height <= 0 or left + box_width > width or top + box_height > height:
            raise ValueError(f"{prefix}.bbox is outside the image or has non-positive size")
        item["bbox"] = [left, top, box_width, box_height]
        item["x"] = _number(item.get("x"), f"{prefix}.x")
        item["y"] = _number(item.get("y"), f"{prefix}.y")
        item["font_size"] = _number(item.get("font_size"), f"{prefix}.font_size")
        if item["font_size"] <= 0 or item["font_size"] > height:
            raise ValueError(f"{prefix}.font_size must be positive and no larger than image height")
        item["line_height"] = _number(item.get("line_height", 1.2), f"{prefix}.line_height")
        if item["line_height"] <= 0:
            raise ValueError(f"{prefix}.line_height must be positive")
        last_y = item["y"] + (len(lines) - 1) * item["line_height"] * item["font_size"]
        if not (0 <= item["x"] <= width and 0 <= item["y"] <= height and last_y <= height):
            raise ValueError(f"{prefix} text baseline is outside the image")
        item["font_family"] = _xml_string(item.get("font_family", "Times New Roman"), f"{prefix}.font_family")
        item["font_weight"] = str(item.get("font_weight", "normal"))
        if item["font_weight"] not in {"normal", "bold", *[str(n) for n in range(100, 1000, 100)]}:
            raise ValueError(f"{prefix}.font_weight is unsupported")
        item["font_style"] = item.get("font_style", "normal")
        if item["font_style"] not in {"normal", "italic", "oblique"}:
            raise ValueError(f"{prefix}.font_style is unsupported")
        item["fill"] = _color(item.get("fill", "#000000"), f"{prefix}.fill")
        item["background"] = _color(item.get("background"), f"{prefix}.background")
        if "text_width" in item or "textLength" in item:
            raise ValueError(f"{prefix}: text_width/textLength is unsupported; use an accurate font_size")
        clean_items.append(item)
    return {"schema_version": "1.0", "image_width": int(width), "image_height": int(height), "text_elements": clean_items}


def _distinct_output(source: str | Path, destination: str | Path) -> Path:
    source_path, output_path = Path(source).resolve(), Path(destination).resolve()
    if source_path == output_path:
        raise ValueError("output must differ from the source; preserve the original")
    return output_path


def prepare_text_image(input_path: str | Path, manifest_path: str | Path, cleaned_path: str | Path) -> dict:
    """Fill reviewed text boxes in the image's displayed, EXIF-corrected orientation.

    Bounding boxes are half-open pixel areas, rounded outward. They must contain
    only the intended text on a verified flat background, without intersecting
    lines, icons, or other labels. No inpainting or background guessing occurs.
    """
    manifest = _load_manifest(manifest_path)
    output_path = _distinct_output(input_path, cleaned_path)
    if output_path.suffix.lower() != ".png":
        raise ValueError("cleaned_path must end in .png to avoid lossy recompression")
    with Image.open(input_path) as source:
        displayed = ImageOps.exif_transpose(source)
        expected = (manifest["image_width"], manifest["image_height"])
        if displayed.size != expected:
            raise ValueError(f"manifest image dimensions {expected} differ from displayed input {displayed.size}")
        cleaned = displayed.convert("RGBA" if "A" in displayed.getbands() or "transparency" in displayed.info else "RGB")
    draw = ImageDraw.Draw(cleaned)
    for item in manifest["text_elements"]:
        left, top, width, height = item["bbox"]
        draw.rectangle((math.floor(left), math.floor(top), math.ceil(left + width) - 1, math.ceil(top + height) - 1), fill=item["background"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.save(output_path, format="PNG")
    return {"cleaned_path": str(output_path), "text_count": len(manifest["text_elements"]), "image_width": manifest["image_width"], "image_height": manifest["image_height"]}


def _svg_canvas(root: ET.Element, manifest: dict) -> None:
    if root.tag != f"{{{SVG_NS}}}svg":
        raise ValueError("input must have a namespaced SVG root")
    if any(node.tag.rsplit("}", 1)[-1] in {"image", "feImage", "foreignObject", "script"} for node in root.iter()):
        raise ValueError("SVG must contain only vector artwork; raster or active nodes are prohibited")
    width, height = manifest["image_width"], manifest["image_height"]
    raw_viewbox = root.get("viewBox")
    if raw_viewbox:
        try:
            values = [float(value) for value in re.split(r"[\s,]+", raw_viewbox.strip())]
        except ValueError as error:
            raise ValueError("invalid SVG viewBox") from error
        if len(values) != 4 or not all(math.isfinite(v) for v in values) or any(abs(a - b) > 1e-6 for a, b in zip(values, (0, 0, width, height))):
            raise ValueError("SVG viewBox must be 0 0 image_width image_height in manifest pixels")
    else:
        for key, expected in (("width", width), ("height", height)):
            raw = root.get(key, "")
            if not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:px)?", raw):
                raise ValueError("SVG without viewBox requires pixel width and height")
            if not math.isclose(float(raw.removesuffix("px")), expected, abs_tol=1e-6, rel_tol=0):
                raise ValueError("SVG dimensions differ from the manifest")
        root.set("viewBox", f"0 0 {width} {height}")


def restore_text(svg_path: str | Path, manifest_path: str | Path, output_path: str | Path) -> dict:
    """Append real SVG text over existing vector paths, one element per line."""
    manifest = _load_manifest(manifest_path)
    destination = _distinct_output(svg_path, output_path)
    raw = Path(svg_path).read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("SVG document type and entity declarations are unsupported")
    root = ET.fromstring(raw)
    _svg_canvas(root, manifest)
    existing_ids: set[str] = set()
    for node in root.iter():
        node_id = node.get("id")
        if node_id:
            if node_id in existing_ids:
                raise ValueError(f"duplicate existing SVG id: {node_id}")
            existing_ids.add(node_id)
    additions = []
    for item in manifest["text_elements"]:
        lines = item["content"].splitlines()
        if item["id"] in existing_ids:
            raise ValueError(f"text id already exists in SVG: {item['id']}")
        for index, line in enumerate(lines):
            line_id = item["id"] if len(lines) == 1 else f"{item['id']}-line-{index + 1}"
            if line_id in existing_ids:
                raise ValueError(f"text id already exists in SVG: {line_id}")
            existing_ids.add(line_id)
            element = ET.Element(f"{{{SVG_NS}}}text", {
                "id": line_id,
                "x": f"{item['x']:g}",
                "y": f"{item['y'] + index * item['line_height'] * item['font_size']:g}",
                "font-family": item["font_family"],
                "font-size": f"{item['font_size']:g}",
                "font-weight": item["font_weight"],
                "font-style": item["font_style"],
                "fill": item["fill"],
                "text-anchor": "start",
                f"{{http://www.w3.org/XML/1998/namespace}}space": "preserve",
                "data-cell-local-text-id": item["id"],
            })
            element.text = line
            additions.append(element)
    root.extend(additions)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(destination, encoding="utf-8", xml_declaration=True)
    return {"output_path": str(destination), "output_svg": str(destination), "live_text_count": len(additions), "text_count": len(manifest["text_elements"])}


def generate_ocr_draft(input_path: str | Path, output_manifest: str | Path, lang: str = "eng") -> dict:
    """Use an already installed Tesseract CLI to propose unreviewed line boxes.

    Sparse-text segmentation (PSM 11) suits scattered scientific figure labels.
    Coordinates follow displayed pixels after applying EXIF orientation.
    Font, baseline, content and every box need manual/agent verification. No
    packages, language models or external services are downloaded or called.
    """
    executable = shutil.which("tesseract")
    if executable is None:
        raise RuntimeError("Tesseract is optional and is not installed; create a reviewed manifest manually")
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", lang):
        raise ValueError("lang must be a Tesseract language name or '+' separated names")
    source_path = Path(input_path).resolve()
    destination = _distinct_output(source_path, output_manifest)
    with tempfile.TemporaryDirectory(prefix="cell-local-ocr-") as temporary:
        normalized_path = Path(temporary) / "displayed.png"
        with Image.open(source_path) as source:
            displayed = ImageOps.exif_transpose(source).convert("RGBA")
            width, height = displayed.size
            # Match the vectorizer's white canvas for transparent source pixels.
            normalized = Image.alpha_composite(Image.new("RGBA", displayed.size, "white"), displayed).convert("RGB")
            normalized.save(normalized_path, format="PNG")
        completed = subprocess.run([executable, str(normalized_path), "stdout", "-l", lang, "--psm", "11", "tsv"], capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
    if completed.returncode:
        raise RuntimeError(f"Tesseract failed: {completed.stderr.strip()}")
    groups: dict[tuple, list[dict]] = {}
    for row in csv.DictReader(io.StringIO(completed.stdout), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        if float(row.get("conf", "-1")) < 0:
            continue
        key = tuple(row.get(field) for field in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append(row)
    items = []
    for index, rows in enumerate(groups.values()):
        left = min(int(row["left"]) for row in rows)
        top = min(int(row["top"]) for row in rows)
        right = max(int(row["left"]) + int(row["width"]) for row in rows)
        bottom = max(int(row["top"]) + int(row["height"]) for row in rows)
        items.append({"id": f"ocr-line-{index + 1:03}", "content": " ".join(row["text"] for row in rows), "bbox": [left, top, right - left, bottom - top], "x": left, "y": bottom, "font_family": "Times New Roman", "font_size": max(1, bottom - top), "font_weight": "normal", "fill": "#000000", "background": None, "reviewed": False, "ocr_confidence": round(sum(float(row["conf"]) for row in rows) / len(rows), 2)})
    manifest = {"schema_version": "1.0", "image_width": width, "image_height": height, "coordinate_space": "display_pixels", "ocr_engine": "tesseract", "ocr_page_segmentation_mode": 11, "draft": True, "review_note": "Review content, box, baseline, font and solid background in the displayed EXIF-corrected orientation; never approve a box that crosses artwork.", "text_elements": items}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_manifest": str(destination), "draft_text_count": len(items), "review_required": True, "image_width": width, "image_height": height, "ocr_page_segmentation_mode": 11}
