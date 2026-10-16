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
    assert sum(len(variants_for(family)) for family in FAMILIES) == 30
    assert sum(len(variants_for(family, adjusted=True)) for family in FAMILIES) == 42
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
    ('teletext', ((0, 1), (2, 0), (0, 0)), dict(teletext_mode='mosaic')),
    ('spectrum', ((2, 11) * 4,) * 8, dict(spectrum_mode='attributes')),
    ('cpc', ((0, 1, 2),), dict(profile_name='cpc-mode2', cpc_mode='constrained')),
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
