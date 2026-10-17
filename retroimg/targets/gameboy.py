"""Original DMG Game Boy background shade codes and the BGP register."""
from dataclasses import dataclass

from retroimg.model import IndexedImage, Palette
from retroimg.palettes.gameboy import GAMEBOY, GAMEBOY_GREY
from retroimg.quantize import quantize


@dataclass(frozen=True)
class GameBoyImage:
    width: int
    height: int
    pixels: tuple[tuple[int, ...], ...]
    palette: Palette = GAMEBOY
    bgp: int = 0xe4

    def __post_init__(self):
        if any(type(n) is not int or n <= 0 or n % 8 for n in (self.width, self.height)):
            raise ValueError('Game Boy tile dimensions must be positive multiples of 8')
        if self.palette not in (GAMEBOY, GAMEBOY_GREY):
            raise ValueError('Game Boy tiles require gameboy or gameboy-grey palette')
        if type(self.bgp) is not int or not 0 <= self.bgp <= 255:
            raise ValueError('Game Boy BGP must be a byte')
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('Game Boy pixel grid does not match dimensions')
        if any(type(code) is not int or not 0 <= code <= 3 for row in self.pixels for code in row):
            raise ValueError('Game Boy pixel codes must be in 0..3')


def optimise_gameboy(image, palette=GAMEBOY, dither='none', *, bayer_size=4):
    if palette not in (GAMEBOY, GAMEBOY_GREY):
        raise ValueError('Game Boy tiles require gameboy or gameboy-grey palette')
    if any(n <= 0 or n % 8 for n in image.size):
        raise ValueError('Game Boy tile dimensions must be positive multiples of 8')
    # DMG codes represent luminance shades; the LCD tint is a rendering choice.
    indexed = quantize(image.convert('L').convert('RGB'), GAMEBOY_GREY, dither, bayer_size=bayer_size)
    return GameBoyImage(image.width, image.height, indexed.pixels, palette)


def rasterize_gameboy(image):
    pixels = tuple(tuple((image.bgp >> (2 * code)) & 3 for code in row) for row in image.pixels)
    return IndexedImage(image.width, image.height, image.palette, pixels)


def quantize_gameboy(image, palette, dither='none', *, bayer_size=4):
    return rasterize_gameboy(optimise_gameboy(image, palette, dither, bayer_size=bayer_size))
