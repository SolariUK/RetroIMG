"""Single SNES background layer: 4bpp palette-bank tiles or 8bpp indexed pixels."""
from dataclasses import dataclass

from PIL import Image

from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.constraints.palette_banks import BankedImage, fit_palette_banks, rasterize_banks
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.ordered import validate_dither
from retroimg.palettes.snes import SNES, SNES_RGB
from retroimg.quantize import quantize


def encode_colour(rgb):
    r, g, b = (SNES_RGB.levels.index(v) for v in rgb)
    return (b << 10) | (g << 5) | r


def decode_colour(value):
    if type(value) is not int or not 0 <= value <= 0x7fff:
        raise ValueError('SNES CGRAM colour must be an integer in 0..0x7fff')
    return tuple(SNES_RGB.levels[(value >> shift) & 31] for shift in (0, 5, 10))


@dataclass(frozen=True)
class SNESTileImage:
    registers: tuple[tuple[int, ...], ...]
    tiles: BankedImage

    def __post_init__(self):
        if len(self.registers) != 8 or any(len(bank) != 16 for bank in self.registers):
            raise ValueError('SNES 4bpp background requires eight 16-entry palette banks')
        decoded = tuple(tuple(decode_colour(v) for v in bank) for bank in self.registers)
        if self.tiles.tile_size != 8 or not self.tiles.shared_backdrop or decoded != self.tiles.palettes:
            raise ValueError('SNES registers must match the 8x8 tile representation')


@dataclass(frozen=True)
class SNESIndexedImage:
    """8bpp BG1 as in mode 3; slot zero resolves to the opaque backdrop.

    Excludes a second layer, direct colour, colour math and Mode 7 transforms.
    """

    width: int
    height: int
    registers: tuple[int, ...]
    pixels: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 or n % 8 for n in (self.width, self.height)):
            raise ValueError('SNES dimensions must be positive multiples of 8')
        if not 1 <= len(self.registers) <= 256:
            raise ValueError('SNES 8bpp background requires 1..256 colours')
        for value in self.registers:
            decode_colour(value)
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('SNES pixel grid does not match dimensions')
        if any(type(v) is not int or not 0 <= v < len(self.registers) for row in self.pixels for v in row):
            raise ValueError('SNES palette index out of range')


def optimise_snes_tiles(image: Image.Image, palette: Palette = SNES, dither='none', *, bayer_size=4):
    if palette != SNES:
        raise ValueError('SNES tiles mode requires the snes palette')
    tiles = fit_palette_banks(image, SNES_RGB, 8, dither=dither, bayer_size=bayer_size)
    return SNESTileImage(tuple(tuple(encode_colour(rgb) for rgb in bank) for bank in tiles.palettes), tiles)


def rasterize_snes_tiles(image: SNESTileImage):
    return rasterize_banks(image.tiles, 'snes')


def quantize_snes_tiles(image: Image.Image, palette: Palette, dither='none', *, bayer_size=4):
    return rasterize_snes_tiles(optimise_snes_tiles(image, palette, dither, bayer_size=bayer_size))


def optimise_snes_indexed(image: Image.Image, palette: Palette = SNES, dither='none', *, bayer_size=4):
    if palette != SNES:
        raise ValueError('SNES indexed mode requires the snes palette')
    validate_dither(dither, bayer_size)
    if any(n <= 0 or n % 8 for n in image.size):
        raise ValueError('SNES dimensions must be positive multiples of 8')
    selected = fit_rgb_palette(image, SNES_RGB, 256, max_samples=2048, max_iterations=6)
    screen = Palette('snes', tuple(Colour(str(i), rgb) for i, rgb in enumerate(selected)))
    indexed = quantize(image, screen, dither, bayer_size=bayer_size)
    return SNESIndexedImage(image.width, image.height, tuple(encode_colour(rgb) for rgb in selected), indexed.pixels)


def rasterize_snes_indexed(image: SNESIndexedImage):
    palette = Palette('snes', tuple(Colour(str(i), decode_colour(v)) for i, v in enumerate(image.registers)))
    return IndexedImage(image.width, image.height, palette, image.pixels)


def quantize_snes_indexed(image: Image.Image, palette: Palette, dither='none', *, bayer_size=4):
    return rasterize_snes_indexed(optimise_snes_indexed(image, palette, dither, bayer_size=bayer_size))
