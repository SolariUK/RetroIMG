"""Whole-cell source matching preserves composition and bounded retro geometry."""
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from retroimg.cli import build_parser, main
from retroimg.convert import convert_file, convert_to_indexed
from retroimg.geometry import match_source_geometry
from retroimg.gui import jobs
from retroimg.presets import load_file, save_preset
from retroimg.profiles import get_profile
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings
from retroimg.targets.teletext import page_from_indexed


@pytest.mark.parametrize('size', [(1920, 1080), (1080, 1920), (400, 300), (1000, 1000),
                                 (1613, 907), (2400, 100), (100, 2400), (80, 75), (1, 1)])
def test_geometry_preserves_cells_pixel_shape_and_resolution_budget(size):
    native = get_profile('teletext').geometry
    geometry = match_source_geometry(size, native)
    assert geometry.width % 2 == 0 and geometry.height % 3 == 0
    assert geometry.width * geometry.height <= 2 * native.width * native.height
    assert max(geometry.width, geometry.height) <= 512
    assert .98 <= geometry.pixel_aspect <= 1.02
    assert geometry.width * geometry.pixel_aspect / geometry.height == pytest.approx(size[0] / size[1])


def test_widescreen_uses_near_native_height_and_native_input_stays_native():
    native = get_profile('teletext').geometry
    geometry = match_source_geometry((1920, 1080), native)
    assert (geometry.width, geometry.height, geometry.pixel_aspect) == (128, 72, 1)
    assert match_source_geometry((80, 75), native) == native


@pytest.mark.parametrize('size', [(100000, 1), (1, 100000)])
def test_extreme_ratios_fail_instead_of_large_allocations_or_distorted_pixels(size):
    with pytest.raises(ValueError, match='too extreme'):
        match_source_geometry(size, get_profile('teletext').geometry)


def marked_source(path, size=(1600, 900)):
    image = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle((0, 0, w - 1, h // 5), fill='red')
    draw.rectangle((0, h * 4 // 5, w - 1, h - 1), fill=(0, 255, 0))
    draw.rectangle((0, h // 3, w // 5, h * 2 // 3), fill='blue')
    draw.rectangle((w * 4 // 5, h // 3, w - 1, h * 2 // 3), fill='yellow')
    image.save(path)


@pytest.mark.parametrize('dither', ['none', 'bayer', 'floyd-steinberg'])
@pytest.mark.parametrize('mode', ['bitmap', 'mosaic'])
def test_full_composition_survives_with_no_padding_and_valid_cells(tmp_path, mode, dither):
    source, output = tmp_path / 'source.png', tmp_path / 'output.png'
    marked_source(source)
    indexed = convert_file(source, output, aspect_mode='source', teletext_mode=mode, dither=dither, scale=5)
    rgb = indexed.palette.rgb_values()
    assert rgb[indexed.pixels[0][indexed.width // 2]] == (255, 0, 0)
    assert rgb[indexed.pixels[-1][indexed.width // 2]] == (0, 255, 0)
    assert rgb[indexed.pixels[indexed.height // 2][0]] == (0, 0, 255)
    assert rgb[indexed.pixels[indexed.height // 2][-1]] == (255, 255, 0)
    if mode == 'mosaic':
        page = page_from_indexed(indexed)
        assert (page.columns, page.rows) == (64, 24)
    with Image.open(output) as rendered:
        assert rendered.size == (640, 360)


@pytest.mark.parametrize('fit', ['cover', 'contain', 'stretch'])
def test_source_matching_replaces_the_fixed_canvas_fit_policy(tmp_path, fit):
    source = tmp_path / 'source.png'
    marked_source(source, (1613, 907))
    indexed = convert_to_indexed(source, teletext_mode='mosaic', aspect_mode='source', fit=fit)
    assert indexed == convert_to_indexed(source, teletext_mode='mosaic', aspect_mode='source')
    assert indexed.pixel_aspect != 1
    rendered = render_indexed(indexed, scale=5)
    assert abs(rendered.width / rendered.height / (1613 / 907) - 1) < 1 / min(rendered.size)


@pytest.mark.parametrize('options', [dict(profile_name='gameboy'), dict(width=80, height=75),
                                    dict(width=80), dict(aspect_mode='missing')])
def test_unsupported_combinations_fail_before_opening_source(options):
    values = dict(aspect_mode='source', **{k: v for k, v in options.items() if k != 'aspect_mode'})
    values.update(options)
    with pytest.raises(ValueError, match='aspect|custom'):
        convert_to_indexed(Path('does-not-exist.png'), **values)


def test_native_default_preserves_existing_conversion_and_rendering(tmp_path):
    source = tmp_path / 'source.png'
    marked_source(source)
    a, b = tmp_path / 'a.png', tmp_path / 'b.png'
    indexed = convert_file(source, a, teletext_mode='mosaic')
    explicit = convert_file(source, b, teletext_mode='mosaic', aspect_mode='native')
    assert indexed == explicit and indexed.pixel_aspect is None
    assert a.read_bytes() == b.read_bytes()


def test_presets_keep_automatic_intent_and_explicit_overrides_clear_conflicts(tmp_path):
    parser = build_parser()
    defaults = default_settings(parser)
    saved = save_preset(tmp_path / 'wide.json', 'Wide Teletext', '',
                        dict(aspect_mode='source', teletext_mode='mosaic'), parser)
    loaded = load_file(saved.path, parser)
    assert loaded.settings['aspect_mode'] == 'source'
    assert 'width' not in loaded.settings and 'height' not in loaded.settings
    assert merge_settings(loaded.settings, dict(profile='gameboy'), defaults)['aspect_mode'] == 'native'
    manual = merge_settings(loaded.settings, dict(width=80, height=75), defaults)
    assert manual['aspect_mode'] == 'native'
    automatic = merge_settings(dict(width=80, height=75), dict(aspect_mode='source'), defaults)
    assert automatic['width'] is automatic['height'] is None
    with pytest.raises(ValueError, match='only for Teletext'):
        normalize_settings(dict(profile='gameboy', aspect_mode='source'), defaults)


def test_cli_and_cached_worker_share_fractional_pixel_geometry_and_effects(tmp_path):
    source, cli_output = tmp_path / 'source.png', tmp_path / 'cli.png'
    marked_source(source, (1613, 907))
    settings = dict(profile='teletext', teletext_mode='mosaic', aspect_mode='source', scale=5,
                    display_effect='crt-aperture', bloom_strength=.2)
    job = dict(kind='retro', source=str(source), image=str(tmp_path / 'gui.png'),
               cache=str(tmp_path / 'indexed.json'), settings=settings)
    first = jobs.render_job(job)
    assert not first['reused_conversion']
    settings['display_brightness'] = 1.2
    cached = jobs.render_job(job)
    assert cached['reused_conversion']
    main(['convert', str(source), str(cli_output), '--aspect-mode=source', '--teletext-mode=mosaic',
          '--scale=5', '--display-effect=crt-aperture', '--bloom-strength=.2', '--display-brightness=1.2'])
    with Image.open(cli_output) as expected, Image.open(job['image']) as actual:
        assert actual.size == expected.size == tuple(cached['size'])
        assert actual.tobytes() == expected.tobytes()
    settings['aspect_mode'] = 'native'
    assert not jobs.render_job(job)['reused_conversion']
