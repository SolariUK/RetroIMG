import unittest
from itertools import combinations_with_replacement
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from retroimg.constraints import quantize_teletext_mosaic
from retroimg.convert import convert_file
from retroimg.model import Colour, Palette
from retroimg.palettes import get_palette
from retroimg.quantize import colour_distance, quantize


class MosaicTests(unittest.TestCase):
    def test_source_fit_beats_prequantized_fit(self):
        palette = Palette("grey", tuple(Colour(str(v), (v, v, v)) for v in (0, 100, 255)))
        source = Image.new("RGB", (2, 3))
        source.putdata([(v, v, v) for v in (0, 45, 45, 45, 170, 255)])
        result = quantize_teletext_mosaic(source, palette)
        values = palette.rgb_values()
        samples = [source.getpixel((x, y)) for y in range(3) for x in range(2)]
        error = sum(colour_distance(sample, values[index])
                    for sample, index in zip(samples, sum(result.pixels, ())))
        optimum = min(sum(min(colour_distance(sample, values[a]),
                              colour_distance(sample, values[b])) for sample in samples)
                      for a, b in combinations_with_replacement(range(len(values)), 2))
        self.assertEqual(error, optimum)
        from retroimg.constraints import constrain_teletext_mosaic
        old = constrain_teletext_mosaic(quantize(source, palette))
        old_error = sum(colour_distance(sample, values[index])
                        for sample, index in zip(samples, sum(old.pixels, ())))
        self.assertLess(error, old_error)

    def test_dither_respects_cells_and_is_deterministic(self):
        palette = get_palette("teletext")
        source = Image.new("RGB", (4, 6))
        source.putdata([((i * 43) % 256, (i * 97) % 256, (i * 19) % 256) for i in range(24)])
        for dither in ("none", "floyd-steinberg"):
            result = quantize_teletext_mosaic(source, palette, dither)
            self.assertEqual(result, quantize_teletext_mosaic(source, palette, dither))
            for y in (0, 3):
                for x in (0, 2):
                    colours = {result.pixels[y + dy][x + dx] for dy in range(3) for dx in range(2)}
                    self.assertLessEqual(len(colours), 2)

    def test_conversion_preserves_bitmap_and_uses_source_for_mosaic(self):
        source = Image.new("RGB", (2, 3))
        source.putdata([(10, 90, 140), (220, 50, 20), (40, 200, 80)] * 2)
        palette = get_palette("teletext")
        with TemporaryDirectory() as directory:
            src, dst = Path(directory) / "in.png", Path(directory) / "out.png"
            source.save(src)
            for dither in ("none", "floyd-steinberg"):
                args = dict(width=2, height=3, scale=1, dither=dither)
                bitmap = convert_file(src, dst, **args)
                self.assertEqual(bitmap, quantize(source, palette, dither))
                mosaic = convert_file(src, dst, teletext_mode="mosaic", **args)
                self.assertEqual(mosaic, quantize_teletext_mosaic(source, palette, dither))
