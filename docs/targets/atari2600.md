# Atari 2600

`atari2600-ntsc` uses a nominal 160x192 active picture and `atari2600-pal`
uses 160x228. Both preview at 4:3; at scale 2 this gives 512x384 and 608x456
PNGs respectively. These active picture sizes follow Atari's
[Stella Programmer's Guide](https://www.atariage.com/2600/programming/2600_101/docs/stella.html).
The console has programmable vertical timing; these are useful presets, not
its only possible picture heights.

The two named palettes preserve 128 even TIA colour-register slots in register
order: palette index `i` corresponds to register value `i * 2`. NTSC has 128
distinct RGB values; PAL has 104 because hue banks 0, 1, 14 and 15 share the
same eight grays. Our palettes are **idealised approximations**, generated
independently with nominal hue phases, a luminance ramp and a YIQ-to-RGB
transform. PAL uses its own interleaved hue order. They are not measured console
output or copied emulator palette tables. Analogue colours depend on the TIA,
console adjustment and television; hue, saturation and gain controls remain
useful. The [Stella emulator documentation](https://stella-emu.github.io/docs/index.html)
also describes separate NTSC/PAL palettes and adjustable colour reproduction.
There are no TV/CRT effects in these previews.

`--atari-mode bitmap` is the default unrestricted palette conversion at the
profile's full logical resolution. It also allows other named palettes and
custom dimensions, as with existing profiles.

The playfield modes require a logical width of 160 and either Atari palette.
They divide each row into 40 blocks, each four colour clocks wide:

| Mode | Pattern constraint |
| --- | --- |
| `playfield` | 40 independent blocks across the image |
| `repeat` | 20 blocks repeated in the right half |
| `mirror` | 20 blocks reflected into the right half |

Each band has one foreground/background colour pair. `--atari-row-height`
selects how many scanlines share the pattern and pair (default 2); use 1 for
finer detail or 4/8 for chunkier output. A final partial band is supported.
Custom heights are allowed; custom playfield widths are rejected.

The fitter evaluates every distinct palette pair against the prepared RGB
source. Samples sharing a pattern bit are fitted together, including both
halves in repeated/mirrored modes. Without dithering this minimises the same
weighted RGB squared error used elsewhere in retroimg. Ties follow palette
order. Floyd–Steinberg uses the selected pair and diffuses horizontally along
the independent pattern bits, resetting at each band. Group means are rounded
to 8-bit RGB for the dithering step; no dithering occurs inside a shared block.

```bash
# Unrestricted full-resolution Atari palette conversion
retroimg convert /path/to/image.jpg atari-bitmap.png \
    --profile atari2600-ntsc --dither floyd-steinberg --scale 2

# Independent playfield blocks, with the landscape adjustments
retroimg convert /path/to/image.jpg atari-playfield.png \
    --profile atari2600-ntsc --atari-mode playfield \
    --hue-shift 20 --green-gain 1.15 --dither floyd-steinberg --scale 2

# PAL mirrored playfield with chunkier vertical blocks
retroimg convert /path/to/image.jpg atari-mirror.png \
    --profile atari2600-pal --atari-mode mirror --atari-row-height 8 --scale 2

# Repeated halves; use --atari-mode mirror to compare symmetry
retroimg convert /path/to/image.jpg atari-repeat.png \
    --profile atari2600-ntsc --atari-mode repeat --scale 2

# Keep unrestricted palette/profile mixing
retroimg convert /path/to/image.jpg atari-c64-palette.png \
    --profile atari2600-ntsc --palette c64 --scale 2
```

These are visual playfield constraints. Independent halves correspond to
mid-line playfield updates; this converter does not model CPU scheduling,
sprites, score mode or timed colour changes within a line. Output is PNG;
Atari native export and executable ROM generation are outside the current scope.

[All targets](README.md) · [Project README](../../README.md)
