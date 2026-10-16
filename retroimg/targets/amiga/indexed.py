"""Standard OCS/ECS indexed screens; independent of bitplane/file encoding."""
from dataclasses import dataclass

from PIL import Image

from retroimg.ordered import validate_dither

from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.builtin import AMIGA, AMIGA_RGB
from retroimg.quantize import quantize

AMIGA_COLOUR_LIMITS = {'lores': 32, 'hires': 16}


def _colour_count(resolution: str, colours: int | None) -> int:
    if resolution not in AMIGA_COLOUR_LIMITS:
        raise ValueError('Amiga resolution must be lores or hires')
    if colours is None:
        return AMIGA_COLOUR_LIMITS[resolution]
    if type(colours) is not int or colours not in (2, 4, 8, 16, 32) or colours > AMIGA_COLOUR_LIMITS[resolution]:
        raise ValueError(f'Amiga {resolution} colours must be 2, 4, 8, 16' + (', or 32' if resolution == 'lores' else ''))
    return colours


@dataclass(frozen=True)
class AmigaImage:
    """Pixel values select registers holding 12-bit 0xRGB hardware colours.

    The register table may use fewer entries than its bitplane capacity.
    Custom dimensions are permitted. EHB, HAM, sprites and Copper palette
    changes need separate models and are not encoded here.
    """

    width: int
    height: int
    resolution: str
    bitplanes: int
    registers: tuple[int, ...]
    pixels: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        if type(self.bitplanes) is not int or not 1 <= self.bitplanes <= 5:
            raise ValueError('Amiga bitplanes must be an integer in 1..5')
        limit = _colour_count(self.resolution, 1 << self.bitplanes)
        if any(type(size) is not int or size <= 0 for size in (self.width, self.height)):
            raise ValueError('Amiga dimensions must be positive integers')
        if not 1 <= len(self.registers) <= limit:
            raise ValueError('Amiga register count exceeds mode limit or is empty')
        if any(type(value) is not int or not 0 <= value <= 0xfff for value in self.registers):
            raise ValueError('Amiga register colours must be integers in 0x000..0xfff')
        if len(set(self.registers)) != len(self.registers):
            raise ValueError('Amiga register colours must be unique')
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('Amiga pixel grid does not match dimensions')
        if any(type(pixel) is not int or not 0 <= pixel < len(self.registers) for row in self.pixels for pixel in row):
            raise ValueError('Amiga register index out of range')

    @property
    def palette(self) -> Palette:
        return Palette('amiga', tuple(AMIGA.colours[value] for value in self.registers),
                       'Selected OCS/ECS screen register colours.')


def optimise_amiga(
    image: Image.Image, palette: Palette = AMIGA, dither: str = 'none', *,
    resolution: str = 'lores', colours: int | None = None, bayer_size: int = 4,
) -> AmigaImage:
    limit = _colour_count(resolution, colours)
    if palette != AMIGA:
        raise ValueError('Amiga constrained mode requires the amiga palette')
    validate_dither(dither, bayer_size)
    selected = fit_rgb_palette(image, AMIGA_RGB, limit)
    registers = tuple(AMIGA_RGB.nearest_index(rgb) for rgb in selected)
    screen_palette = Palette('amiga', tuple(AMIGA.colours[value] for value in registers))
    indexed = quantize(image, screen_palette, dither, bayer_size=bayer_size)
    return AmigaImage(image.width, image.height, resolution, limit.bit_length() - 1, registers, indexed.pixels)


def rasterize_amiga(image: AmigaImage) -> IndexedImage:
    return IndexedImage(image.width, image.height, image.palette, image.pixels)


def quantize_amiga(
    image: Image.Image, palette: Palette, dither: str = 'none', *,
    resolution: str = 'lores', colours: int | None = None, bayer_size: int = 4,
) -> IndexedImage:
    return rasterize_amiga(optimise_amiga(image, palette, dither, resolution=resolution, colours=colours, bayer_size=bayer_size))
