"""Fixed-palette CGA graphics screens, without composite or raster effects."""
from dataclasses import dataclass

from retroimg.model import IndexedImage, Palette
from retroimg.palettes.cga import CGA_PALETTES, CGA_MONO, CGA_COLOUR_SELECT
from retroimg.quantize import quantize


@dataclass(frozen=True)
class CGAImage:
    width: int
    height: int
    resolution: int
    colour_select: int
    palette: Palette
    pixels: tuple[tuple[int, ...], ...]

    def __post_init__(self):
        if type(self.resolution) is not int or self.resolution not in (320, 640):
            raise ValueError('CGA resolution family must be 320 or 640')
        allowed = tuple(CGA_PALETTES.values()) if self.resolution == 320 else (CGA_MONO,)
        if self.palette not in allowed:
            raise ValueError('CGA palette does not match the resolution family')
        if (type(self.colour_select) is not int or
                self.colour_select != CGA_COLOUR_SELECT[self.palette.name]):
            raise ValueError('CGA Colour Select register must match the selected palette')
        if any(type(n) is not int or n <= 0 for n in (self.width, self.height)):
            raise ValueError('CGA dimensions must be positive integers')
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('CGA pixel grid does not match dimensions')
        if any(type(i) is not int or not 0 <= i < len(self.palette.colours) for row in self.pixels for i in row):
            raise ValueError('CGA local pixel code out of range')


def optimise_cga(image, palette, dither='none', *, resolution=320, bayer_size=4):
    if type(resolution) is not int or resolution not in (320, 640):
        raise ValueError('CGA resolution family must be 320 or 640')
    allowed = tuple(CGA_PALETTES.values()) if resolution == 320 else (CGA_MONO,)
    if palette not in allowed:
        raise ValueError('CGA constrained palette does not match the resolution family')
    indexed = quantize(image, palette, dither, bayer_size=bayer_size)
    return CGAImage(image.width, image.height, resolution, CGA_COLOUR_SELECT[palette.name], palette, indexed.pixels)


def rasterize_cga(image):
    return IndexedImage(image.width, image.height, image.palette, image.pixels)


def quantize_cga(image, palette, dither='none', *, resolution=320, bayer_size=4):
    return rasterize_cga(optimise_cga(image, palette, dither, resolution=resolution, bayer_size=bayer_size))
