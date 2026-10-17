"""Compatibility imports; new callers should use the machine palette modules."""
from .megadrive import MEGADRIVE, MEGADRIVE_RGB
from .snes import SNES, SNES_RGB

__all__ = ['MEGADRIVE', 'MEGADRIVE_RGB', 'SNES', 'SNES_RGB']
