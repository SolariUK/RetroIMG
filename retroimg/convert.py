from __future__ import annotations

from pathlib import Path

from PIL import Image

from retroimg.adjustments import adjust_colours

from retroimg.conversion_modes import get_profile_quantizer
from retroimg.geometry import resize_to_geometry
from retroimg.model import Geometry, IndexedImage
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile
from retroimg.render import render_indexed


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
    saturation: float = 1.0,
    hue_shift: float = 0.0,
    red_gain: float = 1.0,
    green_gain: float = 1.0,
    blue_gain: float = 1.0,
    scale: int = 8,
    teletext_mode: str = "bitmap",
    spectrum_mode: str = "bitmap",
    c64_mode: str = "bitmap",
    cpc_mode: str = "bitmap",
) -> IndexedImage:
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
        c64_mode=c64_mode, cpc_mode=cpc_mode,
    )

    with Image.open(input_path) as source:
        prepared = resize_to_geometry(source, geometry, fit=fit)
        prepared = adjust_colours(
            prepared, saturation=saturation, hue_shift=hue_shift,
            red_gain=red_gain, green_gain=green_gain, blue_gain=blue_gain,
        )
        indexed = quantizer(prepared, palette, dither)

    preview_aspect = geometry.pixel_aspect if profile.aspect_correct_preview else 1.0
    render_indexed(indexed, scale=scale, pixel_aspect=preview_aspect).save(output_path)
    return indexed
