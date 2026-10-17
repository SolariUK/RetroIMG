from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.convert import convert_file
from retroimg.model import IndexedImage
from retroimg.palettes import get_palette
from retroimg.presets import load_file, save_preset
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings


def cells(palette='gameboy'):
    return IndexedImage(2, 2, get_palette(palette), ((3, 3), (3, 3)))


def test_plain_render_and_zero_strength_preserve_pixels_and_indexes():
    indexed = cells()
    original = indexed.pixels
    plain = render_indexed(indexed, scale=8)
    assert plain.getpixel((0, 0)) == indexed.palette.rgb_values()[3]
    assert plain.tobytes() == render_indexed(indexed, scale=8, display_effect='none').tobytes()
    assert plain.tobytes() == render_indexed(indexed, scale=8, display_effect='gameboy-lcd', effect_strength=0).tobytes()
    assert indexed.pixels == original


@pytest.mark.parametrize('palette', ['gameboy', 'gameboy-grey', 'cga'])
def test_lcd_cells_repeat_and_preserve_centres_and_palette_tint(palette):
    indexed = cells(palette)
    output = render_indexed(indexed, scale=8, display_effect='gameboy-lcd', effect_strength=1)
    assert output.size == (16, 16) and output.mode == 'RGB'
    # The clear centre remains the converted colour; borders reveal substrate.
    assert output.getpixel((3, 3)) == indexed.palette.rgb_values()[3]
    assert output.getpixel((0, 0)) != output.getpixel((3, 3))
    # The small offset shadow darkens the right edge relative to the left.
    assert sum(output.getpixel((7, 3))) < sum(output.getpixel((0, 3)))
    assert output.crop((0, 0, 8, 8)).tobytes() == output.crop((8, 8, 16, 16)).tobytes()
    if palette == 'gameboy-grey':
        assert all(r == g == b for _, (r, g, b) in output.getcolors(256 * 256))


def test_strength_changes_only_display_and_has_no_image_dependent_grid_shift():
    indexed = cells()
    plain = render_indexed(indexed, scale=8)
    subtle = render_indexed(indexed, scale=8, display_effect='gameboy-lcd', effect_strength=.3)
    strong = render_indexed(indexed, scale=8, display_effect='gameboy-lcd', effect_strength=.9)
    assert plain.getpixel((0, 0))[1] < subtle.getpixel((0, 0))[1] < strong.getpixel((0, 0))[1]
    other = IndexedImage(2, 2, indexed.palette, ((0, 3), (3, 3)))
    modified = render_indexed(other, scale=8, display_effect='gameboy-lcd', effect_strength=.9)
    assert strong.crop((8, 8, 16, 16)).tobytes() == modified.crop((8, 8, 16, 16)).tobytes()


@pytest.mark.parametrize('aspect', [.5, 1.2, 2])
def test_effect_uses_logical_grid_after_aspect_correction(aspect):
    indexed = cells()
    plain = render_indexed(indexed, scale=5, pixel_aspect=aspect)
    output = render_indexed(indexed, scale=5, pixel_aspect=aspect, display_effect='gameboy-lcd')
    assert output.size == plain.size
    assert output.getpixel((output.width // 4, output.height // 4)) == indexed.palette.rgb_values()[3]
    assert output.tobytes() != plain.tobytes()


@pytest.mark.parametrize('settings', [
    dict(display_effect='unknown'), dict(effect_strength=.5),
    dict(display_effect='gameboy-lcd', scale=2), dict(display_effect='scanlines', scale=2),
    *[dict(display_effect='gameboy-lcd', effect_strength=v)
      for v in (-.1, 1.1, float('inf'), float('nan'), True)],
])
def test_invalid_effects_rejected_by_api_and_presets_before_io(tmp_path, settings):
    output = tmp_path / 'output.png'
    output.write_bytes(b'keep')
    with pytest.raises(ValueError):
        convert_file(tmp_path / 'missing.png', output, **settings)
    with pytest.raises(ValueError):
        normalize_settings(settings, default_settings(build_parser()))
    assert output.read_bytes() == b'keep'


@pytest.mark.parametrize('effect', ['gameboy-lcd', 'scanlines'])
@pytest.mark.parametrize('profile,mode', [('gameboy', {'gameboy_mode': 'tiles'}), ('cga-320', {})])
def test_cli_and_python_effects_match_and_return_plain_indexed_data(tmp_path, profile, mode, effect):
    source = tmp_path / 'source.png'
    Image.new('RGB', (8, 8), (180, 210, 180)).save(source)
    options = dict(profile_name=profile, width=8, height=8, scale=4, **mode)
    plain = convert_file(source, tmp_path / 'plain.png', **options)
    effected = convert_file(source, tmp_path / 'effect.png', display_effect=effect, **options)
    assert plain == effected
    args = ['convert', str(source), str(tmp_path / 'cli.png'), '--profile', profile,
            '--width=8', '--height=8', '--scale=4', f'--display-effect={effect}']
    args.extend(f'--{key.replace("_", "-")}={value}' for key, value in mode.items())
    main(args)
    assert (tmp_path / 'effect.png').read_bytes() == (tmp_path / 'cli.png').read_bytes()
    assert (tmp_path / 'effect.png').read_bytes() != (tmp_path / 'plain.png').read_bytes()


@pytest.mark.parametrize('effect', ['gameboy-lcd', 'scanlines'])
def test_preset_roundtrip_disable_and_cross_platform_experiment(tmp_path, effect):
    parser = build_parser()
    settings = dict(profile='gameboy', gameboy_mode='tiles', scale=6,
                    display_effect=effect, effect_strength=.8)
    saved = save_preset(tmp_path / 'lcd.json', 'LCD', '', settings, parser)
    loaded = load_file(saved.path, parser)
    assert saved.settings == loaded.settings
    defaults = default_settings(parser)
    changed = merge_settings(loaded.settings, dict(profile='cga-320'), defaults)
    assert changed['display_effect'] == effect and changed['effect_strength'] == .8
    disabled = merge_settings(loaded.settings, dict(display_effect='none', scale=1), defaults)
    assert disabled['display_effect'] == 'none' and disabled['effect_strength'] is None
    with pytest.raises(ValueError, match='requires a display effect'):
        merge_settings(loaded.settings, dict(display_effect='none', effect_strength=.5), defaults)


def test_existing_gameboy_conversion_checksum_is_unchanged(tmp_path):
    from hashlib import sha256
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'samples/comparisons/manifest.json').read_text())
    entry = next(item for item in manifest['comparisons'] if item['family'] == 'gameboy')
    variant = entry['variants'][0]
    output = tmp_path / 'plain.png'
    convert_file(root / 'samples/sources' / entry['source']['file'], output, **variant['settings'])
    assert sha256(output.read_bytes()).hexdigest() == variant['sha256']


def test_scanlines_repeat_per_logical_row_without_changing_columns_or_black():
    indexed = IndexedImage(2, 3, get_palette('gameboy-grey'), ((0, 3),) * 3)
    original = indexed.pixels
    plain = render_indexed(indexed, scale=8)
    output = render_indexed(indexed, scale=8, display_effect='scanlines')
    assert output.size == plain.size
    assert render_indexed(indexed, scale=8, display_effect='scanlines', effect_strength=0).tobytes() == plain.tobytes()
    assert output.crop((0, 0, 16, 8)).tobytes() == output.crop((0, 8, 16, 16)).tobytes()
    assert output.getpixel((0, 0))[0] < output.getpixel((0, 3))[0]
    assert output.getpixel((0, 3)) == output.getpixel((7, 3))
    assert output.crop((8, 0, 16, 24)).getextrema() == ((0, 0),) * 3
    assert indexed.pixels == original


@pytest.mark.parametrize('aspect', [1, .7, 1.3])
def test_scanlines_preserve_aspect_and_integrated_brightness(aspect):
    indexed = IndexedImage(2, 7, get_palette('gameboy-grey'), ((0, 0),) * 7)
    output = render_indexed(indexed, scale=5, pixel_aspect=aspect,
                            display_effect='scanlines', effect_strength=.6)
    assert output.size == render_indexed(indexed, scale=5, pixel_aspect=aspect).size
    # Dimming is calculated in linear light, averaging 1 - strength/2 per row.
    values = [output.getpixel((0, y))[0] / 255 for y in range(output.height)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    assert sum(linear) / len(linear) == pytest.approx(.7, abs=.005)
    assert max(values) < 1 and min(values) > 0


def test_stronger_scanlines_dim_boundaries_more_than_subtle_scanlines():
    indexed = cells('gameboy-grey')
    # Use a non-black shade so the brightness difference is visible.
    indexed = IndexedImage(2, 2, indexed.palette, ((1, 1),) * 2)
    subtle = render_indexed(indexed, scale=8, display_effect='scanlines', effect_strength=.35)
    strong = render_indexed(indexed, scale=8, display_effect='scanlines', effect_strength=.85)
    assert strong.getpixel((0, 0))[0] < subtle.getpixel((0, 0))[0] < 170
    assert subtle.tobytes() == render_indexed(indexed, scale=8, display_effect='scanlines').tobytes()


@pytest.mark.parametrize('folder,profile,size', [('display-effects', 'gameboy', (1280, 1152)),
                                                ('scanlines', 'megadrive-320', (1280, 960))])
def test_bundled_display_examples_have_valid_hashes_commands_and_unscaled_crops(folder, profile, size):
    from hashlib import sha256
    import json
    from pathlib import Path
    import shlex

    root = Path(__file__).resolve().parents[1]
    directory = root / 'samples' / folder
    manifest = json.loads((directory / 'manifest.json').read_text())
    source = manifest['source']
    assert source['public'] is True
    assert sha256((root / 'samples/sources' / source['file']).read_bytes()).hexdigest() == source['reference_sha256']
    assert len(manifest['examples']) == 3
    for example in manifest['examples']:
        assert sha256((directory / example['filename']).read_bytes()).hexdigest() == example['sha256']
        assert sha256((directory / example['crop']).read_bytes()).hexdigest() == example['crop_sha256']
        args = build_parser().parse_args(shlex.split(example['command'])[1:])
        assert args.profile == profile and args.scale == (8 if profile == 'gameboy' else 4)
        with Image.open(directory / example['filename']) as full, Image.open(directory / example['crop']) as crop:
            assert full.size == size and crop.size == (512, 512)
            assert full.crop(example['crop_box']).tobytes() == crop.tobytes()
