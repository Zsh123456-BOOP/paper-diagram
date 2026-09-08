"""Behavioral tests for reviewed text restoration and pixel preservation."""

import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cell_local.text import generate_ocr_draft, prepare_text_image, restore_text


class TextWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source.png"
        Image.new("RGB", (100, 60), "black").save(self.source)
        self.manifest_path = self.root / "text.json"
        self.item = {"id": "label", "content": "Graph & nodes", "bbox": [10, 10, 70, 20], "x": 11, "y": 26, "font_family": "Times New Roman", "font_size": 12, "font_weight": "normal", "fill": "#123456", "background": "#ffffff", "reviewed": True}
        self.manifest = {"schema_version": "1.0", "image_width": 100, "image_height": 60, "text_elements": [self.item]}
        self.svg_path = self.root / "paths.svg"
        self.svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60" viewBox="0 0 100 60"><path id="shape" d="M 0 0 L 99 59" stroke="#000000"/></svg>')

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def test_removal_preserves_every_pixel_outside_half_open_box(self):
        self.write_manifest()
        output = self.root / "cleaned.png"
        result = prepare_text_image(self.source, self.manifest_path, output)
        self.assertEqual(result["text_count"], 1)
        with Image.open(output) as image:
            for y in range(60):
                for x in range(100):
                    self.assertEqual(image.getpixel((x, y)), (255, 255, 255) if 10 <= x < 80 and 10 <= y < 30 else (0, 0, 0))
        with Image.open(self.source) as original:
            self.assertEqual(original.getpixel((20, 20)), (0, 0, 0))

    def test_restore_keeps_path_and_emits_escaped_real_text(self):
        self.write_manifest()
        output = self.root / "restored.svg"
        result = restore_text(self.svg_path, self.manifest_path, output)
        root = ET.parse(output).getroot()
        path = root.find("{http://www.w3.org/2000/svg}path")
        text = root.find("{http://www.w3.org/2000/svg}text")
        self.assertEqual(path.get("d"), "M 0 0 L 99 59")
        self.assertEqual(text.text, "Graph & nodes")
        self.assertEqual(text.get("font-size"), "12")
        self.assertEqual(text.get("x"), "11")
        self.assertEqual(result["live_text_count"], 1)
        self.assertFalse(root.findall(".//{http://www.w3.org/2000/svg}image"))

    def test_multiline_is_independent_text_with_baseline_spacing(self):
        self.item.update(content="Graph\nnodes", y=20, line_height=1.5)
        self.write_manifest()
        output = self.root / "multiline.svg"
        restore_text(self.svg_path, self.manifest_path, output)
        texts = ET.parse(output).getroot().findall("{http://www.w3.org/2000/svg}text")
        self.assertEqual([node.get("id") for node in texts], ["label-line-1", "label-line-2"])
        self.assertEqual([node.get("y") for node in texts], ["20", "38"])

    def test_unreviewed_rejected_without_writing(self):
        self.item["reviewed"] = False
        self.write_manifest()
        for operation, source, name in ((prepare_text_image, self.source, "unreviewed.png"), (restore_text, self.svg_path, "unreviewed.svg")):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(ValueError, "reviewed:true"):
                operation(source, self.manifest_path, self.root / name)
            self.assertFalse((self.root / name).exists())

    def test_invalid_manifest_values_rejected(self):
        cases = (("bbox", [-1, 10, 70, 20]), ("bbox", [10, 10, 95, 20]), ("x", float("nan")), ("font_size", float("inf")), ("font_size", True), ("background", None), ("content", ""), ("content", "x\u0000"), ("id", "bad id"), ("y", 61), ("text_width", 70))
        for field, value in cases:
            with self.subTest(field=field, value=value):
                saved = dict(self.item)
                self.item[field] = value
                self.write_manifest()
                with self.assertRaises(ValueError):
                    prepare_text_image(self.source, self.manifest_path, self.root / "invalid.png")
                self.item.clear()
                self.item.update(saved)

    def test_duplicate_and_svg_id_collisions_rejected(self):
        self.manifest["text_elements"].append(dict(self.item))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            restore_text(self.svg_path, self.manifest_path, self.root / "duplicate.svg")
        self.manifest["text_elements"].pop()
        self.item["id"] = "shape"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "already exists"):
            restore_text(self.svg_path, self.manifest_path, self.root / "collision.svg")

    def test_canvas_mismatch_and_raster_rejected(self):
        self.write_manifest()
        for contents in ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60"/>', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><image href="data:image/png;base64,AAAA"/></svg>'):
            with self.subTest(contents=contents):
                self.svg_path.write_text(contents)
                with self.assertRaises(ValueError):
                    restore_text(self.svg_path, self.manifest_path, self.root / "bad-svg.svg")
        self.manifest["image_width"] = 99
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "dimensions"):
            prepare_text_image(self.source, self.manifest_path, self.root / "bad-image.png")

    def test_source_cannot_be_overwritten(self):
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "preserve the original"):
            prepare_text_image(self.source, self.manifest_path, self.source)
        with self.assertRaisesRegex(ValueError, "preserve the original"):
            restore_text(self.svg_path, self.manifest_path, self.svg_path)

    def oriented_source(self):
        source = Image.new("RGB", (100, 60), "black")
        source.putpixel((90, 10), (255, 0, 0))
        exif = Image.Exif()
        exif[274] = 6  # Stored landscape pixels display rotated 90 degrees clockwise.
        source.save(self.source, exif=exif)

    def test_removal_uses_displayed_exif_coordinates_and_preserves_orientation(self):
        self.oriented_source()
        self.manifest.update(image_width=60, image_height=100)
        self.item["bbox"] = [10, 10, 30, 20]
        self.write_manifest()
        output = self.root / "oriented-cleaned.png"
        result = prepare_text_image(self.source, self.manifest_path, output)
        self.assertEqual((result["image_width"], result["image_height"]), (60, 100))
        with Image.open(output) as image:
            self.assertEqual(image.size, (60, 100))
            self.assertEqual(image.getpixel((20, 20)), (255, 255, 255))
            self.assertEqual(image.getpixel((49, 90)), (255, 0, 0))
            self.assertEqual(image.getexif().get(274, 1), 1)
        with Image.open(self.source) as original:
            self.assertEqual(original.size, (100, 60))
            self.assertEqual(original.getexif().get(274), 6)
        self.manifest.update(image_width=100, image_height=60)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "displayed input"):
            prepare_text_image(self.source, self.manifest_path, self.root / "wrong-orientation.png")

    def test_ocr_sparse_mode_normalizes_exif_and_requires_review(self):
        self.oriented_source()
        draft_path = self.root / "ocr-draft.json"
        normalized_inputs = []

        def fake_tesseract(command, **kwargs):
            self.assertEqual(command[2:], ["stdout", "-l", "eng", "--psm", "11", "tsv"])
            normalized_path = Path(command[1])
            normalized_inputs.append(normalized_path)
            self.assertNotEqual(normalized_path, self.source)
            with Image.open(normalized_path) as normalized:
                self.assertEqual(normalized.size, (60, 100))
                self.assertEqual(normalized.getexif().get(274, 1), 1)
                self.assertEqual(normalized.getpixel((49, 90)), (255, 0, 0))
            tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t10\t20\t8\t99\tGraph\n"
            return subprocess.CompletedProcess(command, 0, tsv, "")

        with patch("cell_local.text.shutil.which", return_value="/local/tesseract"), patch("cell_local.text.subprocess.run", side_effect=fake_tesseract):
            result = generate_ocr_draft(self.source, draft_path)
        self.assertFalse(normalized_inputs[0].exists())
        self.assertEqual((result["image_width"], result["image_height"]), (60, 100))
        manifest = json.loads(draft_path.read_text())
        self.assertEqual(manifest["ocr_page_segmentation_mode"], 11)
        self.assertEqual(manifest["coordinate_space"], "display_pixels")
        self.assertEqual(manifest["text_elements"][0]["content"], "Graph")
        self.assertIs(manifest["text_elements"][0]["reviewed"], False)
        self.assertIsNone(manifest["text_elements"][0]["background"])
        with self.assertRaisesRegex(ValueError, "reviewed:true"):
            prepare_text_image(self.source, draft_path, self.root / "unsafe-ocr-removal.png")


if __name__ == "__main__":
    unittest.main()
