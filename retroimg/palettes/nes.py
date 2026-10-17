"""Common NTSC NES RGB approximation in six-bit PPU colour-code order.

The composite PPU has no definitive digital RGB palette. This is a familiar
preview approximation, without emphasis bits or a simulated TV decoder.
Colour data reference: https://pkg.go.dev/github.com/andrewthecodertx/go-nes-emulator/pkg/ppu#HardwarePalette
"""
from retroimg.model import Colour, Palette

_HEX = '''
545454 001e74 081090 300088 440064 5c0030 540400 3c1800
202a00 083a00 004000 003c00 00323c 000000 000000 000000
989698 084cc4 3032ec 5c1ee4 8814b0 a01464 982220 783c00
545a00 287200 087c00 007628 006678 000000 000000 000000
eceeec 4c9aec 787cec b062ec e454ec ec58b4 ec6a64 d48820
a0aa00 74c400 4cd020 38cc6c 38b4cc 3c3c3c 000000 000000
eceeec a8ccec bcbcec d4b2ec ecaeec ecaed4 ecb4b0 e4c490
ccd278 b4de78 a8e290 98e2b4 a0d6e4 a0a2a0 000000 000000
'''.split()
NES = Palette('nes', tuple(Colour(f'ppu-{code:02x}', tuple(bytes.fromhex(value)))
                           for code, value in enumerate(_HEX)),
              'NES 64 PPU colour codes; common NTSC RGB approximation, duplicate slots retained.')
# Exclude the problematic below-black $0D code from constrained output.
NES_SAFE_CODES = tuple(i for i in range(64) if i != 0x0d)
NES_SAFE = Palette('nes', tuple(NES.colours[i] for i in NES_SAFE_CODES))
