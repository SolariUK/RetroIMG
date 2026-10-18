"""Shared presentation choices for terminal and desktop frontends."""
from retroimg.conversion_modes import CONSTRAINED_QUANTIZERS, MODE_OPTIONS
from retroimg.model import TargetProfile
from retroimg.palettes import PALETTES
from retroimg.profiles import PROFILES
from retroimg.settings import CONSTRAINT_PALETTES, REQUIRED_PALETTES

FAMILY_LABELS = {
    'teletext': 'Teletext', 'spectrum': 'ZX Spectrum', 'c64': 'Commodore 64',
    'cpc': 'Amstrad CPC', 'bbc': 'BBC Micro', 'amiga': 'Amiga', 'atari2600': 'Atari 2600',
    'megadrive': 'Sega Mega Drive / Genesis', 'snes': 'Super Nintendo / SNES',
    'nes': 'Nintendo / NES', 'mastersystem': 'Sega Master System', 'gameboy': 'Original Game Boy',
    'cga': 'IBM CGA', 'ega': 'IBM EGA',
}
MODE_HELP = {
    'bitmap': 'unrestricted palette conversion',
    'tiles': '8x8 tiles, each selecting one shared 16-entry palette bank and backdrop',
    'indexed': 'up to 256 image-selected colours for one 8bpp background layer',
    'mosaic': 'two colours per 2x3 cell',
    'attributes': 'ink/paper with shared brightness per 8x8 cell',
    'multicolour': 'shared background plus three local colours per 4x8 cell',
    'constrained': 'apply this display mode\'s screen-colour limit',
    'ehb': '32 base colours and their linked half-bright colours (lores)',
    'ham': 'HAM6: base colours and changes to the held colour (lores)',
    'playfield': '40 independent blocks with two colours per band',
    'repeat': '20 playfield blocks repeated in the right half',
    'mirror': '20 playfield blocks mirrored in the right half',
}


def mode_label(mode: str) -> str:
    """Consistent editing choices; CLI/preset mode identifiers stay stable."""
    if mode == 'bitmap':
        return 'Palette only'
    variants = {
        'indexed': '256 colours', 'ehb': 'EHB', 'ham': 'HAM6',
        'playfield': 'playfield', 'repeat': 'repeated playfield',
        'mirror': 'mirrored playfield',
    }
    variant = variants.get(mode)
    return 'Hardware constrained' + (f' ({variant})' if variant else '')


def mode_description(option: str | None, mode: str) -> str:
    overrides = {
        ('c64_mode', 'hires'): 'two independent C64 colours per 8x8 cell; no shared background colour',
        ('nes_mode', 'attributes'): 'four shared palettes, three local colours plus backdrop per 16x16 region',
        ('mastersystem_mode', 'tiles'): '8x8 tiles selecting either of two 16-colour palettes; all slots usable',
        ('gameboy_mode', 'tiles'): 'four luminance shades, retained 2-bit codes; green or grey preview',
        ('cga_mode', 'constrained'): 'standard four-colour palettes at 320x200, monochrome at 640x200',
        ('ega_mode', 'constrained'): 'sixteen RGBI colours in 200 lines, or sixteen selected RGB6 colours in 350 lines',
    }
    return overrides.get((option, mode), MODE_HELP.get(mode, mode))


def suggested_scale(profile: TargetProfile, width: int | None = None, height: int | None = None,
                    *, minimum: int = 1, maximum: int = 8) -> int:
    """Choose integer enlargement toward a 640-pixel, aspect-correct output.

    Never shrink the logical raster. Surface effects can require a minimum
    enlargement that exceeds the size target.
    """
    geometry = profile.geometry
    width = geometry.width if width is None else width
    height = geometry.height if height is None else height
    aspect = geometry.pixel_aspect if profile.aspect_correct_preview else 1
    longest = max(width * max(1, aspect), height * max(1, 1 / aspect))
    return max(minimum, min(maximum, int(640 // longest)))



def profile_families() -> dict[str, tuple[TargetProfile, ...]]:
    families: dict[str, list[TargetProfile]] = {}
    for profile in PROFILES.values():
        families.setdefault(profile.name.split('-', 1)[0], []).append(profile)
    return {name: tuple(families[name]) for name in
            sorted(families, key=lambda name: FAMILY_LABELS.get(name, name).casefold())}


def profile_modes(profile: TargetProfile) -> tuple[str | None, tuple[str, ...]]:
    for option, spec in MODE_OPTIONS.items():
        if profile.constraint_model in spec.constraint_models:
            modes = tuple(mode for mode in spec.modes if mode == 'bitmap'
                          or (profile.constraint_model, mode) in CONSTRAINED_QUANTIZERS)
            return option, modes
    return None, ('bitmap',)


def preferred_mode(modes: tuple[str, ...]) -> str:
    """New GUI selections start with the first hardware-constrained option."""
    return next((mode for mode in modes if mode != 'bitmap'), 'bitmap')


def palette_choices(profile: TargetProfile, mode: str, option: str | None) -> tuple[str, ...]:
    names = (CONSTRAINT_PALETTES.get(profile.constraint_model, REQUIRED_PALETTES.get(option, tuple(PALETTES))) if mode != 'bitmap'
             else tuple(PALETTES))
    return tuple(sorted(names, key=lambda name: (name != profile.default_palette, name)))

