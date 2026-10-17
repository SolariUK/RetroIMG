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

# Nominal active picture sizes, displayed at 4:3. Playfield adapters group
# four colour clocks horizontally without changing the bitmap profile.
ATARI_PROFILES = tuple(
    TargetProfile(
        name=f"atari2600-{standard}",
        geometry=Geometry(160, height, pixel_aspect=height / 120),
        default_palette=f"atari2600-{standard}",
        description=f"Atari 2600 {standard.upper()} nominal active picture (160x{height}).",
        constraint_model="atari2600-playfield",
        aspect_correct_preview=True,
    )
    for standard, height in (("ntsc", 192), ("pal", 228))
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

AMIGA_PROFILES = tuple(
    TargetProfile(
        name=f"amiga-{resolution}{suffix}",
        geometry=Geometry(width, height, pixel_aspect=aspect),
        default_palette="amiga",
        description=f"Amiga OCS/ECS {standard} {resolution} ({width}x{height}, up to {limit} selected colours).",
        constraint_model=f"amiga-{resolution}",
        aspect_correct_preview=True,
    )
    for standard, height, suffix in (("PAL", 256, ""), ("NTSC", 200, "-ntsc"))
    for resolution, width, aspect, limit in (("lores", 320, 1.0, 32), ("hires", 640, 0.5, 16))
)

MEGADRIVE_PROFILES = tuple(
    TargetProfile(
        name=f'megadrive-{width}{suffix}',
        geometry=Geometry(width, height, pixel_aspect=height * 4 / (width * 3)),
        default_palette='megadrive',
        description=f'Mega Drive/Genesis {width}x{height}; normal colour, single background plane.',
        constraint_model='megadrive-tiles',
        aspect_correct_preview=True,
    )
    for height, suffix in ((224, ''), (240, '-pal')) for width in (320, 256)
)

SNES_PROFILE = TargetProfile(
    name='snes', geometry=Geometry(256, 224, pixel_aspect=7 / 6),
    default_palette='snes', description='SNES 256x224; single 4bpp or 8bpp background layer.',
    constraint_model='snes-background', aspect_correct_preview=True,
)

NES_PROFILE = TargetProfile(
    name='nes', geometry=Geometry(256, 240, pixel_aspect=1.25), default_palette='nes',
    description='NES 256x240; one palette per 16x16 background attribute region.',
    constraint_model='nes-attributes', aspect_correct_preview=True,
)
MASTERSYSTEM_PROFILES = tuple(TargetProfile(
    name=f'mastersystem{suffix}', geometry=Geometry(256, height, pixel_aspect=height / 192),
    default_palette='mastersystem', description=f'Master System Mode 4 256x{height}; two 16-colour tile palettes.',
    constraint_model='mastersystem-tiles', aspect_correct_preview=True,
) for height, suffix in ((192, ''), (224, '-224'), (240, '-240')))
GAMEBOY_PROFILE = TargetProfile(
    name='gameboy', geometry=Geometry(160, 144), default_palette='gameboy',
    description='Original monochrome Game Boy 160x144; four background shades.',
    constraint_model='gameboy-tiles',
)

CGA_PROFILES = tuple(TargetProfile(
    name=f'cga-{width}', geometry=Geometry(width, 200, pixel_aspect=800 / (width * 3)),
    default_palette='cga-pal1-high' if width == 320 else 'cga-mono',
    description=f'CGA {width}x200; ' + ('four-colour RGBI palette combinations.' if width == 320 else 'two-colour monochrome graphics.'),
    constraint_model=f'cga-{width}', aspect_correct_preview=True,
) for width in (320, 640))
EGA_PROFILES = tuple(TargetProfile(
    name=name, geometry=Geometry(width, height, pixel_aspect=height * 4 / (width * 3)),
    default_palette='ega-default' if height == 200 else 'ega',
    description=f'EGA {width}x{height}; ' + ('sixteen standard RGBI colours.' if height == 200 else 'sixteen selected RGB6 colours.'),
    constraint_model=f'ega-{height}', aspect_correct_preview=True,
) for name, width, height in (('ega-320', 320, 200), ('ega-640-200', 640, 200), ('ega-640', 640, 350)))

PROFILES = {p.name: p for p in (TELETEXT, C64, C64_MULTICOLOUR, SPECTRUM, *CPC_PROFILES, *BBC_PROFILES, *AMIGA_PROFILES, *ATARI_PROFILES, *MEGADRIVE_PROFILES, SNES_PROFILE, NES_PROFILE, *MASTERSYSTEM_PROFILES, GAMEBOY_PROFILE, *CGA_PROFILES, *EGA_PROFILES)}


def get_profile(name: str) -> TargetProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown profile: {name}") from exc
