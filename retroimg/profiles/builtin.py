from __future__ import annotations

from retroimg.model import Geometry, TargetProfile

# Teletext mosaic graphics: 40x25 character cells, each graphics cell 2x3 subcells.
TELETEXT = TargetProfile(
    name="teletext",
    geometry=Geometry(80, 75, pixel_aspect=1.0),
    default_palette="teletext",
    description="Teletext/Ceefax mosaic graphics logical raster (80x75).",
    constraint_model="teletext-mosaic",
)

C64 = TargetProfile(
    name="c64-hires",
    geometry=Geometry(320, 200, pixel_aspect=1.2),
    default_palette="c64",
    description="Commodore 64 high-resolution bitmap geometry.",
    constraint_model="c64-hires",
)

C64_MULTICOLOUR = TargetProfile(
    name="c64-multicolour",
    geometry=Geometry(160, 200, pixel_aspect=2.0),
    default_palette="c64",
    description="C64 multicolour bitmap geometry with wide pixels (160x200).",
    constraint_model="c64-multicolour",
    aspect_correct_preview=True,
)

SPECTRUM = TargetProfile(
    name="spectrum",
    geometry=Geometry(256, 192, pixel_aspect=1.0),
    default_palette="spectrum",
    description="ZX Spectrum display geometry.",
    constraint_model="spectrum-attributes",
)

CPC_PROFILES = tuple(
    TargetProfile(
        name=f"cpc-mode{mode}",
        geometry=Geometry(width, 200, pixel_aspect=aspect),
        default_palette="cpc",
        description=f"Amstrad CPC mode {mode} geometry ({width}x200, {limit}-ink hardware limit).",
        constraint_model=f"cpc-mode{mode}",
        aspect_correct_preview=True,
    )
    for mode, width, aspect, limit in ((0, 160, 2.0, 16), (1, 320, 1.0, 4), (2, 640, 0.5, 2))
)

BBC_PROFILES = tuple(
    TargetProfile(
        name=f"bbc-mode{mode}",
        geometry=Geometry(width, 256, pixel_aspect=aspect),
        default_palette="bbc",
        description=f"BBC Micro mode {mode} geometry ({width}x256, {limit} steady colours).",
        constraint_model=f"bbc-mode{mode}",
        aspect_correct_preview=True,
    )
    for mode, width, aspect, limit in (
        (0, 640, 0.5, 2), (1, 320, 1.0, 4), (2, 160, 2.0, 8),
        (4, 320, 1.0, 2), (5, 160, 2.0, 4),
    )
)

PROFILES = {p.name: p for p in (TELETEXT, C64, C64_MULTICOLOUR, SPECTRUM, *CPC_PROFILES, *BBC_PROFILES)}


def get_profile(name: str) -> TargetProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown profile: {name}") from exc
