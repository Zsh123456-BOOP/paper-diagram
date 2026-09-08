"""Small integration checks for the local raster-to-path contract."""

from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

from cell_local.vectorize import vectorize_image

try:
    import cairosvg
except (ImportError, OSError) as exc:
    cairosvg = None
    CAIRO_SKIP_REASON = f"Optional pixel preview requires CairoSVG and native Cairo: {exc}"
else:
    CAIRO_SKIP_REASON = ""


class VectorizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def fixture(self, name="input.png"):
        image = Image.new("RGB", (128, 96), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((8, 8, 48, 38), fill="#96b7d6", outline="black")
        draw.ellipse((68, 8, 94, 34), fill="#ffbc00", outline="black")
        draw.line((8, 52, 115, 52), fill="black", width=1)
        draw.polygon([(115, 52), (108, 48), (108, 56)], fill="black")
        draw.rectangle((20, 68, 44, 88), fill="black")
        draw.rectangle((27, 73, 37, 83), fill="white")
        draw.rectangle((80, 80, 81, 81), fill="black")
        path = self.directory / name
        image.save(path)
        return path

    def render(self, path):
        return Image.open(io.BytesIO(cairosvg.svg2png(url=str(path)))).convert("RGB")

    def alpha_fixture(self):
        source = self.directory / "alpha.png"
        image = Image.new("RGBA", (32, 24), (17, 43, 87, 0))
        ImageDraw.Draw(image).rectangle((8, 6, 23, 17), fill=(255, 0, 0, 128))
        image.save(source)
        return source

    def test_paths_and_canvas_contract(self):
        source = self.fixture()
        output = self.directory / "result.svg"
        info = vectorize_image(source, output)
        root = ET.parse(output).getroot()
        self.assertEqual(root.attrib["viewBox"], "0 0 128 96")
        self.assertEqual(info["original_size"], [128, 96])
        self.assertGreater(info["path_count"], 5)
        self.assertEqual(info["embedded_raster_count"], 0)
        self.assertTrue(all(n.tag.rsplit("}", 1)[-1] in {"svg", "g", "path"} for n in root.iter()))

    @unittest.skipIf(cairosvg is None, CAIRO_SKIP_REASON)
    def test_rendered_hole_thin_line_and_small_dot(self):
        source = self.fixture()
        output = self.directory / "result.svg"
        vectorize_image(source, output)
        rendered = self.render(output)
        self.assertEqual(rendered.size, (128, 96))
        self.assertLess(sum(rendered.getpixel((60, 52))) / 3, 150)
        self.assertGreater(min(rendered.getpixel((32, 78))), 240)
        self.assertLess(sum(rendered.getpixel((80, 80))) / 3, 180)

    def test_output_is_deterministic(self):
        source = self.fixture()
        first, second = self.directory / "a.svg", self.directory / "b.svg"
        vectorize_image(source, first, preset="balanced")
        vectorize_image(source, second, preset="balanced")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_empty_engine_paths_are_removed_but_small_dots_survive(self):
        source = self.fixture()
        output = self.directory / "empty-path.svg"
        engine_output = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="384">'
            '<path d="" fill="#808080" />'
            '<path d="M0,0 L512,0 L512,384 L0,384 Z" fill="#fff" />'
            '<path d="M10,10 L11,10 L11,11 L10,11 Z" fill="#000" />'
            '</svg>'
        )
        with patch("vtracer.convert_raw_image_to_svg", return_value=engine_output):
            info = vectorize_image(source, output)
        self.assertEqual(info["discarded_empty_path_count"], 1)
        self.assertEqual(info["path_count"], 2)
        self.assertTrue(all(path.get("d", "").strip() for path in ET.parse(output).iter("{http://www.w3.org/2000/svg}path")))

    def test_transparent_pixels_get_documented_white_matte(self):
        source = self.alpha_fixture()
        output = self.directory / "alpha.svg"
        info = vectorize_image(source, output)
        self.assertEqual(info["alpha_handling"], "composited-on-white")
        self.assertTrue(info["input_has_transparency"])
        self.assertEqual(info["matte_color"], "#ffffff")

    @unittest.skipIf(cairosvg is None, CAIRO_SKIP_REASON)
    def test_rendered_transparency_matches_white_matte(self):
        source = self.alpha_fixture()
        output = self.directory / "alpha.svg"
        vectorize_image(source, output)
        rendered = self.render(output)
        # Tracing averages each color region; allow a small quantization error.
        self.assertGreaterEqual(min(rendered.getpixel((0, 0))), 252)
        self.assertLess(max(abs(a - b) for a, b in zip(rendered.getpixel((16, 12)), (255, 127, 127))), 5)

    def test_png_jpeg_webp_have_identical_canvas_contract(self):
        for extension in ("png", "jpg", "webp"):
            with self.subTest(extension=extension):
                source = self.fixture("source." + extension)
                info = vectorize_image(source, self.directory / (extension + ".svg"), "balanced")
                self.assertEqual((info["width"], info["height"]), (128, 96))

    def test_exif_orientation(self):
        source = self.directory / "orientation.jpg"
        image = Image.new("RGB", (16, 24), "white")
        exif = image.getexif()
        exif[274] = 6
        image.save(source, exif=exif)
        info = vectorize_image(source, self.directory / "orientation.svg", "balanced")
        self.assertEqual(info["original_size"], [16, 24])
        self.assertEqual((info["width"], info["height"]), (24, 16))
        self.assertTrue(info["exif_orientation_applied"])

    def test_clear_failures_do_not_overwrite_input(self):
        source = self.fixture()
        original = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "different files"):
            vectorize_image(source, source)
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "Unknown preset"):
            vectorize_image(source, self.directory / "bad.svg", "unknown")
        with self.assertRaises(FileNotFoundError):
            vectorize_image(self.directory / "missing.png", self.directory / "bad.svg")
        corrupt = self.directory / "corrupt.png"
        corrupt.write_text("not an image")
        with self.assertRaisesRegex(ValueError, "Cannot decode"):
            vectorize_image(corrupt, self.directory / "bad.svg")


if __name__ == "__main__":
    unittest.main()
