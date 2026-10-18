"""Radial colour separation and composition with the display surface and bloom."""
from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.convert import convert_file
from retroimg.display_effects import (
    apply_display_brightness, bloom, chromatic_aberration, crt_aperture, gameboy_lcd, scanlines,
)
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.presets import load_file, save_preset
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings


def target():
    palette = Palette('test', (Colour('black', (0, 0, 0)), Colour('white', (255, 255, 255))))
    return IndexedImage(9, 9, palette, tuple(tuple(int(1 <= x <= 3 and 1 <= y <= 6)
                                                  for x in range(9)) for y in range(9)))


def test_radial_separation_leaves_green_and_centre_fixed_and_interpolates_linear_light():
    source = Image.new('RGB', (65, 65))
    source.paste((255, 255, 255), (16, 0, 48, 65))
    result = chromatic_aberration(source, 65, 1)
    assert result.getchannel('G').tobytes() == source.getchannel('G').tobytes()
    assert result.getpixel((32, 32)) == source.getpixel((32, 32))
    # Red expands outwards on both sides; blue contracts towards the centre.
    assert result.getpixel((15, 32))[0] > 0 and result.getpixel((48, 32))[0] > 0
    assert result.getpixel((16, 32))[2] < 255 and result.getpixel((47, 32))[2] < 255
    # The red sample at x=15 contains roughly half white/half black light.
    # Linear-light interpolation encodes this near 188 rather than sRGB 128.
    assert 180 <= result.getpixel((15, 32))[0] <= 195


def test_separation_increases_towards_edges_and_with_strength():
    source = Image.new('RGB', (65, 65))
    for x in (8, 32, 56):
        source.paste((255, 255, 255), (x, 0, x + 1, 65))
    subtle = chromatic_aberration(source, 65, .25)
    strong = chromatic_aberration(source, 65, 1)
    assert strong.getpixel((32, 32)) == (255, 255, 255)
    assert strong.getpixel((7, 32))[0] > subtle.getpixel((7, 32))[0] > 0
    assert strong.getpixel((57, 32))[0] > subtle.getpixel((57, 32))[0] > 0


@pytest.mark.parametrize('size', [(1, 1), (1, 13), (13, 1), (17, 11)])
@pytest.mark.parametrize('colour', [(0, 0, 0), (64, 128, 192), (255, 255, 255)])
def test_uniform_colours_stay_uniform_without_dark_borders(size, colour):
    source = Image.new('RGB', size, colour)
    result = chromatic_aberration(source, size[0], 1)
    assert result.size == source.size and result.tobytes() == source.tobytes()


def test_edges_clamp_without_wrapping_to_the_opposite_side():
    source = Image.new('RGB', (65, 33))
    source.paste((0, 0, 255), (0, 0, 4, 33))
    result = chromatic_aberration(source, 65, 1)
    assert result.getpixel((0, 16)) == (0, 0, 255)
    assert result.getpixel((64, 16)) == (0, 0, 0)
    assert not any(result.getchannel('R').tobytes())


@pytest.mark.parametrize('effect', ['none', 'gameboy-lcd', 'scanlines', 'crt-aperture'])
def test_zero_preserves_existing_effect_and_bloom_combinations_exactly(effect):
    options = dict(scale=4, display_effect=effect, bloom_strength=.25)
    before = render_indexed(target(), **options)
    after = render_indexed(target(), chromatic_strength=0, **options)
    assert before.tobytes() == after.tobytes()


@pytest.mark.parametrize('effect', ['none', 'gameboy-lcd', 'scanlines', 'crt-aperture'])
@pytest.mark.parametrize('aspect', [.5, 1.2])
def test_separation_precedes_surface_and_bloom_with_final_brightness(effect, aspect):
    indexed = target()
    original = indexed.pixels
    plain = render_indexed(indexed, scale=5, pixel_aspect=aspect)
    shifted = chromatic_aberration(plain, indexed.width, .7)
    expected = shifted
    if effect == 'gameboy-lcd':
        expected = gameboy_lcd(shifted, (9, 9), (255, 255, 255), .35)
    elif effect == 'scanlines':
        expected = scanlines(shifted, 9, .35)
    elif effect == 'crt-aperture':
        expected = crt_aperture(shifted, 9, .35)
    expected = apply_display_brightness(bloom(expected, 9, .4, 1), 1.2)
    actual = render_indexed(indexed, scale=5, pixel_aspect=aspect, display_effect=effect,
                            chromatic_strength=.7, bloom_strength=.4, display_brightness=1.2)
    assert actual.size == plain.size
    assert actual.tobytes() == expected.tobytes()
    assert indexed.pixels == original


def test_displacement_scales_with_enlargement():
    source = Image.new('RGB', (65, 33))
    source.paste((255, 255, 255), (16, 0, 48, 33))
    a = chromatic_aberration(source.resize((260, 132), Image.Resampling.NEAREST), 65, .75)
    b = chromatic_aberration(source.resize((520, 264), Image.Resampling.NEAREST), 65, .75)
    # The first red fringe lies near logical x=15 at both enlargement factors.
    x_a = next(x for x in range(a.width) if a.getpixel((x, a.height // 2))[0] > 20)
    x_b = next(x for x in range(b.width) if b.getpixel((x, b.height // 2))[0] > 20)
    assert abs(x_a / 4 - x_b / 8) <= .25


@pytest.mark.parametrize('value', [-.1, 1.1, float('inf'), float('nan'), True, '0.2', None])
def test_invalid_strength_rejected_before_io_and_in_presets(tmp_path, value):
    output = tmp_path / 'output.png'
    output.write_bytes(b'keep')
    with pytest.raises(ValueError, match='chromatic'):
        convert_file(tmp_path / 'missing.png', output, chromatic_strength=value)
    with pytest.raises(ValueError, match='chromatic'):
        render_indexed(target(), chromatic_strength=value)
    with pytest.raises(ValueError, match='chromatic'):
        normalize_settings(dict(chromatic_strength=value), default_settings(build_parser()))
    assert output.read_bytes() == b'keep'


def test_cli_preset_and_independent_overrides_preserve_conversion(tmp_path):
    parser = build_parser()
    settings = dict(profile='gameboy', gameboy_mode='tiles', scale=4, display_effect='crt-aperture',
                    chromatic_strength=.7, bloom_strength=.25, display_brightness=1.2)
    preset = save_preset(tmp_path / 'combined.json', 'Combined', '', settings, parser)
    assert load_file(preset.path, parser).settings == preset.settings
    source = tmp_path / 'source.png'
    render_indexed(target(), scale=4).save(source)
    before = convert_file(source, tmp_path / 'plain.png', profile_name='gameboy', gameboy_mode='tiles', scale=4)
    options = dict(settings)
    options['profile_name'] = options.pop('profile')
    after = convert_file(source, tmp_path / 'api.png', **options)
    main(['convert', str(source), str(tmp_path / 'cli.png'), '--preset', str(preset.path)])
    assert before == after
    with Image.open(tmp_path / 'api.png') as api, Image.open(tmp_path / 'cli.png') as cli:
        assert api.tobytes() == cli.tobytes()
    disabled = merge_settings(preset.settings, dict(chromatic_strength=0), default_settings(parser))
    assert disabled['display_effect'] == 'crt-aperture' and disabled['bloom_strength'] == .25
    surface_disabled = merge_settings(preset.settings, dict(display_effect='none'), default_settings(parser))
    assert surface_disabled['chromatic_strength'] == .7


def test_chromatic_aberration_alone_at_native_resolution():
    assert render_indexed(target(), chromatic_strength=.5).size == (9, 9)
