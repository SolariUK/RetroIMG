# Conversion options

Optional [display effects](display-effects.md) apply after conversion and preview
scaling. Game Boy LCD cells are available with any profile using
`--display-effect gameboy-lcd --scale 8`; the default is plain output.

## Palette/profile independence

Palettes can be mixed with geometries for experimentation:

```bash
retroimg convert photo.jpg hybrid.png --profile teletext --palette c64
```

Custom dimensions are also available:

```bash
retroimg convert photo.jpg custom.png --profile teletext --width 160 --height 150
```

For `--teletext-mode mosaic`, width must be divisible by 2 and height by 3.

## Compare modes with the same source

After activating the virtual environment, run these commands from the project
directory. Replace `/path/to/image.jpg` with your source image path. Outputs
are saved in the current directory; change their paths as needed.

```bash
# Bitmap, with and without dithering
retroimg convert /path/to/image.jpg output-bitmap.png \
    --teletext-mode bitmap --dither none --scale 6
retroimg convert /path/to/image.jpg output-bitmap-dither.png \
    --teletext-mode bitmap --dither floyd-steinberg --scale 6

# Mosaic, with and without dithering
retroimg convert /path/to/image.jpg output-mosaic.png \
    --teletext-mode mosaic --dither none --scale 6
retroimg convert /path/to/image.jpg output-mosaic-dither.png \
    --teletext-mode mosaic --dither floyd-steinberg --scale 6

# Alternate palettes, retaining Teletext's 2x3 cell constraints
retroimg convert /path/to/image.jpg output-mosaic-c64.png \
    --teletext-mode mosaic --palette c64 --scale 6
retroimg convert /path/to/image.jpg output-mosaic-spectrum.png \
    --teletext-mode mosaic --palette spectrum --scale 6

# Larger logical grid, with the same preview dimensions
retroimg convert /path/to/image.jpg output-mosaic-large.png \
    --teletext-mode mosaic --width 160 --height 150 --scale 3

# More saturated source colours before optimisation
retroimg convert /path/to/image.jpg output-mosaic-saturated.png \
    --teletext-mode mosaic --saturation 1.5 --scale 6
```

All eight outputs are 480x450 previews. `--scale` enlarges logical pixels using
nearest-neighbour scaling; it does not add image detail. The larger mosaic uses
an 80x50 cell grid rather than the default 40x25. Palette swaps do not enable C64
or Spectrum hardware constraints.

The default `--fit cover` crops to fill the logical raster. Use `--fit contain`
to keep the whole source with padding, or `--fit stretch` to fill without
preserving its aspect ratio. Dithering defaults to `none` in these examples
unless explicitly enabled.

## Dithering

`--dither` accepts `none` (the default), `floyd-steinberg` and `bayer`.
Floyd–Steinberg spreads quantisation error to neighbouring pixels. Bayer uses a
repeating threshold matrix for a regular patterned texture, with no error
diffusion. Both work with the existing source colour adjustments.

Choose a **2x2, 4x4 or 8x8** matrix with `--bayer-size`; the default is 4x4.
Larger matrices provide finer coverage increments over a larger repeating tile.
They do not change the image resolution or preview scale. The option is rejected
unless `--dither bayer` is selected.

```bash
# Bayer with the default 4x4 matrix
retroimg convert /path/to/image.jpg cpc-bayer.png \
    --profile cpc-mode0 --cpc-mode constrained --dither bayer --scale 2

# Compare a larger matrix with the existing landscape adjustments
retroimg convert /path/to/image.jpg c64-bayer8.png \
    --profile c64-multicolour --c64-mode multicolour \
    --dither bayer --bayer-size 8 --hue-shift 20 --green-gain 1.15 --scale 2

# Smaller pattern, retaining Teletext cell constraints
retroimg convert /path/to/image.jpg teletext-bayer2.png \
    --profile teletext --teletext-mode mosaic --dither bayer --bayer-size 2 --scale 6

# HAM6 uses legal, state-dependent colour choices
retroimg convert /path/to/image.jpg amiga-ham-bayer.png \
    --profile amiga-lores --amiga-mode ham --dither bayer --scale 2
```

For an arbitrary palette, ordered conversion finds the nearest colour, then
chooses its best mixing partner by projecting the source RGB onto the segments
joining it to other available colours. Mixing proportions are rounded to coverage
the selected 2×2, 4×4 or 8×8 matrix can actually represent. Scoring balances the
average weighted RGB error against visible contrast between mixing colours:
distant partners need a worthwhile improvement, reducing isolated dark or bright
dots. The penalty is relative to the anchor's nearest available colour spacing,
so adjacent shade ramps and two-colour palettes retain normal ordered coverage.
It remains a nearest-anchor heuristic, not an exhaustive search of every pair
or a neighbourhood-aware filter. Equal scores prefer closer colours. Complete regular RGB grids,
such as unrestricted Amiga RGB12, instead use ordered rounding between adjacent
levels independently for each channel.

Target palette fitting stays the same: Bayer assigns pixels using the selected
cell/screen colours. A cell fitted to a single colour remains solid. Teletext,
Spectrum and C64 retain global logical matrix coordinates across cell boundaries.
Atari applies the matrix to its independent block bits and band number, then
expands shared scanlines and repeated/mirrored halves. HAM evaluates the 64 legal
codes at each pixel using the held colour, then makes its ordered choice; it
remains greedy and may show colour fringes. All outputs retain their mode's
colour and pattern constraints. Existing `none` and Floyd–Steinberg conversion
remain unchanged.

## Source colour adjustments

Source adjustments below run before palette conversion. The separate
`--display-brightness` control runs after enlargement and display effects;
it adjusts only the finished RGB preview. See [pipeline order](display-effects.md#source-brightness-and-display-brightness).

Independent `--bloom-strength` (0 to 1; default 0/off) adds highlight glow after
any display treatment or by itself. `--bloom-radius` controls its Gaussian spread
in logical pixel widths (0.25 to 8; default 1). Display brightness remains last.
For example, combine `--display-effect crt-aperture --effect-strength 0.35` with
`--bloom-strength 0.25 --bloom-radius 1 --scale 4`.

`--chromatic-strength` (0 to 1; default 0/off) adds radial colour separation after
enlargement and before the selected display treatment. Try `0.25` for subtle
fringing, alone or combined with the CRT grille and bloom. It does not change the
palette conversion, output dimensions, or final position of display brightness.

`--rf-strength` (0 to 1; default 0/off) adds horizontal colour bleed and smearing
after enlargement and before chromatic aberration and the display treatment.
Try `0.35` for subtle degradation or `0.85` for stronger colour trails. It works
with every profile and combines with all the other display controls.

Optional adjustments apply after resizing and before palette/cell optimisation
for every profile. Processing order is **brightness → contrast → saturation →
hue shift → RGB gains → sharpen**. Each stage works on 8-bit RGB values and clips results
to 0–255 before the next stage.
Neutral defaults preserve existing conversion output.

`--sharpen` is an amount from **0 to 4**, default **0/off**. Try `--sharpen 1`
for moderate edge enhancement. It uses Pillow's unsharp mask with a fixed radius
of one logical pixel and threshold of three RGB levels; the amount controls the
strength (1 means 100%). It runs after the other source adjustments at the
resized logical resolution, before palette fitting, hardware constraints and
dithering. The output still obeys the selected palette and cell/tile rules.
Higher values can emphasise noise or create light/dark halos around edges.
Use `--sharpen 0` to disable a value inherited from a preset. Pixelation remains
an independent original-colour workflow and does not use this control.

```bash
# Lift a dark source and strengthen contrast before fitting CPC screen colours
retroimg convert /path/to/image.jpg output-toned.png \
    --profile cpc-mode0 --cpc-mode constrained --dither bayer \
    --brightness 1.1 --contrast 1.2 --sharpen 1 --scale 2

# Boost green by 15%
retroimg convert /path/to/image.jpg output-green.png \
    --teletext-mode mosaic --green-gain 1.15 --scale 6

# Rotate hue and adjust channel balance
retroimg convert /path/to/image.jpg output-balanced.png \
    --teletext-mode mosaic --hue-shift 10 \
    --red-gain 0.9 --green-gain 1.15 --blue-gain 1.0 --scale 6
```

`--brightness` and `--contrast` are finite, non-negative factors with a default
of `1.0`. Values below 1 reduce the effect and values above 1 increase it:

| Control | `0` | `1` | Above `1` |
| --- | --- | --- | --- |
| Brightness | Black source | Unchanged | Multiply RGB values to brighten |
| Contrast | Flat grey at mean luminance | Unchanged | Push values away from mean luminance |

Brightness multiplies channel intensities; it does not add a fixed offset, so
black remains black. Contrast uses Pillow's `ImageEnhance.Contrast`, centred
on the rounded mean luminance of the brightness-adjusted logical image. With
`--fit contain`, this includes any padding. Strong increases may clip detail in
shadows or highlights. These operations precede quantisation: the output still
obeys its palette and constraints, and subtle changes may map to identical
colours in a limited palette. Both controls work with every target and dither.

The guide asks for them under **Adjust source image**, retains them when
editing, and includes them in the summary, generated command and saved presets.
Existing presets that omit them use neutral defaults. Use explicit
`--brightness 1 --contrast 1` to reset values inherited from a preset.

`--hue-shift` rotates HSV hue in degrees (default `0`); positive 120 degrees
maps red to green, and negative values rotate the other way. Rotation wraps at
360 degrees. Greys remain neutral under hue rotation.

`--red-gain`, `--green-gain` and `--blue-gain` multiply the respective RGB
channels (default `1.0`). Values below 1 reduce a channel, values above 1 boost
it, and zero removes it. Results clip to 0–255. Gains must be finite and
non-negative; hue must be finite. These adjustments affect the whole image,
including sky, skin and neutral colours. A green boost can still leave grass
mapped to yellow when red remains high; a small red reduction may help, but
also changes other areas. All outputs still use the selected palette.
