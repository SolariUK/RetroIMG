# Visual comparison gallery

`generate_gallery.py` runs real source images through Teletext, Spectrum, C64
and CPC conversion. It produces individual PNGs, labelled JPEG comparison
sheets, reproduction commands, JSON settings/checksums, and offline HTML and
Markdown indexes. It is a visual integration run, separate from the fast pytest
suite. It uses the installed converter and Pillow, with no additional dependencies.

## Sources and rights

`sources.json` records filenames, captions, fitting choices and rights. Place
the source files in a directory of your choice. Public-only runs require:

| Filename | Subject | Rights/source |
| --- | --- | --- |
| `macaws.jpg` | Blue-and-yellow macaws | Public-domain release by Adrian Pingstone; [source statement](https://commons.wikimedia.org/wiki/File:Macaw.blueyellow.arp.750pix.jpg) |
| `city-night.jpg` | Stockholm night architecture | CC0 dedication by Martin Eklund; [source statement](https://commons.wikimedia.org/wiki/File:City_silhouette_at_night.jpg) |
| `diagnostic-chart.png` | Mathematical gradients, swatches, fine patterns and text | Generated locally without third-party source imagery |

The default local run also uses the two user-supplied files recorded in the
catalogue. Their redistribution rights have not been established, so they are
marked local-only and excluded from public exports. Generated examples retain
the source's credit and rights information; conversion does not establish new
rights to the source image.

The generator never downloads source files or publishes anything remotely.
Original files are read without modification. Reports include source checksums
and resized source previews, rather than duplicating full-size originals.

Create the diagnostic source without downloading anything:

```bash
python examples/generate_diagnostic_chart.py \
    --output /path/to/source-images/diagnostic-chart.png
```

The output directory must already exist. The chart uses Pillow's bundled font;
font rendering may differ between Pillow versions. The source checksum recorded
by each gallery identifies the exact input used in that run.

## Reproduce the gallery

Install retroimg in the active environment, then run from the project root:

```bash
# Only the documented public examples
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-public-gallery \
    --public-only

# All local sources, plus a separate filtered public gallery
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-local-gallery \
    --public-output /path/to/new-public-gallery

# Run just one target family
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-cpc-gallery \
    --family cpc --public-only
```

Use the virtualenv's Python when appropriate. Output directories must be new,
which prevents stale local-only files from surviving in a public export. Open
`index.html` or `README.md` in the chosen output directory. No server or network
access is needed to browse the gallery. JPEG sheets are convenient overviews;
use the linked PNGs to judge exact converted pixels.

`--family` accepts `teletext`, `spectrum`, `c64`, `cpc` or `all`. The generated
commands use placeholder source paths; replace `/path/to/filename` and run the
commands from the gallery directory, or adjust the output paths.

## Comparison matrix

Each source gets the same 30 neutral conversions:

| Target family | Variants |
| --- | --- |
| Teletext | Bitmap/mosaic, each with no dither and Floyd–Steinberg; mosaic C64/Spectrum palette swaps; larger mosaic grid; saturation 1.5 example |
| Spectrum | Unrestricted bitmap/attribute constraints, each with no dither and Floyd–Steinberg |
| C64 | Unrestricted bitmap/multicolour constraints, each with no dither and Floyd–Steinberg; unrestricted Teletext/Spectrum palette swaps |
| CPC | Modes 0/1/2, unrestricted/constrained, each with no dither and Floyd–Steinberg |

The source marked `adjusted` in the catalogue also gets 12 constrained examples
with hue +20 degrees and green gain 1.15. These are labelled separately from
neutral baselines. With the current five-source catalogue, the full local run
produces 162 converted PNGs and 20 comparison sheets; the public-only run
produces 90 converted PNGs and 12 sheets.

Photos use `cover` fitting; the diagnostic chart uses `contain` so the complete
chart remains visible. Different target geometries can therefore crop photos
differently. Assess colour-constraint changes within the same target geometry.

## Automated checks

Every conversion validates indexed pixels, expected preview dimensions, and
that PNG colours belong to its selected palette. Constrained examples also check:

- Teletext: at most two colours in every 2x3 cell.
- Spectrum: at most two colours per 8x8 cell, with compatible shared brightness.
- C64: at most four colours per 4x8 cell and a legal background shared across
  the whole image. Merely checking each cell independently is insufficient.
- CPC: at most 16, 4 or 2 colours across the entire image, according to mode.

These checks establish structural validity, not visual quality or historical
hardware-file compatibility. The normal pytest suite additionally covers the
gallery matrix, constraint-failure detection and exclusion of private files and
metadata from public exports. Large source images are not pytest dependencies.
