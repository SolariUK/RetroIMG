# Amstrad CPC modes 0, 1 and 2

The `cpc` palette contains all 27 firmware colours in colour-number order.
It uses idealised RGB channel levels **0, 128 and 255**, corresponding to the
CPC's three levels per channel. These are digital approximations rather than
measurements of a particular analogue monitor. Colour numbering and RGB mixing
are documented in the [CPC Gate Array reference](https://cpctech.cpcwiki.de/docs/garray.html);
mode dimensions and ink limits appear in the [CPC464 manual](https://www.manualslib.com/manual/862146/Amstrad-Cpc464.html?page=107).

| Profile | Logical raster | Relative pixel aspect | Constrained ink limit | Scale for a 640x400 preview |
| --- | --- | --- | --- | --- |
| `cpc-mode0` | 160x200 | 2:1 | 16 from 27 | 2 |
| `cpc-mode1` | 320x200 | 1:1 | 4 from 27 | 2 |
| `cpc-mode2` | 640x200 | 1:2 | 2 from 27 | 1 |

Geometry is independent of colour constraints. Each profile defaults to
`--cpc-mode bitmap`, allowing unrestricted use of all palette colours and
palette swaps. Add `--cpc-mode constrained` to enforce the image-wide ink limit.
Unlike Teletext, Spectrum and C64 multicolour, CPC has no per-cell colour limit
in these modes. Mode 2 can use any selected pair of CPC colours, not just black
and white. Border colours, flashing inks and raster palette changes are excluded.

```bash
# Unrestricted CPC palette conversion in mode 0 geometry (the default)
retroimg convert /path/to/image.jpg output-cpc0-free.png \
    --profile cpc-mode0 --cpc-mode bitmap --scale 2

# Limit the whole image to 16 CPC inks
retroimg convert /path/to/image.jpg output-cpc0.png \
    --profile cpc-mode0 --cpc-mode constrained --scale 2

# Mode 1: choose four inks and dither using that global palette
retroimg convert /path/to/image.jpg output-cpc1.png \
    --profile cpc-mode1 --cpc-mode constrained \
    --dither floyd-steinberg --scale 2

# Mode 2: choose two inks, preserving every narrow logical pixel
retroimg convert /path/to/image.jpg output-cpc2.png \
    --profile cpc-mode2 --cpc-mode constrained \
    --dither floyd-steinberg --scale 1

# Hue and colour balance apply before selecting screen inks
retroimg convert /path/to/image.jpg output-cpc0-adjusted.png \
    --profile cpc-mode0 --cpc-mode constrained \
    --hue-shift 20 --green-gain 1.15 --scale 2

# Mix mode 1 geometry with the C64 palette, without CPC ink restrictions
retroimg convert /path/to/image.jpg output-cpc1-c64.png \
    --profile cpc-mode1 --cpc-mode bitmap --palette c64 --scale 2
```

Constrained mode requires the built-in `cpc` palette. Custom width and height
are supported without cell-alignment restrictions; they are visual experiments
rather than standard CPC screens. Existing profiles and defaults are unchanged.
All CPC previews account for relative pixel aspect during fitting and rendering.
Mode 2 stretches preview pixels vertically instead of discarding logical columns
at scale 1. The aspect model preserves relative mode geometry; it does not
simulate a particular monitor.

### Screen palette selection

Screen inks are selected against weighted RGB error from the prepared source.
One/two-colour selection searches every candidate; four/sixteen-colour selection
uses greedy additions followed by up to eight improving one-colour swaps.
The larger searches are deterministic heuristics, not guaranteed global optima.

Selection uses the complete RGB histogram when it contains at most 4096 unique
colours. Larger histograms use a deterministic, frequency-weighted sample of up
to 4096 RGB colours, so rare colours may be omitted during fitting. The Python
helper `select_palette_indices(..., max_samples=None)` can fit the complete
histogram. Palette selection always precedes dithering; **every output pixel is
quantised from the full prepared source**. Floyd–Steinberg diffusion runs across
the whole image using only the chosen screen inks. Hue, saturation and RGB gain
adjustments can therefore change which inks are selected.

### CPC firmware palette RGB values

These numbers identify firmware colours, not pen slots or Gate Array hardware
register values. The historical colour name `white` is the middle RGB level;
`bright-white` is full white.

| Firmware colour | Name | RGB |
| --- | --- | --- |
| 0 | black | 0, 0, 0 |
| 1 | blue | 0, 0, 128 |
| 2 | bright-blue | 0, 0, 255 |
| 3 | red | 128, 0, 0 |
| 4 | magenta | 128, 0, 128 |
| 5 | mauve | 128, 0, 255 |
| 6 | bright-red | 255, 0, 0 |
| 7 | purple | 255, 0, 128 |
| 8 | bright-magenta | 255, 0, 255 |
| 9 | green | 0, 128, 0 |
| 10 | cyan | 0, 128, 128 |
| 11 | sky-blue | 0, 128, 255 |
| 12 | yellow | 128, 128, 0 |
| 13 | white | 128, 128, 128 |
| 14 | pastel-blue | 128, 128, 255 |
| 15 | orange | 255, 128, 0 |
| 16 | pink | 255, 128, 128 |
| 17 | pastel-magenta | 255, 128, 255 |
| 18 | bright-green | 0, 255, 0 |
| 19 | sea-green | 0, 255, 128 |
| 20 | bright-cyan | 0, 255, 255 |
| 21 | lime | 128, 255, 0 |
| 22 | pastel-green | 128, 255, 128 |
| 23 | pastel-cyan | 128, 255, 255 |
| 24 | bright-yellow | 255, 255, 0 |
| 25 | pastel-yellow | 255, 255, 128 |
| 26 | bright-white | 255, 255, 255 |

[All targets](README.md) · [Project README](../../README.md)
