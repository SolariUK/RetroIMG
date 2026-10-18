from __future__ import annotations

from pathlib import Path

from PIL import Image

from retroimg.adjustments import adjust_colours
from retroimg.ordered import validate_dither

from retroimg.conversion_modes import get_profile_quantizer
from retroimg.geometry import resize_to_geometry
from retroimg.model import Geometry, IndexedImage
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile
from retroimg.render import render_indexed
from retroimg.display_effects import (
    DEFAULT_BLOOM_RADIUS, validate_bloom, validate_chromatic_strength,
    validate_display_brightness, validate_display_effect,
    validate_rf_strength,
)


def convert_file(
    input_path: Path,
    output_path: Path,
    *,
    profile_name: str = "teletext",
    palette_name: str | None = None,
    width: int | None = None,
    height: int | None = None,
    fit: str = "cover",
    dither: str = "none",
    bayer_size: int | None = None,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    hue_shift: float = 0.0,
    red_gain: float = 1.0,
    green_gain: float = 1.0,
    blue_gain: float = 1.0,
    scale: int = 8,
    display_effect: str = 'none',
    effect_strength: float | None = None,
    display_brightness: float = 1.0,
    bloom_strength: float = 0.0,
    bloom_radius: float = DEFAULT_BLOOM_RADIUS,
    chromatic_strength: float = 0.0,
    rf_strength: float = 0.0,
    teletext_mode: str = "bitmap",
    spectrum_mode: str = "bitmap",
    c64_mode: str = "bitmap",
    cpc_mode: str = "bitmap",
    bbc_mode: str = "bitmap",
    amiga_mode: str = "bitmap",
    atari_mode: str = "bitmap",
    megadrive_mode: str = "bitmap",
    snes_mode: str = "bitmap",
    nes_mode: str = "bitmap",
    mastersystem_mode: str = "bitmap",
    gameboy_mode: str = "bitmap",
    cga_mode: str = "bitmap",
    ega_mode: str = "bitmap",
    atari_row_height: int | None = None,
    colours: int | None = None,
) -> IndexedImage:
    validate_display_effect(display_effect, effect_strength, scale)
    validate_display_brightness(display_brightness)
    validate_bloom(bloom_strength, bloom_radius)
    validate_chromatic_strength(chromatic_strength)
    validate_rf_strength(rf_strength)
    validate_dither(dither, 4 if bayer_size is None else bayer_size)
    if bayer_size is not None and dither != "bayer":
        raise ValueError("--bayer-size requires --dither bayer")
    profile = get_profile(profile_name)
    palette = get_palette(palette_name or profile.default_palette)

    geometry = profile.geometry
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError("--width and --height must be supplied together")
        geometry = Geometry(width, height, pixel_aspect=geometry.pixel_aspect)

    if saturation <= 0:
        raise ValueError("saturation must be positive")
    quantizer = get_profile_quantizer(
        profile, teletext_mode=teletext_mode, spectrum_mode=spectrum_mode,
        c64_mode=c64_mode, cpc_mode=cpc_mode, bbc_mode=bbc_mode,
        amiga_mode=amiga_mode, atari_mode=atari_mode,
        megadrive_mode=megadrive_mode, snes_mode=snes_mode,
        nes_mode=nes_mode, mastersystem_mode=mastersystem_mode, gameboy_mode=gameboy_mode,
        cga_mode=cga_mode, ega_mode=ega_mode,
        atari_row_height=atari_row_height, colours=colours, bayer_size=bayer_size,
    )

    with Image.open(input_path) as source:
        prepared = resize_to_geometry(source, geometry, fit=fit)
        prepared = adjust_colours(
            prepared, brightness=brightness, contrast=contrast,
            saturation=saturation, hue_shift=hue_shift,
            red_gain=red_gain, green_gain=green_gain, blue_gain=blue_gain,
        )
        indexed = quantizer(prepared, palette, dither)

    preview_aspect = geometry.pixel_aspect if profile.aspect_correct_preview else 1.0
    render_indexed(indexed, scale=scale, pixel_aspect=preview_aspect,
                   display_effect=display_effect, effect_strength=effect_strength,
                   display_brightness=display_brightness,
                   bloom_strength=bloom_strength, bloom_radius=bloom_radius,
                   chromatic_strength=chromatic_strength, rf_strength=rf_strength).save(output_path)
    return indexed
