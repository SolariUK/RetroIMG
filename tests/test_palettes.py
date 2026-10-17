"""Public palette lookup and earlier import paths retain canonical objects."""
from importlib import import_module

import pytest

from retroimg.palettes import PALETTES, get_palette
from retroimg.palettes import builtin, consoles


@pytest.mark.parametrize('module,constant,name', [
    ('teletext', 'TELETEXT', 'teletext'), ('c64', 'C64', 'c64'),
    ('spectrum', 'SPECTRUM', 'spectrum'), ('cpc', 'CPC', 'cpc'),
    ('bbc', 'BBC', 'bbc'), ('amiga', 'AMIGA', 'amiga'),
    ('atari', 'ATARI_NTSC', 'atari2600-ntsc'), ('atari', 'ATARI_PAL', 'atari2600-pal'),
    ('megadrive', 'MEGADRIVE', 'megadrive'), ('snes', 'SNES', 'snes'),
])
def test_palette_definitions_registry_and_legacy_exports_share_objects(module, constant, name):
    owner = import_module('retroimg.palettes.' + module)
    palette = getattr(owner, constant)
    assert get_palette(name) is palette
    assert PALETTES[name] is palette
    assert getattr(builtin, constant) is palette


def test_legacy_grid_and_console_imports_share_objects():
    from retroimg.palettes.amiga import AMIGA_RGB
    from retroimg.palettes.megadrive import MEGADRIVE, MEGADRIVE_RGB
    from retroimg.palettes.snes import SNES, SNES_RGB
    assert builtin.AMIGA_RGB is AMIGA_RGB
    assert consoles.MEGADRIVE is MEGADRIVE
    assert consoles.MEGADRIVE_RGB is MEGADRIVE_RGB
    assert consoles.SNES is SNES
    assert consoles.SNES_RGB is SNES_RGB
