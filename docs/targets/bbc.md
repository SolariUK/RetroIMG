# BBC Micro modes 0, 1, 2, 4 and 5

The `bbc` palette provides eight steady physical colours in BBC colour-number
order: black, red, green, yellow, blue, magenta, cyan and white. Each RGB channel
is idealised to 0 or 255. Mode dimensions, colour numbering and logical-colour
remapping follow the [BBC Microcomputer User Guide](https://www.bbcmicrobot.com/docs/BBC_User_Guide.pdf)
(printed pages 164–165, 224 and 301).

| Profile | Logical raster | Relative pixel aspect | Constrained steady colours | Scale for a 640x512 preview |
| --- | --- | --- | --- | --- |
| `bbc-mode0` | 640x256 | 1:2 | 2 from 8 | 1 |
| `bbc-mode1` | 320x256 | 1:1 | 4 from 8 | 2 |
| `bbc-mode2` | 160x256 | 2:1 | All 8 | 2 |
| `bbc-mode4` | 320x256 | 1:1 | 2 from 8 | 2 |
| `bbc-mode5` | 160x256 | 2:1 | 4 from 8 | 2 |

Every profile defaults to `--bbc-mode bitmap`: unrestricted palette use, with
palette swaps allowed. Add `--bbc-mode constrained` to select a screen-wide
palette within the mode's limit. Two-colour modes may choose any pair, not just
black and white; four-colour modes may choose any four steady colours. There
are no per-cell colour restrictions. Selection reuses the generic whole-image
selector described above: exhaustive pair fitting, deterministic greedy/swap
fitting for four colours, with up to 4096 weighted RGB samples. Dithering uses
the full prepared image and only the selected colours.

Mode 2 has **16 logical hardware slots**, but its default upper eight are
flashing colour pairs, not eight extra steady RGB colours. This static converter
uses its eight steady physical colours. Consequently Mode 2 bitmap and
constrained output match when using the built-in BBC palette and identical
settings. Unrestricted palette swaps can still produce different aesthetics.
Modes 3 and 6 are text modes and are omitted. BBC Mode 7 control-code emulation
is separate future work; the existing visual Teletext profile remains available.

```bash
# Mode 0: choose two colours and retain fine horizontal detail
retroimg convert /path/to/image.jpg output-bbc0.png \
    --profile bbc-mode0 --bbc-mode constrained \
    --dither floyd-steinberg --scale 1

# Mode 1: four automatically selected screen colours
retroimg convert /path/to/image.jpg output-bbc1.png \
    --profile bbc-mode1 --bbc-mode constrained --scale 2

# Mode 2: wide pixels and all eight steady colours
retroimg convert /path/to/image.jpg output-bbc2.png \
    --profile bbc-mode2 --bbc-mode constrained \
    --dither floyd-steinberg --scale 2

# Mode 4: two colours at 320x256
retroimg convert /path/to/image.jpg output-bbc4.png \
    --profile bbc-mode4 --bbc-mode constrained --scale 2

# Mode 5: four colours, with hue and green gain adjustments
retroimg convert /path/to/image.jpg output-bbc5-adjusted.png \
    --profile bbc-mode5 --bbc-mode constrained \
    --hue-shift 20 --green-gain 1.15 --scale 2

# Keep BBC geometry while using all 27 CPC colours
retroimg convert /path/to/image.jpg output-bbc1-cpc.png \
    --profile bbc-mode1 --bbc-mode bitmap --palette cpc --scale 2
```

Constrained conversion requires the built-in `bbc` palette. Custom dimensions
remain available without cell alignment requirements, as visual experiments.
Previews account for relative pixel aspect when fitting and scaling; Mode 0
stretches rows rather than discarding logical columns. This gives consistent
relative geometry between modes, not a simulation of a particular PAL monitor.
Flashing colours, raster palette changes, hardware screen-file export and CRT
effects are not implemented.

[All targets](README.md) · [Project README](../../README.md)
