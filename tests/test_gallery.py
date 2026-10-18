import json
from pathlib import Path

from PIL import Image
import pytest

from examples.generate_gallery import (
    FAMILIES, check_constraints, export_public_gallery, variants_for,
)
from retroimg.model import IndexedImage
from retroimg.palettes import get_palette


def test_example_matrix_covers_all_modes_and_adjustments():
    assert sum(len(variants_for(family)) for family in FAMILIES) == 178
    assert sum(len(variants_for(family, adjusted=True)) for family in FAMILIES) == 274
    for family in FAMILIES:
        variants = variants_for(family, adjusted=True)
        assert len({variant.slug for variant in variants}) == len(variants)
        assert any(variant.options.get('dither') == 'none' for variant in variants)
        assert any(variant.options.get('dither') == 'floyd-steinberg' for variant in variants)


def test_c64_check_rejects_locally_legal_cells_without_shared_background():
    palette = get_palette('c64')
    image = IndexedImage(8, 8, palette, ((0, 1, 2, 3, 4, 5, 6, 7),) * 8)
    with pytest.raises(AssertionError, match='background'):
        check_constraints(image, dict(c64_mode='multicolour'))
    valid = IndexedImage(8, 8, palette, ((1, 2, 3, 1, 4, 5, 6, 4),) * 8)
    check_constraints(valid, dict(c64_mode='multicolour'))  # Background slot may be unused.


@pytest.mark.parametrize('palette,pixels,settings', [
    ('c64', ((0, 1, 2, 0, 1, 2, 0, 1),) * 8, dict(c64_mode='hires')),
    ('teletext', ((0, 1), (2, 0), (0, 0)), dict(teletext_mode='mosaic')),
    ('spectrum', ((2, 11) * 4,) * 8, dict(spectrum_mode='attributes')),
    ('cpc', ((0, 1, 2),), dict(profile_name='cpc-mode2', cpc_mode='constrained')),
    ('bbc', ((0, 1, 2),), dict(profile_name='bbc-mode0', bbc_mode='constrained')),
    ('bbc', ((0, 1, 2),), dict(profile_name='amiga-lores', amiga_mode='constrained', colours=2)),
    ('cpc', ((1,),), dict(profile_name='amiga-lores', amiga_mode='constrained', colours=32)),
])
def test_checks_reject_constraint_violations(palette, pixels, settings):
    image = IndexedImage(len(pixels[0]), len(pixels), get_palette(palette), pixels)
    with pytest.raises((AssertionError, ValueError)):
        check_constraints(image, settings)


def test_public_export_excludes_private_files_and_metadata(tmp_path):
    local = tmp_path / 'local'
    output = tmp_path / 'public'
    sources = []
    entries = []
    for identifier, public in [('public-source', True), ('PRIVATE_SENTINEL', False)]:
        directory = local / identifier
        (directory / 'cpc').mkdir(parents=True)
        Image.new('RGB', (1, 1)).save(directory / 'source-preview.png')
        Image.new('RGB', (1, 1)).save(directory / 'cpc' / 'example.png')
        Image.new('RGB', (1, 1)).save(directory / 'cpc' / 'comparison.jpg')
        (directory / 'cpc' / 'commands.md').write_text(identifier)
        sources.append(dict(id=identifier, title=identifier, public=public, credit=identifier,
                            rights='CC0' if public else identifier, sha256=identifier, source=None))
        entries.append(dict(source=identifier, family='cpc', label=identifier,
                            png=f'{identifier}/cpc/example.png', colours_used=1))
    manifest = dict(version=1, public_only=False, sources=sources, outputs=entries, families=['cpc'])
    export_public_gallery(local, output, manifest)
    exported = json.loads((output / 'manifest.json').read_text())
    assert exported['public_only'] is True
    assert [source['id'] for source in exported['sources']] == ['public-source']
    assert (output / 'public-source/cpc/example.png').is_file()
    assert not (output / 'PRIVATE_SENTINEL').exists()
    for path in output.rglob('*'):
        assert 'PRIVATE_SENTINEL' not in str(path)
        if path.is_file():
            assert b'PRIVATE_SENTINEL' not in path.read_bytes()
    with pytest.raises(ValueError, match='new output directory'):
        export_public_gallery(local, output, manifest)


CATALOG_PATH = Path(__file__).resolve().parents[1] / 'examples' / 'sources.json'
PUBLIC_SOURCES = [source for source in json.loads(CATALOG_PATH.read_text()) if source['public']]


@pytest.mark.parametrize('source', PUBLIC_SOURCES, ids=lambda source: source['id'])
def test_bundled_reference_assets_match_catalogue(source):
    from hashlib import sha256
    from examples.generate_gallery import BUNDLED_SOURCES

    path = BUNDLED_SOURCES / source['file']
    assert sha256(path.read_bytes()).hexdigest() == source['reference_sha256']
    with Image.open(path) as image:
        assert list(image.size) == source['reference_size']
        image.verify()
    assert source['rights'] and source['credit']
    assert source['source'] or source['id'] == 'diagnostic-chart'


def test_bundled_directory_contains_only_catalogued_public_assets():
    from examples.generate_gallery import BUNDLED_SOURCES

    assert {path.name for path in BUNDLED_SOURCES.iterdir()} == {source['file'] for source in PUBLIC_SOURCES}
    assert {'portrait-colour', 'lush-landscape', 'green-hills', 'portrait-man'} <= {
        source['id'] for source in PUBLIC_SOURCES}


@pytest.mark.parametrize('identifier', [
    'macaws-cpc', 'macaws-teletext', 'lush-landscape-c64',
    'lush-landscape-spectrum', 'macaws-bbc', 'portrait-colour-amiga',
    'lush-landscape-atari2600', 'macaws-adjustments',
    'macaws-megadrive', 'lush-landscape-snes',
    'macaws-nes', 'macaws-mastersystem', 'portrait-colour-gameboy',
    'macaws-cga', 'portrait-colour-ega',
])
def test_curated_sheets_retain_public_provenance_and_valid_commands(identifier):
    from hashlib import sha256
    import shlex
    from retroimg.cli import build_parser

    directory = CATALOG_PATH.parents[1] / 'samples' / 'comparisons'
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    entry = next(item for item in manifest['comparisons'] if item['sheet'] == identifier + '.png')
    source = entry['source']
    original = next(item for item in PUBLIC_SOURCES if item['id'] == source['id'])
    assert source['public'] is True
    assert all(source[key] == value for key, value in original.items())
    assert source['sha256'] == original['reference_sha256']
    assert entry['sheet'] == entry['sheets'][0]['filename']
    assert entry['panel_size'] == entry['sheets'][0]['size']
    assert entry['sha256'] == entry['sheets'][0]['sha256']
    tile_count = 0
    for part in entry['sheets']:
        assert part['first_tile'] == tile_count
        assert 1 <= part['tiles'] <= 6
        tile_count += part['tiles']
        sheet = directory / part['filename']
        assert sha256(sheet.read_bytes()).hexdigest() == part['sha256']
        with Image.open(sheet) as image:
            assert image.size == tuple(part['size'])
            assert image.width == 1328
            assert image.height <= 1944
            assert image.format == 'PNG'
            image.verify()
    assert tile_count == len(entry['variants']) + int(entry['show_source'])
    assert 1 <= len(entry['variants']) + int(entry['show_source']) <= 20
    for variant in entry['variants']:
        arguments = build_parser().parse_args(shlex.split(variant['command'])[1:])
        assert arguments.input == Path('/path/to/image.jpg')
        assert arguments.dither == variant['settings']['dither']


def test_curated_samples_are_bounded_and_cover_all_target_families():
    from examples.generate_samples import panel_size, selections, sheet_names

    panels = selections()
    assert len(panels) == 15
    assert set(FAMILIES) <= {panel.family for panel in panels}
    for panel in panels:
        assert panel_size(panel)[0] == 1328
        assert panel_size(panel)[1] <= 6312
        assert len({variant.slug for variant in panel.variants}) == len(panel.variants)
    directory = CATALOG_PATH.parents[1] / 'samples' / 'comparisons'
    assert {p.name for p in directory.iterdir()} == {
        'README.md', 'manifest.json', *(name for panel in panels for name in sheet_names(panel))}


def test_sample_modes_and_greener_c64_controls_are_represented():
    from examples.generate_samples import selections

    panels = {panel.family: panel for panel in selections()}
    assert panels['teletext'].source == 'macaws'
    assert {v.options['teletext_mode'] for v in panels['teletext'].variants} == {'bitmap', 'mosaic'}
    cpc = {tuple(v.options[key] for key in ('profile_name', 'cpc_mode', 'dither'))
           for v in panels['cpc'].variants}
    assert cpc == {(f'cpc-mode{mode}', constraint, dither)
                   for mode in (0, 1, 2) for constraint in ('bitmap', 'constrained')
                   for dither in ('none', 'floyd-steinberg', 'bayer')}
    assert any(v.options.get('saturation', 1) > 1 and v.options.get('green_gain', 1) > 1
               and v.options.get('hue_shift') == 20 for v in panels['c64'].variants)
    assert {v.options['profile_name'] for v in panels['bbc'].variants} == {
        f'bbc-mode{mode}' for mode in (0, 1, 2, 4, 5)}
    assert {'ehb', 'ham', 'constrained', 'bitmap'} <= {
        v.options.get('amiga_mode', 'bitmap') for v in panels['amiga'].variants}
    assert {v.options['atari_mode'] for v in panels['atari2600'].variants} == {
        'bitmap', 'playfield', 'repeat', 'mirror'}


def test_sample_refresh_refuses_unmanaged_files(tmp_path):
    from examples.generate_samples import generate_samples

    directory = tmp_path / 'samples'
    directory.mkdir()
    precious = directory / 'my-photo.png'
    precious.write_bytes(b'keep')
    with pytest.raises(ValueError, match='exists'):
        generate_samples(directory)
    with pytest.raises(ValueError, match='unmanaged'):
        generate_samples(directory, replace=True)
    assert precious.read_bytes() == b'keep'


def test_failed_sample_refresh_preserves_existing_panels(tmp_path, monkeypatch):
    from examples import generate_samples as generator

    directory = tmp_path / 'samples'
    directory.mkdir()
    existing = directory / 'macaws-cpc.png'
    existing.write_bytes(b'previous panel')
    def fail(*args, **kwargs):
        raise OSError('conversion failed')
    monkeypatch.setattr(generator, 'convert_file', fail)
    with pytest.raises(OSError, match='conversion failed'):
        generator.generate_samples(directory, replace=True)
    assert existing.read_bytes() == b'previous panel'
    assert list(tmp_path.iterdir()) == [directory]


def test_catalogue_gallery_totals():
    catalog = json.loads(CATALOG_PATH.read_text())
    def output_count(sources):
        return sum(len(variants_for(family, source.get('adjusted', False)))
                   for source in sources for family in FAMILIES)
    assert output_count(catalog) == 1794
    assert output_count(PUBLIC_SOURCES) == 1342


def test_dither_comparison_matrix_and_reproducible_options():
    from examples.generate_gallery import dither_variants_for
    total = 0
    for family in FAMILIES:
        variants = dither_variants_for(family)
        assert all(variant.label.isascii() for variant in variants)  # Pillow 10 bitmap-font compatibility.
        assert len({variant.slug for variant in variants}) == len(variants)
        assert {v.options['dither'] for v in variants} == {'none', 'floyd-steinberg', 'bayer'}
        assert {v.options['bayer_size'] for v in variants if v.options['dither'] == 'bayer'} == {2, 4, 8}
        assert all('bayer_size' not in v.options for v in variants if v.options['dither'] != 'bayer')
        total += len(variants)
    assert total == 120


@pytest.mark.parametrize('source_ids', [('missing',), ('picard',)])
def test_selected_sources_reject_unknown_and_excluded_ids(tmp_path, source_ids):
    from examples.generate_gallery import generate, BUNDLED_SOURCES
    output = tmp_path / 'gallery'
    with pytest.raises(ValueError, match='unknown or excluded'):
        generate(BUNDLED_SOURCES, output, ('teletext',), True, source_ids=source_ids)
    assert not output.exists()


def test_selected_public_dither_gallery_runs_and_records_matrix_sizes(tmp_path):
    from examples.generate_gallery import generate, BUNDLED_SOURCES
    output = tmp_path / 'gallery'
    manifest = generate(BUNDLED_SOURCES, output, ('teletext',), True,
                        dither_comparison=True, source_ids=('diagnostic-chart',))
    assert [source['id'] for source in manifest['sources']] == ['diagnostic-chart']
    assert len(manifest['outputs']) == 5
    assert {entry['settings']['bayer_size'] for entry in manifest['outputs']
            if entry['settings']['dither'] == 'bayer'} == {2, 4, 8}
    assert (output / 'index.html').is_file()
    assert (output / 'diagnostic-chart/teletext/comparison.jpg').is_file()
    commands = (output / 'diagnostic-chart/teletext/commands.md').read_text()
    assert '--dither bayer --' in commands
    assert '--bayer-size 8' in commands


@pytest.mark.parametrize('size', [(640, 480), (320, 200), (480, 450)])
def test_sample_tiles_preserve_converted_pixels(size):
    from examples.generate_samples import _tile

    # A one-pixel pattern exposes both interpolation and accidental scaling.
    image = Image.new('RGB', size)
    image.putdata([(255, 0, 0) if (x + y) % 2 else (0, 255, 255)
                   for y in range(size[1]) for x in range(size[0])])
    sheet = Image.new('RGB', (1328, 696))
    _tile(sheet, 0, 'Preview', image)
    left = 16 + (640 - size[0]) // 2
    top = 82 + (576 - size[1]) // 2
    assert sheet.crop((left, top, left + size[0], top + size[1])).tobytes() == image.tobytes()


def test_sample_sheet_split_preserves_every_tile(tmp_path):
    from examples.generate_samples import Panel, _save_sheets, _tile, panel_size

    panel = Panel('test', 'test', 'Split preview', (None,) * 7, False)
    sheet = Image.new('RGB', panel_size(panel))
    colours = [(i * 30, 255 - i * 30, i * 20) for i in range(7)]
    for i, colour in enumerate(colours):
        _tile(sheet, i, str(i), Image.new('RGB', (640, 576), colour))
    parts = _save_sheets(sheet, panel, tmp_path)
    assert [(part['first_tile'], part['tiles']) for part in parts] == [(0, 6), (6, 1)]
    for part in parts:
        with Image.open(tmp_path / part['filename']) as page:
            for local in range(part['tiles']):
                left = 16 + (local % 2) * 656
                top = 82 + (local // 2) * 624
                tile = page.crop((left, top, left + 640, top + 576))
                assert tile.getextrema() == tuple((v, v) for v in colours[part['first_tile'] + local])
