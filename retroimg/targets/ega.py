"""EGA single screens: RGBI in 200 lines, selected RGB6 in 350 lines."""
from dataclasses import dataclass

from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.ordered import validate_dither
from retroimg.palettes.ega import EGA, EGA_DEFAULT, EGA_RGB
from retroimg.quantize import quantize


def encode_colour(rgb):
    r, g, b = (EGA_RGB.levels.index(v) for v in rgb)
    return ((r >> 1) << 2) | ((g >> 1) << 1) | (b >> 1) | ((r & 1) << 5) | ((g & 1) << 4) | ((b & 1) << 3)


def decode_colour(value):
    if type(value) is not int or not 0 <= value <= 63:
        raise ValueError('EGA palette register must be in 0..63')
    return tuple(170 * ((value >> primary) & 1) + 85 * ((value >> secondary) & 1)
                 for primary, secondary in ((2, 5), (1, 4), (0, 3)))


@dataclass(frozen=True)
class EGAImage:
    width: int
    height: int
    scanlines: int
    registers: tuple[int, ...]
    pixels: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        if type(self.scanlines) is not int or self.scanlines not in (200, 350):
            raise ValueError('EGA scanline family must be 200 or 350')
        if not 1 <= len(self.registers) <= 16 or len(set(self.registers)) != len(self.registers):
            raise ValueError('EGA requires at most sixteen unique palette registers')
        colours = tuple(decode_colour(v) for v in self.registers)
        if self.scanlines == 200 and not set(colours) <= set(EGA_DEFAULT.rgb_values()):
            raise ValueError('EGA 200-line screens require the standard RGBI colours')
        if any(type(n) is not int or n <= 0 for n in (self.width, self.height)):
            raise ValueError('EGA dimensions must be positive integers')
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('EGA pixel grid does not match dimensions')
        if any(type(i) is not int or not 0 <= i < len(self.registers) for row in self.pixels for i in row):
            raise ValueError('EGA local pixel code out of range')


def optimise_ega(image, palette, dither='none', *, scanlines=350, bayer_size=4):
    validate_dither(dither, bayer_size)
    if type(scanlines) is not int or scanlines not in (200, 350):
        raise ValueError('EGA scanline family must be 200 or 350')
    allowed = (EGA_DEFAULT,) if scanlines == 200 else (EGA, EGA_DEFAULT)
    if palette not in allowed:
        raise ValueError('EGA constrained palette does not match the scanline family')
    if palette == EGA_DEFAULT:
        selected = palette.rgb_values()
    else:
        selected = fit_rgb_palette(image, EGA_RGB, 16, max_samples=1024, max_iterations=6)
    screen = Palette('ega', tuple(Colour(str(i), rgb) for i, rgb in enumerate(selected)))
    indexed = quantize(image, screen, dither, bayer_size=bayer_size)
    return EGAImage(image.width, image.height, scanlines, tuple(encode_colour(rgb) for rgb in selected), indexed.pixels)


def rasterize_ega(image):
    palette = Palette('ega', tuple(Colour(str(i), decode_colour(v)) for i, v in enumerate(image.registers)))
    return IndexedImage(image.width, image.height, palette, image.pixels)


def quantize_ega(image, palette, dither='none', *, scanlines=350, bayer_size=4):
    return rasterize_ega(optimise_ega(image, palette, dither, scanlines=scanlines, bayer_size=bayer_size))
