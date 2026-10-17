"""Check target-independent algorithms and declarative mode dispatch."""
import subprocess
import sys

import pytest

from retroimg.conversion_modes import get_profile_quantizer, get_quantizer
from retroimg.profiles import get_profile


def test_shared_modules_do_not_import_targets():
    script = '''
import retroimg.render
import retroimg.ordered
import retroimg.colour_spaces
import retroimg.constraints.adaptive_palette
import retroimg.constraints.binary_groups
import retroimg.constraints.cells
import retroimg.constraints.shared_background
import retroimg.constraints.global_palette
import retroimg.constraints.palette_banks
import sys
assert not any(name.startswith('retroimg.targets.') for name in sys.modules)
'''
    subprocess.run([sys.executable, '-c', script], check=True)


@pytest.mark.parametrize('profile,option,mode', [
    *[(f'megadrive-{width}{suffix}', 'megadrive_mode', 'tiles')
      for width in (320, 256) for suffix in ('', '-pal')],
    *[('snes', 'snes_mode', mode) for mode in ('tiles', 'indexed')],
    *[(f'amiga-{resolution}{suffix}', 'amiga_mode', 'constrained')
      for resolution in ('lores', 'hires') for suffix in ('', '-ntsc')],
    *[(f'amiga-lores{suffix}', 'amiga_mode', mode)
      for suffix in ('', '-ntsc') for mode in ('ehb', 'ham')],
    *[(f'atari2600-{standard}', 'atari_mode', mode)
      for standard in ('ntsc', 'pal') for mode in ('playfield', 'repeat', 'mirror')],
    ('teletext', 'teletext_mode', 'mosaic'),
    ('spectrum', 'spectrum_mode', 'attributes'),
    ('c64-multicolour', 'c64_mode', 'multicolour'),
    ('cpc-mode0', 'cpc_mode', 'constrained'),
    ('cpc-mode1', 'cpc_mode', 'constrained'),
    ('cpc-mode2', 'cpc_mode', 'constrained'),
    *[(f'bbc-mode{mode}', 'bbc_mode', 'constrained') for mode in (0, 1, 2, 4, 5)],
])
def test_registry_dispatch(profile, option, mode):
    target = get_profile(profile)
    assert get_profile_quantizer(target, **{option: mode}) is get_quantizer(target.constraint_model, mode)
    assert get_profile_quantizer(target) is get_quantizer(target.constraint_model, 'bitmap')


def test_registry_rejects_unknown_option_names():
    with pytest.raises(ValueError, match='unknown mode options'):
        get_profile_quantizer(get_profile('teletext'), typo_mode='bitmap')
