"""Check target-independent algorithms and declarative mode dispatch."""
import subprocess
import sys

import pytest

from retroimg.conversion_modes import get_profile_quantizer, get_quantizer
from retroimg.profiles import get_profile


def test_shared_modules_do_not_import_targets():
    script = '''
import retroimg.render
import retroimg.constraints.cells
import retroimg.constraints.shared_background
import retroimg.constraints.global_palette
import sys
assert not any(name.startswith('retroimg.targets.') for name in sys.modules)
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
