"""NES single background plane: one of four palettes per 16x16 attribute region."""
from dataclasses import dataclass

from retroimg.constraints.palette_banks import BankedImage, fit_palette_banks, rasterize_banks
from retroimg.palettes.nes import NES, NES_SAFE, NES_SAFE_CODES


@dataclass(frozen=True)
class NESImage:
    registers: tuple[tuple[int, ...], ...]
    attributes: BankedImage

    def __post_init__(self):
        if len(self.registers) != 4 or any(len(bank) != 4 for bank in self.registers):
            raise ValueError('NES requires four four-entry background palettes')
        if any(type(code) is not int or code not in NES_SAFE_CODES for bank in self.registers for code in bank):
            raise ValueError('NES palette code must be in 0..63 excluding $0D')
        decoded = tuple(tuple(NES.colours[code].rgb for code in bank) for bank in self.registers)
        if (self.attributes.tile_size != 16 or not self.attributes.shared_backdrop
                or decoded != self.attributes.palettes):
            raise ValueError('NES palettes must match shared-backdrop 16x16 attributes')


def optimise_nes(image, palette=NES, dither='none', *, bayer_size=4):
    if palette != NES:
        raise ValueError('NES attributes mode requires the nes palette')
    attributes = fit_palette_banks(image, None, 4, slots=4, tile_size=16, palette=NES_SAFE,
                                   dither=dither, bayer_size=bayer_size)
    codes = {NES.colours[i].rgb: i for i in reversed(NES_SAFE_CODES)}
    registers = tuple(tuple(codes[rgb] for rgb in bank) for bank in attributes.palettes)
    return NESImage(registers, attributes)


def rasterize_nes(image):
    return rasterize_banks(image.attributes, 'nes')


def quantize_nes(image, palette, dither='none', *, bayer_size=4):
    return rasterize_nes(optimise_nes(image, palette, dither, bayer_size=bayer_size))
