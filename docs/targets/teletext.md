# Teletext

The Teletext profile has two modes.

### Bitmap mode (default)

This intentionally preserves the colourful 80x75 low-resolution style from the
first version.  It uses the Teletext palette but does not impose mosaic-cell
restrictions.

```bash
retroimg convert photo.jpg output.png \
    --profile teletext \
    --teletext-mode bitmap \
    --dither floyd-steinberg \
    --scale 6
```

Because bitmap is the default, `--teletext-mode bitmap` may be omitted.

### Mosaic mode

This uses the same logical 80x75 raster, grouped into the authentic 40x25 grid
of 2x3 graphics cells.  Each cell is optimised to use at most two palette
colours, producing a visibly more Teletext-like result while retaining the
existing image conversion workflow. Colour pairs are fitted directly to the resized
RGB source, before palette quantisation, using an exhaustive minimum-error
search. Floyd–Steinberg dithering then uses the chosen pair within each cell;
error diffusion resets at cell boundaries. Without dithering, each cell is the
minimum weighted RGB error fit. Ties follow palette order for reproducibility.

```bash
retroimg convert photo.jpg output-mosaic.png \
    --profile teletext \
    --teletext-mode mosaic \
    --dither floyd-steinberg \
    --scale 6
```

This is currently a *visual* mosaic constraint.  Historical Teletext row
control codes, held/separated graphics and background-control behaviour are a
future layer rather than being baked into the image converter.

### Source aspect and custom canvases

Select **Match source aspect** under Output geometry in the desktop frontend,
or add `--aspect-mode source` to either Teletext mode. The complete composition
is retained on an automatically sized canvas. A 16:9 input uses 128×72 logical
pixels / 64×24 mosaic cells, retaining two colours per cell in mosaic mode.
Native dimensions remain the default; this option does not claim a standard
broadcast page. See [source matching](../conversion.md#match-the-source-aspect-teletext)
for rounding, pixel-shape and size limits.

[All targets](README.md) · [Project README](../../README.md)
