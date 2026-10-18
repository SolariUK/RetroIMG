"""CLI settings validation and presentation hints, separate from conversion."""
import math

from retroimg.conversion_modes import (
    COLOUR_COUNT_QUANTIZERS, CONSTRAINED_QUANTIZERS, MODE_OPTIONS, get_profile_quantizer,
)
from retroimg.ordered import BAYER_SIZES, DITHER_MODES
from retroimg.palettes import PALETTES
from retroimg.profiles import PROFILES
from retroimg.targets.amiga import AMIGA_COLOUR_LIMITS
from retroimg.display_effects import (
    DEFAULT_BLOOM_RADIUS, validate_bloom, validate_chromatic_strength,
    validate_display_brightness, validate_display_effect,
    validate_rf_strength,
)

REQUIRED_PALETTES = {
    'spectrum_mode': ('spectrum',), 'c64_mode': ('c64',), 'cpc_mode': ('cpc',),
    'bbc_mode': ('bbc',), 'amiga_mode': ('amiga',),
    'atari_mode': ('atari2600-ntsc', 'atari2600-pal'),
    'megadrive_mode': ('megadrive',), 'snes_mode': ('snes',),
    'nes_mode': ('nes',), 'mastersystem_mode': ('mastersystem',),
    'gameboy_mode': ('gameboy', 'gameboy-grey'),
}
CONSTRAINT_PALETTES = {
    'cga-320': tuple(f'cga-pal{number}-{intensity}' for number in (0, 1) for intensity in ('low', 'high')),
    'cga-640': ('cga-mono',),
    'ega-200': ('ega-default',),
    'ega-350': ('ega', 'ega-default'),
}
CELL_DIMENSIONS = {
    'teletext-mosaic': (2, 3), 'spectrum-attributes': (8, 8), 'c64-hires': (8, 8), 'c64-multicolour': (4, 8),
    'megadrive-tiles': (8, 8), 'snes-background': (8, 8),
    'nes-attributes': (16, 16), 'mastersystem-tiles': (8, 8), 'gameboy-tiles': (8, 8),
}
INTEGER_OPTIONS = {'width', 'height', 'scale', 'bayer_size', 'colours', 'atari_row_height'}
FLOAT_OPTIONS = {'brightness', 'contrast', 'saturation', 'hue_shift', 'red_gain', 'green_gain', 'blue_gain',
                 'effect_strength', 'display_brightness', 'bloom_strength', 'bloom_radius', 'chromatic_strength',
                 'rf_strength'}
OPTIONAL_OPTIONS = {'palette', 'width', 'height', 'bayer_size', 'colours', 'atari_row_height', 'effect_strength'}
NON_SETTINGS = {'command', 'input', 'output', 'preset', 'presets_dir', 'print_only'}


def default_settings(parser) -> dict:
    return {key: value for key, value in vars(parser.parse_args(['convert', 'input', 'output'])).items()
            if key not in NON_SETTINGS}


def normalize_settings(raw: dict, defaults: dict) -> dict:
    """Validate a portable settings object and pin implicit target defaults."""
    if not isinstance(raw, dict):
        raise ValueError('preset settings must be an object')
    unknown = raw.keys() - defaults.keys()
    if unknown:
        raise ValueError('unknown preset settings: ' + ', '.join(sorted(unknown)))
    values = dict(defaults, **raw)
    for key, value in values.items():
        if value is None and key in OPTIONAL_OPTIONS:
            continue
        if key in INTEGER_OPTIONS:
            valid = type(value) is int and value > 0
        elif key in FLOAT_OPTIONS:
            valid = type(value) in (int, float)
            try:
                valid = valid and math.isfinite(value)
            except OverflowError:
                valid = False
        else:
            valid = type(value) is str
        if not valid:
            raise ValueError(f'invalid value for preset setting {key}')
    validate_display_effect(values['display_effect'], values['effect_strength'], values['scale'])
    validate_display_brightness(values['display_brightness'])
    validate_bloom(values['bloom_strength'], values['bloom_radius'])
    validate_chromatic_strength(values['chromatic_strength'])
    validate_rf_strength(values['rf_strength'])
    if values['profile'] not in PROFILES:
        raise ValueError('unknown preset profile: ' + values['profile'])
    profile = PROFILES[values['profile']]
    values['palette'] = values['palette'] or profile.default_palette
    if values['palette'] not in PALETTES:
        raise ValueError('unknown preset palette: ' + values['palette'])
    if values['fit'] not in {'cover', 'contain', 'stretch'}:
        raise ValueError('unknown preset fit mode')
    if values['dither'] not in DITHER_MODES:
        raise ValueError('unknown preset dither mode')
    if values['bayer_size'] is not None and values['dither'] != 'bayer':
        raise ValueError('bayer_size requires bayer dithering')
    if values['dither'] == 'bayer':
        values['bayer_size'] = values['bayer_size'] or 4
        if values['bayer_size'] not in BAYER_SIZES:
            raise ValueError('Bayer size must be 2, 4 or 8')
    if values['saturation'] <= 0 or any(values[c + '_gain'] < 0 for c in ('red', 'green', 'blue')):
        raise ValueError('saturation must be positive and colour gains non-negative')
    for name in ('brightness', 'contrast'):
        if values[name] < 0:
            raise ValueError(f'{name} must be non-negative')
    width, height = values['width'], values['height']
    if (width is None) != (height is None):
        raise ValueError('preset width and height must be supplied together')
    mode = 'bitmap'
    option = None
    for flag, spec in MODE_OPTIONS.items():
        if profile.constraint_model in spec.constraint_models:
            option, mode = flag, values[flag]
    get_profile_quantizer(profile, colours=values['colours'], atari_row_height=values['atari_row_height'],
                          bayer_size=values['bayer_size'], **{key: values[key] for key in MODE_OPTIONS})
    if mode != 'bitmap':
        required = CONSTRAINT_PALETTES.get(profile.constraint_model, REQUIRED_PALETTES.get(option))
        if required and values['palette'] not in required:
            raise ValueError(f'{mode} requires a palette from: ' + ', '.join(required))
        cw, ch = CELL_DIMENSIONS.get(profile.constraint_model, (1, 1))
        w, h = width or profile.geometry.width, height or profile.geometry.height
        if w % cw or h % ch:
            raise ValueError(f'preset dimensions must be divisible by {cw}x{ch}')
        if option == 'atari_mode':
            if w != 160:
                raise ValueError('Atari playfield width must be 160')
            values['atari_row_height'] = values['atari_row_height'] or 2
    if (profile.constraint_model, mode) in COLOUR_COUNT_QUANTIZERS:
        limit = AMIGA_COLOUR_LIMITS[profile.constraint_model.removeprefix('amiga-')]
        values['colours'] = values['colours'] or limit
        if values['colours'] not in (2, 4, 8, 16, 32) or values['colours'] > limit:
            raise ValueError(f'screen colours must be a supported power of two up to {limit}')
    return values


def compact_settings(values: dict) -> dict:
    """Keep applicable flags, compacting inactive and neutral display options."""
    profile = PROFILES[values['profile']]
    active = {key for key, spec in MODE_OPTIONS.items() if profile.constraint_model in spec.constraint_models}
    return {key: value for key, value in values.items() if value is not None
            and not (key == 'display_effect' and value == 'none')
            and not (key == 'display_brightness' and value == 1)
            and not (key == 'bloom_strength' and value == 0)
            and not (key == 'chromatic_strength' and value == 0)
            and not (key == 'rf_strength' and value == 0)
            and not (key == 'bloom_radius' and value == DEFAULT_BLOOM_RADIUS)
            and (key not in MODE_OPTIONS or key in active)}


def merge_settings(saved: dict, overrides: dict, defaults: dict) -> dict:
    """Explicit CLI flags win; discard inherited options made inapplicable."""
    values = dict(saved, **overrides)
    if values.get('display_effect', 'none') == 'none' and 'effect_strength' not in overrides:
        values['effect_strength'] = None
    if values.get('dither') != 'bayer' and 'bayer_size' not in overrides:
        values['bayer_size'] = None
    profile = PROFILES.get(values.get('profile', defaults['profile']))
    if profile:
        active = {key for key, spec in MODE_OPTIONS.items() if profile.constraint_model in spec.constraint_models}
        for flag in MODE_OPTIONS:
            inherited_mode = values.get(flag, 'bitmap')
            supported = (flag in active and (inherited_mode == 'bitmap' or
                         (profile.constraint_model, inherited_mode) in CONSTRAINED_QUANTIZERS))
            if not supported and flag not in overrides:
                values[flag] = 'bitmap'
        if 'profile' in overrides:
            if 'palette' not in overrides:
                values['palette'] = profile.default_palette
            if 'colours' not in overrides:
                values['colours'] = None
        mode = next((values.get(key, 'bitmap') for key in active), 'bitmap')
        if (profile.constraint_model, mode) not in COLOUR_COUNT_QUANTIZERS and 'colours' not in overrides:
            values['colours'] = None
        if profile.constraint_model != 'atari2600-playfield' or mode == 'bitmap':
            if 'atari_row_height' not in overrides:
                values['atari_row_height'] = None
    return normalize_settings(values, defaults)
