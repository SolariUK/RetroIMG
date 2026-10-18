"""Horizontal colour bandwidth, signal trailing and independent display stages."""
from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.convert import convert_file
from retroimg.display_effects import (
    apply_display_brightness, bloom, chromatic_aberration, crt_aperture, rf_smear,
)
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.presets import load_file, save_preset
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings


def target():
    palette = Palette('test', (Colour('grey', (100, 100, 100)), Colour('red', (200, 100, 100))))
    return IndexedImage(9, 9, palette, tuple(tuple(int(2 <= x <= 4) for x in range(9)) for y in range(9)))


def test_colour_spreads_horizontally_with_a_rightward_trail_and_no_vertical_bleed():
    source = Image.new('RGB', (65, 16))
    source.paste((255, 0, 0), (20, 0, 30, 8))
    result = rf_smear(source, 65, 1)
    left, right = result.getpixel((19, 3)), result.getpixel((30, 3))
    assert right[0] > left[0] > 0  # rightward colour trail exceeds the preceding bleed
    assert right[0] > right[1] == right[2]
    assert result.crop((0, 8, 65, 16)).tobytes() == source.crop((0, 8, 65, 16)).tobytes()
    assert result.crop((0, 0, 65, 1)).tobytes() == result.crop((0, 7, 65, 8)).tobytes()


def test_colour_boundaries_soften_more_than_luma_detail():
    # These colours have almost identical encoded luma but distinctly different chroma.
    source = Image.new('RGB', (65, 5), (200, 100, 100))
    source.paste((100, 151, 100), (32, 0, 65, 5))
    result = rf_smear(source, 65, 1)
    a, b = result.getpixel((31, 2)), result.getpixel((32, 2))
    assert 0 < a[0] - b[0] < 100
    for x in range(65):
        r, g, b = result.getpixel((x, 2))
        assert abs(.299 * r + .587 * g + .114 * b - 129.9) < 1


def test_monochrome_edges_soften_without_false_colours():
    source = Image.new('RGB', (64, 8))
    source.paste((255, 255, 255), (32, 0, 64, 8))
    result = rf_smear(source, 16, 1)
    data = result.tobytes()
    assert data[0::3] == data[1::3] == data[2::3]
    assert 0 < result.getpixel((31, 2))[0] < result.getpixel((32, 2))[0] < 255


@pytest.mark.parametrize('size', [(1, 1), (1, 11), (13, 1), (19, 11)])
@pytest.mark.parametrize('colour', [(0, 0, 0), (255, 255, 255), (64, 128, 192), (255, 0, 0)])
def test_uniform_colours_and_frame_edges_remain_stable(size, colour):
    source = Image.new('RGB', size, colour)
    assert rf_smear(source, size[0], 1).tobytes() == source.tobytes()


def test_signal_does_not_wrap_from_one_frame_edge_to_the_other():
    source = Image.new('RGB', (65, 9))
    source.paste((255, 0, 0), (0, 0, 5, 9))
    result = rf_smear(source, 65, 1)
    assert result.getpixel((64, 4)) == (0, 0, 0)
    assert result.getpixel((0, 4))[0] > 240


def test_strength_controls_the_blend_and_spread_tracks_logical_pixel_width():
    source = Image.new('RGB', (65, 5))
    source.paste((255, 0, 0), (20, 0, 30, 5))
    subtle, strong = rf_smear(source, 65, .35), rf_smear(source, 65, .85)
    assert 0 < subtle.getpixel((30, 2))[0] < strong.getpixel((30, 2))[0]
    assert subtle.getpixel((29, 2))[0] > strong.getpixel((29, 2))[0]
    ends = []
    for scale in (4, 8):
        enlarged = source.resize((65 * scale, 5 * scale), Image.Resampling.NEAREST)
        output = rf_smear(enlarged, 65, 1)
        ends.append(max(x / scale for x in range(output.width) if output.getpixel((x, 0))[0] > 5))
    assert abs(ends[0] - ends[1]) < .5


@pytest.mark.parametrize('effect', ['none', 'gameboy-lcd', 'scanlines', 'crt-aperture'])
def test_disabled_rf_preserves_other_effect_combinations_exactly(effect):
    options = dict(scale=4, display_effect=effect, chromatic_strength=.3, bloom_strength=.25)
    before = render_indexed(target(), **options)
    assert render_indexed(target(), rf_strength=0, **options).tobytes() == before.tobytes()


@pytest.mark.parametrize('aspect', [.5, 1.2])
def test_rf_precedes_chromatic_surface_bloom_and_final_gain_with_unrestricted_rgb(aspect):
    indexed = target()
    original = indexed.pixels
    plain = render_indexed(indexed, scale=5, pixel_aspect=aspect)
    expected = rf_smear(plain, 9, .7)
    expected = chromatic_aberration(expected, 9, .3)
    expected = crt_aperture(expected, 9, .35)
    expected = apply_display_brightness(bloom(expected, 9, .25, 1), 1.2)
    actual = render_indexed(indexed, scale=5, pixel_aspect=aspect, rf_strength=.7,
                            chromatic_strength=.3, display_effect='crt-aperture',
                            bloom_strength=.25, display_brightness=1.2)
    assert actual.size == plain.size
    assert actual.tobytes() == expected.tobytes()
    assert indexed.pixels == original
    data = actual.tobytes()
    colours = set(zip(data[0::3], data[1::3], data[2::3]))
    assert colours - set(indexed.palette.rgb_values())


@pytest.mark.parametrize('value', [-.1, 1.1, float('inf'), float('nan'), True, '0.2', None])
def test_invalid_strength_rejected_before_io_and_in_presets(tmp_path, value):
    output = tmp_path / 'output.png'
    output.write_bytes(b'keep')
    with pytest.raises(ValueError, match='RF'):
        convert_file(tmp_path / 'missing.png', output, rf_strength=value)
    with pytest.raises(ValueError, match='RF'):
        render_indexed(target(), rf_strength=value)
    with pytest.raises(ValueError, match='RF|rf_strength'):
        normalize_settings(dict(rf_strength=value), default_settings(build_parser()))
    assert output.read_bytes() == b'keep'


def test_cli_preset_roundtrip_and_independent_disable_preserve_conversion(tmp_path):
    parser = build_parser()
    settings = dict(profile='nes', nes_mode='attributes', width=16, height=16, scale=4,
                    rf_strength=.7, display_effect='crt-aperture',
                    chromatic_strength=.3, bloom_strength=.25, display_brightness=1.2)
    saved = save_preset(tmp_path / 'combined.json', 'Combined', '', settings, parser)
    assert load_file(saved.path, parser).settings == saved.settings
    source = tmp_path / 'source.png'
    render_indexed(target(), scale=4).save(source)
    before = convert_file(source, tmp_path / 'plain.png', profile_name='nes', nes_mode='attributes',
                          width=16, height=16, scale=4)
    options = dict(settings)
    options['profile_name'] = options.pop('profile')
    after = convert_file(source, tmp_path / 'api.png', **options)
    main(['convert', str(source), str(tmp_path / 'cli.png'), '--preset', str(saved.path)])
    assert before == after
    with Image.open(tmp_path / 'api.png') as api, Image.open(tmp_path / 'cli.png') as cli:
        assert api.tobytes() == cli.tobytes()
    disabled = merge_settings(saved.settings, dict(rf_strength=0), default_settings(parser))
    assert disabled['display_effect'] == 'crt-aperture' and disabled['chromatic_strength'] == .3
    surface_disabled = merge_settings(saved.settings, dict(display_effect='none'), default_settings(parser))
    assert surface_disabled['rf_strength'] == .7
    assert normalize_settings({}, default_settings(parser))['rf_strength'] == 0


def test_rf_alone_at_native_resolution():
    assert render_indexed(target(), rf_strength=.5).size == (9, 9)
