"""Highlight glow, independent composition and user-facing setting round trips."""
from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.convert import convert_file
from retroimg.display_effects import apply_display_brightness, bloom
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.presets import load_file, save_preset
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings


def target():
    palette = Palette('test', (Colour('black', (0, 0, 0)), Colour('white', (255, 255, 255))))
    return IndexedImage(9, 9, palette, tuple(tuple(int(3 <= x <= 5 and 3 <= y <= 5)
                                                  for x in range(9)) for y in range(9)))


@pytest.mark.parametrize('effect', ['none', 'gameboy-lcd', 'scanlines', 'crt-aperture'])
def test_disabled_bloom_preserves_existing_effects_exactly(effect):
    indexed = target()
    existing = render_indexed(indexed, scale=6, display_effect=effect)
    disabled = render_indexed(indexed, scale=6, display_effect=effect, bloom_strength=0, bloom_radius=8)
    assert disabled.size == existing.size
    assert disabled.tobytes() == existing.tobytes()


def test_glow_spreads_highlights_without_blurring_or_dimming_the_original():
    source = Image.new('RGB', (65, 65))
    source.paste((255, 255, 255), (28, 28, 37, 37))
    subtle = bloom(source, 65, .25, 2)
    strong = bloom(source, 65, .85, 2)
    assert subtle.getpixel((32, 32)) == (255, 255, 255)
    assert 0 < subtle.getpixel((27, 32))[0] < strong.getpixel((27, 32))[0]
    assert strong.getpixel((0, 0)) == (0, 0, 0)
    assert all(a >= b for a, b in zip(subtle.tobytes(), source.tobytes()))
    data = subtle.tobytes()
    assert data[0::3] == data[1::3] == data[2::3]


@pytest.mark.parametrize('colour', [(0, 0, 0), (180, 180, 180), (0, 180, 60)])
def test_dark_images_do_not_glow(colour):
    source = Image.new('RGB', (19, 17), colour)
    assert bloom(source, 19, 1, 1).tobytes() == source.tobytes()


def test_saturated_highlights_keep_their_channel_identity_and_edges_do_not_wrap():
    source = Image.new('RGB', (65, 41))
    source.paste((255, 0, 0), (0, 16, 8, 25))
    output = bloom(source, 65, 1, 2)
    assert output.getpixel((9, 20))[0] > 0
    assert output.getpixel((64, 20)) == (0, 0, 0)
    data = output.tobytes()
    assert not any(data[1::3]) and not any(data[2::3])


def test_radius_controls_spread_in_logical_units_across_enlargements():
    source = Image.new('RGB', (41, 41))
    source.paste((255, 255, 255), (16, 16, 25, 25))
    narrow = bloom(source, 41, 1, .5)
    wide = bloom(source, 41, 1, 3)
    assert wide.getpixel((12, 20))[0] > narrow.getpixel((12, 20))[0]
    enlarged = source.resize((164, 164), Image.Resampling.NEAREST)
    scaled = bloom(enlarged, 41, 1, 3)
    # Compare mean light over matching logical footprints, allowing blur sampling.
    a = wide.getpixel((12, 20))[0]
    b = sum(scaled.getpixel((x, y))[0] for y in range(80, 84) for x in range(48, 52)) / 16
    assert abs(a - b) < 5


@pytest.mark.parametrize('aspect', [.5, 1, 1.2])
def test_combined_pipeline_has_explicit_order_and_preserves_indexed_data(aspect):
    indexed = target()
    before = indexed.pixels
    surface = render_indexed(indexed, scale=6, pixel_aspect=aspect, display_effect='crt-aperture')
    expected = apply_display_brightness(bloom(surface, indexed.width, .4, 1.5), 1.2)
    actual = render_indexed(indexed, scale=6, pixel_aspect=aspect, display_effect='crt-aperture',
                            bloom_strength=.4, bloom_radius=1.5, display_brightness=1.2)
    assert actual.size == surface.size
    assert actual.tobytes() == expected.tobytes()
    assert actual.tobytes() != surface.tobytes()
    assert indexed.pixels == before


@pytest.mark.parametrize('setting,value', [
    *[('bloom_strength', value) for value in (-.1, 1.1, float('inf'), float('nan'), True, '0.2', None)],
    *[('bloom_radius', value) for value in (0, .1, 9, float('inf'), float('nan'), True, '1', None)],
])
def test_invalid_bloom_rejected_before_io_and_in_presets(tmp_path, setting, value):
    options = {setting: value}
    output = tmp_path / 'output.png'
    output.write_bytes(b'keep')
    with pytest.raises(ValueError, match='bloom'):
        convert_file(tmp_path / 'missing.png', output, **options)
    with pytest.raises(ValueError, match='bloom'):
        normalize_settings(options, default_settings(build_parser()))
    with pytest.raises(ValueError, match='bloom'):
        render_indexed(target(), **options)
    assert output.read_bytes() == b'keep'


def test_cli_preset_roundtrip_independent_disable_and_conversion_data(tmp_path):
    parser = build_parser()
    settings = dict(profile='gameboy', gameboy_mode='tiles', scale=4,
                    display_effect='crt-aperture', bloom_strength=.4, bloom_radius=1.5, display_brightness=1.2)
    saved = save_preset(tmp_path / 'combined.json', 'Combined', '', settings, parser)
    assert load_file(saved.path, parser).settings == saved.settings
    source = tmp_path / 'source.png'
    render_indexed(target(), scale=4).save(source)
    plain = convert_file(source, tmp_path / 'plain.png', profile_name='gameboy', gameboy_mode='tiles', scale=4)
    options = dict(settings)
    options['profile_name'] = options.pop('profile')
    effected = convert_file(source, tmp_path / 'api.png', **options)
    main(['convert', str(source), str(tmp_path / 'cli.png'), '--preset', str(saved.path)])
    assert plain == effected
    with Image.open(tmp_path / 'api.png') as api, Image.open(tmp_path / 'cli.png') as cli:
        assert api.tobytes() == cli.tobytes()
    defaults = default_settings(parser)
    no_surface = merge_settings(saved.settings, dict(display_effect='none'), defaults)
    assert no_surface['bloom_strength'] == .4
    no_bloom = merge_settings(saved.settings, dict(bloom_strength=0), defaults)
    assert no_bloom['display_effect'] == 'crt-aperture'
    assert no_bloom['bloom_strength'] == 0 and no_bloom['bloom_radius'] == 1.5
    assert normalize_settings({}, defaults)['bloom_strength'] == 0


def test_bloom_alone_works_at_native_resolution(tmp_path):
    source = tmp_path / 'source.png'
    render_indexed(target()).save(source)
    main(['convert', str(source), str(tmp_path / 'bloom.png'), '--profile', 'gameboy',
          '--width', '9', '--height', '9', '--scale', '1', '--bloom-strength', '.5'])
    with Image.open(tmp_path / 'bloom.png') as output:
        assert output.size == (9, 9)

