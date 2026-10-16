# Reference images and comparison samples

`sources/` contains the seven public-domain/CC0 or locally generated reference images used by the gallery. Keeping these modest source files in Git makes comparisons reproducible from a fresh checkout, without a download service or access to a developer scratchpad. The files total approximately 6 MB.

The two earlier user-supplied sources remain outside the repository and are excluded from public galleries. Large generated galleries, experimental conversions and verification reports belong in a temporary directory. A future `comparisons/` directory can hold a curated selection of labelled comparison sheets; it is intentionally not populated with every generated output.

## Generate examples

Run from the project root with retroimg installed:

```bash
python examples/generate_gallery.py \
    --public-only \
    --output-dir /path/to/new-public-gallery
```

The source directory defaults to `samples/sources/`. Add `--family bbc` (or `teletext`, `spectrum`, `c64`, `cpc`, `amiga`) for a smaller run. `--sources-dir` still accepts an external directory for local experiments. The output directory must be new.

## Image rights

Image rights are recorded individually below and in [`examples/sources.json`](../examples/sources.json). They are separate from the software licence; including an image does not relicense it under MIT. The photographs use CC0 or an explicit worldwide public-domain release, without attribution or share-alike copyright conditions. Credits are retained for provenance and courtesy.

CC0 does not remove third-party personality, privacy or trademark rights. The portrait providers report model releases and caution against offensive or derogatory portrayals; use these as neutral conversion demonstrations without implying endorsement. See the [CC0 deed](https://creativecommons.org/publicdomain/zero/1.0/).

Checksums identify the exact bundled bytes. Sources are copied without resizing or re-encoding. The diagnostic chart is generated locally with the project script and uses Pillow’s bundled font.

| File | Reference size | Coverage | Credit / rights |
| --- | --- | --- | --- |
| [macaws.jpg](sources/macaws.jpg) | 750×536 | Saturated colours, feathers and silhouettes | Adrian Pingstone (Arpingstone), July 2004; Released into the public domain by the photographer, with an unrestricted-use fallback. |
| [city-night.jpg](sources/city-night.jpg) | 4879×3253 | Dark gradients, architectural edges and small highlights | Martin Eklund (Teadrinker), 27 October 2012; CC0 1.0 Universal Public Domain Dedication. |
| [diagnostic-chart.png](sources/diagnostic-chart.png) | 640×400 | Ramps, exact swatches, fine patterns and text | Generated locally for retroimg using Pillow; Locally generated gradients, patterns and text; no third-party source imagery. |
| [portrait-colour.jpg](sources/portrait-colour.jpg) | 1920×1593 | Primary colour portrait: skin tones, eyes, hair, hat texture, soft shadows and bright background. | Petr Kratochvil; CC0 1.0 Universal Public Domain Dedication |
| [lush-landscape.jpg](sources/lush-landscape.jpg) | 1599×896 | Primary lush landscape: grass, leafy trees, distant green hill, blue-grey sky, haze and fine wire detail. | Baap8969; CC0 1.0 Universal Public Domain Dedication |
| [green-hills.jpg](sources/green-hills.jpg) | 1000×750 | Alternative hill landscape: yellow-green versus blue-green foliage, rocks, distant mountains, sky gradient and dense vegetation. | Jon Sullivan; Worldwide public-domain release by the author, with an unrestricted-use fallback where necessary. |
| [portrait-man.jpg](sources/portrait-man.jpg) | 1920×1271 | Optional near-monochrome portrait: deep shadows, facial texture, hand detail and dither behaviour. Not a substitute for the colour portrait skin-tone case. | George Hodan; CC0 1.0 Universal Public Domain Dedication |

## Source records

### macaws.jpg

Blue-and-yellow macaws — Adrian Pingstone (Arpingstone), July 2004.

Released into the public domain by the photographer, with an unrestricted-use fallback.

[Source and rights statement](https://commons.wikimedia.org/wiki/File:Macaw.blueyellow.arp.750pix.jpg)

Reference SHA-256: `6dcaf4984208e348508570d85667307cd3cb7e143276df3e5637d04cecab8c7e`

### city-night.jpg

Stockholm at night — Martin Eklund (Teadrinker), 27 October 2012.

CC0 1.0 Universal Public Domain Dedication.

[Source and rights statement](https://commons.wikimedia.org/wiki/File:City_silhouette_at_night.jpg)

Reference SHA-256: `7cce3e17e8180acd3a2a3bf8185ef2fcf7c91a344e33069f7ecb3c5cc7af4092`

### diagnostic-chart.png

Diagnostic chart — Generated locally for retroimg using Pillow.

Locally generated gradients, patterns and text; no third-party source imagery.

Reference SHA-256: `33514e9e68750a7d9ccd9485cfbe5fc413be4d652ecd7f6b8823e3184a9b5a46`

### portrait-colour.jpg

Summer Girl Portrait — Petr Kratochvil.

CC0 1.0 Universal Public Domain Dedication

[Source and rights statement](https://www.publicdomainpictures.net/en/view-image.php?image=392516&picture=summer-girl-portrait)

Source explicitly identifies CC0 and reports obtaining a model release. It also cautions against offensive or derogatory depictions of the person. Do not imply model endorsement. Download is the free standard-resolution version, not the paid original.

Reference SHA-256: `8eb9944c64a0b2601e3ebff852dcfa48136d6309607f64267107e0161c2e7602`

### lush-landscape.jpg

Green Landscape with Hills and Trees — Baap8969.

CC0 1.0 Universal Public Domain Dedication

[Source and rights statement](https://commons.wikimedia.org/wiki/File:Green_Landscape_with_Hills_and_Trees.jpg)

Uploader identifies this photograph as own work and explicitly applies CC0. Current Commons original includes the recorded rotation correction.

Reference SHA-256: `29d3d56805edc2d3c02880975d8a29ad1c7a574e40e6a43cbc58e35a781a7fc1`

### green-hills.jpg

Green hills — Jon Sullivan.

Worldwide public-domain release by the author, with an unrestricted-use fallback where necessary.

[Source and rights statement](https://commons.wikimedia.org/wiki/File:Green_hills.jpg)

Commons records the author release and earlier public-domain-image.com provenance. Original Commons JPEG retained without re-encoding.

Reference SHA-256: `7338b0c737504593697881e31b413cb5de3d74f0d821b4ae7d473fe0509fd1f9`

### portrait-man.jpg

People — George Hodan.

CC0 1.0 Universal Public Domain Dedication

[Source and rights statement](https://www.publicdomainpictures.net/en/view-image.php?image=82849&picture=people)

[Additional rights statement](https://www.publicdomainpictures.net/en/free-download.php?id=82849&image=people)

The download page explicitly states CC0. The indexed image description reports a model release and cautions against offensive or derogatory depictions. Do not imply model endorsement. Free standard-resolution download, not the paid original.

Reference SHA-256: `ffb6b5cf7d2fedceb5d6cf498669045e0f994b38594b4cc988443e885ba6c5bd`

