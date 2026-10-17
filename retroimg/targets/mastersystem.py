"""Master System Mode 4 background tiles; all sixteen entries in either bank are usable."""
from dataclasses import dataclass

from retroimg.constraints.palette_banks import BankedImage, fit_palette_banks, rasterize_banks
from retroimg.palettes.mastersystem import MASTERSYSTEM, MASTERSYSTEM_RGB


def encode_colour(rgb):
    r, g, b = (MASTERSYSTEM_RGB.levels.index(v) for v in rgb)
    return (b << 4) | (g << 2) | r


def decode_colour(code):
    if type(code) is not int or not 0 <= code <= 63:
        raise ValueError('Master System CRAM colour must be in 0..63')
    return tuple(MASTERSYSTEM_RGB.levels[(code >> shift) & 3] for shift in (0, 2, 4))


@dataclass(frozen=True)
class MasterSystemImage:
    registers: tuple[tuple[int, ...], ...]
    tiles: BankedImage

    def __post_init__(self):
        if len(self.registers) != 2 or any(len(bank) != 16 for bank in self.registers):
            raise ValueError('Master System requires two sixteen-entry palettes')
        decoded = tuple(tuple(decode_colour(code) for code in bank) for bank in self.registers)
        if self.tiles.tile_size != 8 or self.tiles.shared_backdrop or decoded != self.tiles.palettes:
            raise ValueError('Master System palettes must match opaque 8x8 background tiles')


def optimise_mastersystem(image, palette=MASTERSYSTEM, dither='none', *, bayer_size=4):
    if palette != MASTERSYSTEM:
        raise ValueError('Master System tiles mode requires the mastersystem palette')
    tiles = fit_palette_banks(image, MASTERSYSTEM_RGB, 2, shared_backdrop=False,
                              dither=dither, bayer_size=bayer_size)
    registers = tuple(tuple(encode_colour(rgb) for rgb in bank) for bank in tiles.palettes)
    return MasterSystemImage(registers, tiles)


def rasterize_mastersystem(image):
    return rasterize_banks(image.tiles, 'mastersystem')


def quantize_mastersystem(image, palette, dither='none', *, bayer_size=4):
    return rasterize_mastersystem(optimise_mastersystem(image, palette, dither, bayer_size=bayer_size))
