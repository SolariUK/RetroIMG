"""Single Mega Drive background plane with four shared 16-entry CRAM banks."""
from dataclasses import dataclass

from PIL import Image

from retroimg.constraints.palette_banks import BankedImage, fit_palette_banks, rasterize_banks
from retroimg.model import Palette
from retroimg.palettes.megadrive import MEGADRIVE, MEGADRIVE_RGB


def encode_colour(rgb):
    r, g, b = (MEGADRIVE_RGB.levels.index(v) for v in rgb)
    return (b << 9) | (g << 5) | (r << 1)


def decode_colour(value):
    if type(value) is not int or value < 0 or value & ~0xeee:
        raise ValueError('Mega Drive CRAM colour must use only bits in 0x0eee')
    return tuple(MEGADRIVE_RGB.levels[(value >> shift) & 7] for shift in (1, 5, 9))


@dataclass(frozen=True)
class MegaDriveImage:
    """Normal-colour single plane; register zero in every bank shows the backdrop.

    Retains local codes and bank selectors without claiming VRAM packing or a
    runnable program. No sprites, shadow/highlight or mid-frame palette changes.
    """

    registers: tuple[tuple[int, ...], ...]
    tiles: BankedImage

    def __post_init__(self):
        if len(self.registers) != 4 or any(len(bank) != 16 for bank in self.registers):
            raise ValueError('Mega Drive requires four 16-entry palette banks')
        decoded = tuple(tuple(decode_colour(v) for v in bank) for bank in self.registers)
        if self.tiles.tile_size != 8 or decoded != self.tiles.palettes:
            raise ValueError('Mega Drive registers must match the 8x8 tile representation')


def optimise_megadrive(image: Image.Image, palette: Palette = MEGADRIVE, dither='none', *, bayer_size=4):
    if palette != MEGADRIVE:
        raise ValueError('Mega Drive tiles mode requires the megadrive palette')
    tiles = fit_palette_banks(image, MEGADRIVE_RGB, 4, dither=dither, bayer_size=bayer_size)
    return MegaDriveImage(tuple(tuple(encode_colour(rgb) for rgb in bank) for bank in tiles.palettes), tiles)


def rasterize_megadrive(image: MegaDriveImage):
    return rasterize_banks(image.tiles, 'megadrive')


def quantize_megadrive(image: Image.Image, palette: Palette, dither='none', *, bayer_size=4):
    return rasterize_megadrive(optimise_megadrive(image, palette, dither, bayer_size=bayer_size))
