from __future__ import annotations

from pathlib import Path

from PIL import Image

from retroimg.adjustments import adjust_colours

from retroimg.conversion_modes import get_quantizer
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
    if teletext_mode not in {"bitmap", "mosaic"}:
        raise ValueError(f"unknown Teletext mode: {teletext_mode}")
    if profile_name != "teletext" and teletext_mode != "bitmap":
        raise ValueError("--teletext-mode mosaic is only valid with --profile teletext")

    if spectrum_mode not in {"bitmap", "attributes"}:
        raise ValueError(f"unknown Spectrum mode: {spectrum_mode}")
    if profile.constraint_model != "spectrum-attributes" and spectrum_mode != "bitmap":
        raise ValueError("--spectrum-mode attributes is only valid with --profile spectrum")

    if c64_mode not in {"bitmap", "multicolour"}:
        raise ValueError(f"unknown C64 mode: {c64_mode}")
    if profile.constraint_model != "c64-multicolour" and c64_mode != "bitmap":
        raise ValueError("--c64-mode multicolour is only valid with --profile c64-multicolour")

    cpc_models = {f"cpc-mode{mode}" for mode in range(3)}
    if cpc_mode not in {"bitmap", "constrained"}:
        raise ValueError(f"unknown CPC mode: {cpc_mode}")
    if profile.constraint_model not in cpc_models and cpc_mode != "bitmap":
        raise ValueError("--cpc-mode constrained is only valid with --profile cpc-mode0, cpc-mode1 or cpc-mode2")

    modes = {"teletext-mosaic": teletext_mode, "spectrum-attributes": spectrum_mode,
             "c64-multicolour": c64_mode, **{model: cpc_mode for model in cpc_models}}
    quantizer = get_quantizer(profile.constraint_model, modes.get(profile.constraint_model, "bitmap"))

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
