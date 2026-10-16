"""Keep legacy entry points usable while shared algorithms stay target-independent."""
import importlib
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.conversion_modes import get_profile_quantizer, get_quantizer
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile


@pytest.mark.parametrize('target', ['teletext', 'spectrum', 'c64', 'cpc'])
def test_legacy_target_exports_are_canonical_objects(target):
    legacy = importlib.import_module(f'retroimg.{target}')
    canonical = importlib.import_module(f'retroimg.targets.{target}')
    for name in legacy.__all__:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_legacy_shared_algorithm_exports():
    from retroimg.cellfit import SharedBackgroundFit, fit_shared_background
    from retroimg.constraints.shared_background import SharedBackgroundFit as NewFit, fit_shared_background as new_fit
    from retroimg.palettefit import select_palette_indices
    from retroimg.constraints.global_palette import select_palette_indices as new_select
    from retroimg.constraints import quantize_cells
    from retroimg.constraints.cells import quantize_cells as new_cells
    assert SharedBackgroundFit is NewFit
    assert fit_shared_background is new_fit
    assert select_palette_indices is new_select
    assert quantize_cells is new_cells


def test_old_teletext_constraint_entry_points_and_render_keyword():
    from retroimg import constraints, render
    from retroimg.targets import teletext
    source = Image.new('RGB', (2, 3), 'red')
    palette = get_palette('teletext')
    for dither in ('none', 'floyd-steinberg'):
        page = constraints.optimise_teletext_mosaic(source, palette, dither)
        assert page == teletext.optimise_teletext_mosaic(source, palette, dither)
        raster = constraints.quantize_teletext_mosaic(source, palette, dither)
        assert raster == teletext.quantize_teletext_mosaic(source, palette, dither)
        assert render.rasterize_teletext(page=page) == teletext.rasterize_teletext(page)
        assert constraints.constrain_teletext_mosaic(raster) == teletext.constrain_teletext_mosaic(raster)


@pytest.mark.parametrize('target,optimiser,rasterizer', [
    ('spectrum', 'optimise_spectrum_attributes', 'rasterize_spectrum'),
    ('c64', 'optimise_c64_multicolour', 'rasterize_c64_multicolour'),
    ('cpc', 'optimise_cpc', 'rasterize_cpc'),
])
def test_legacy_renderer_forwards_to_target(target, optimiser, rasterizer):
    module = importlib.import_module(f'retroimg.targets.{target}')
    legacy = importlib.import_module('retroimg.render')
    model = getattr(module, optimiser)(Image.new('RGB', (8, 8), 'red'))
    assert getattr(legacy, rasterizer)(image=model) == getattr(module, rasterizer)(model)


def test_shared_modules_do_not_import_targets():
    script = '''
import retroimg.render
import retroimg.constraints.cells
import retroimg.constraints.shared_background
import retroimg.constraints.global_palette
import sys
assert not any(name.startswith('retroimg.targets.') for name in sys.modules)
assert not any(name in sys.modules for name in ('retroimg.c64', 'retroimg.cpc', 'retroimg.spectrum', 'retroimg.teletext'))
'''
    subprocess.run([sys.executable, '-c', script], check=True)


@pytest.mark.parametrize('profile,option,mode', [
    ('teletext', 'teletext_mode', 'mosaic'),
    ('spectrum', 'spectrum_mode', 'attributes'),
    ('c64-multicolour', 'c64_mode', 'multicolour'),
    ('cpc-mode0', 'cpc_mode', 'constrained'),
    ('cpc-mode1', 'cpc_mode', 'constrained'),
    ('cpc-mode2', 'cpc_mode', 'constrained'),
])
def test_registry_dispatch(profile, option, mode):
    target = get_profile(profile)
    assert get_profile_quantizer(target, **{option: mode}) is get_quantizer(target.constraint_model, mode)
    assert get_profile_quantizer(target) is get_quantizer(target.constraint_model, 'bitmap')


def test_registry_rejects_unknown_option_names():
    with pytest.raises(ValueError, match='unknown mode options'):
        get_profile_quantizer(get_profile('teletext'), typo_mode='bitmap')
