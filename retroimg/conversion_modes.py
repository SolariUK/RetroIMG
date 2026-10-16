"""Resolve profile constraint modes without target rules in the file pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from functools import partial

from PIL import Image

from retroimg.targets.atari2600 import PLAYFIELD_MODES, quantize_atari_playfield
from retroimg.targets.teletext import quantize_teletext_mosaic
from retroimg.targets.c64 import quantize_c64_multicolour
from retroimg.targets.cpc import quantize_cpc
from retroimg.targets.amiga import AMIGA_COLOUR_LIMITS, quantize_amiga, quantize_ehb, quantize_ham
from retroimg.targets.bbc import BBC_COLOUR_LIMITS, quantize_bbc
from retroimg.model import IndexedImage, Palette, TargetProfile
from retroimg.quantize import quantize
from retroimg.targets.spectrum import quantize_spectrum_attributes

Quantizer = Callable[[Image.Image, Palette, str], IndexedImage]

# These adapters accept an optional selected screen-colour count. Target
# functions validate their own supported counts and precision.
COLOUR_COUNT_QUANTIZERS = {
    (f"amiga-{resolution}", "constrained"): partial(quantize_amiga, resolution=resolution)
    for resolution in AMIGA_COLOUR_LIMITS
}

CONSTRAINED_QUANTIZERS: dict[tuple[str, str], Quantizer] = {
    **COLOUR_COUNT_QUANTIZERS,
    **{("atari2600-playfield", mode): partial(quantize_atari_playfield, mode=mode)
       for mode in PLAYFIELD_MODES},
    ("amiga-lores", "ehb"): quantize_ehb,
    ("amiga-lores", "ham"): quantize_ham,
    **{(f"bbc-mode{mode}", "constrained"): partial(quantize_bbc, mode=mode) for mode in BBC_COLOUR_LIMITS},
    ("teletext-mosaic", "mosaic"): quantize_teletext_mosaic,
    ("spectrum-attributes", "attributes"): quantize_spectrum_attributes,
    ("c64-multicolour", "multicolour"): quantize_c64_multicolour,
    **{(f"cpc-mode{mode}", "constrained"): partial(quantize_cpc, mode=mode) for mode in range(3)},
}


def get_quantizer(constraint_model: str, mode: str, *, colours: int | None = None) -> Quantizer:
    if colours is not None:
        try:
            adapter = COLOUR_COUNT_QUANTIZERS[constraint_model, mode]
        except KeyError as exc:
            raise ValueError("--colours requires a selectable screen-palette mode; for Amiga use --amiga-mode constrained") from exc
        return partial(adapter, colours=colours)
    if mode == "bitmap":
        return quantize
    try:
        return CONSTRAINED_QUANTIZERS[constraint_model, mode]
    except KeyError as exc:
        raise ValueError(f"unsupported mode {mode!r} for constraint model {constraint_model!r}") from exc


@dataclass(frozen=True)
class ModeOption:
    """CLI/API mode metadata; the target itself owns its colour rules."""

    label: str
    modes: tuple[str, ...]
    constraint_models: tuple[str, ...]
    required_profiles: str


MODE_OPTIONS = {
    "atari_mode": ModeOption("Atari", ("bitmap", *PLAYFIELD_MODES), ("atari2600-playfield",),
                             "atari2600-ntsc or atari2600-pal"),
    "amiga_mode": ModeOption("Amiga", ("bitmap", "constrained", "ehb", "ham"), ("amiga-lores", "amiga-hires"), "an amiga-* profile"),
    "bbc_mode": ModeOption("BBC", ("bitmap", "constrained"), tuple(f"bbc-mode{mode}" for mode in BBC_COLOUR_LIMITS),
                           "bbc-mode0, bbc-mode1, bbc-mode2, bbc-mode4 or bbc-mode5"),
    "teletext_mode": ModeOption("Teletext", ("bitmap", "mosaic"), ("teletext-mosaic",), "teletext"),
    "spectrum_mode": ModeOption("Spectrum", ("bitmap", "attributes"), ("spectrum-attributes",), "spectrum"),
    "c64_mode": ModeOption("C64", ("bitmap", "multicolour"), ("c64-multicolour",), "c64-multicolour"),
    "cpc_mode": ModeOption("CPC", ("bitmap", "constrained"), tuple(f"cpc-mode{mode}" for mode in range(3)),
                           "cpc-mode0, cpc-mode1 or cpc-mode2"),
}


def get_profile_quantizer(profile: TargetProfile, *, colours: int | None = None,
                          atari_row_height: int | None = None, **modes: str) -> Quantizer:
    """Validate supplied target options, then resolve a raster adapter."""
    unknown = modes.keys() - MODE_OPTIONS.keys()
    if unknown:
        raise ValueError("unknown mode options: " + ", ".join(sorted(unknown)))
    selected = "bitmap"
    for option, spec in MODE_OPTIONS.items():
        mode = modes.get(option, "bitmap")
        if mode not in spec.modes:
            raise ValueError(f"unknown {spec.label} mode: {mode}")
        if profile.constraint_model in spec.constraint_models:
            selected = mode
        elif mode != "bitmap":
            flag = option.replace("_", "-")
            raise ValueError(f"--{flag} {mode} is only valid with --profile {spec.required_profiles}")
    adapter = get_quantizer(profile.constraint_model, selected, colours=colours)
    if atari_row_height is not None:
        if profile.constraint_model != "atari2600-playfield" or selected == "bitmap":
            raise ValueError("--atari-row-height requires an Atari playfield mode")
        if type(atari_row_height) is not int or atari_row_height <= 0:
            raise ValueError("Atari row height must be a positive integer")
        adapter = partial(adapter, row_height=atari_row_height)
    return adapter
