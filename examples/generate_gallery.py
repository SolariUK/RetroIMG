"""Generate checked visual examples and a portable gallery, without new dependencies.

Run with retroimg installed (e.g. the project's virtualenv Python). This is a
visual integration run, separate from the fast pytest suite. It never downloads
sources or publishes files to a remote service.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shlex
from time import perf_counter

from PIL import Image, ImageDraw, ImageFont, ImageOps

from retroimg.convert import convert_file
from retroimg.model import IndexedImage
from retroimg.targets.spectrum import spectrum_from_indexed
from retroimg.targets.teletext import page_from_indexed

FAMILIES = ("teletext", "spectrum", "c64", "cpc", "bbc", "amiga", "atari2600", "megadrive", "snes", "nes", "mastersystem", "gameboy", "cga", "ega")
CATALOG = Path(__file__).with_name("sources.json")
BUNDLED_SOURCES = Path(__file__).resolve().parents[1] / "samples" / "sources"


@dataclass(frozen=True)
class Variant:
    slug: str
    label: str
    options: dict
    size: tuple[int, int]


def variants_for(family: str, adjusted: bool = False) -> list[Variant]:
    variants = []

    def add(slug, label, options, size):
        variants.append(Variant(slug, label, options, size))

    for dither in ("none", "floyd-steinberg"):
        suffix = "-dither" if dither != "none" else ""
        label = "Floyd-Steinberg" if suffix else "no dither"
        if family == "teletext":
            for mode in ("bitmap", "mosaic"):
                add(mode + suffix, f"{mode.title()} / {label}",
                    dict(profile_name="teletext", teletext_mode=mode, dither=dither, scale=6), (480, 450))
        elif family == "spectrum":
            for mode in ("bitmap", "attributes"):
                add(mode + suffix, f"{mode.title()} / {label}",
                    dict(profile_name="spectrum", spectrum_mode=mode, dither=dither, scale=2), (512, 384))
        elif family == "c64":
            add('hires' + suffix, f'High resolution / {label}',
                dict(profile_name='c64-hires', c64_mode='hires', dither=dither, scale=2), (640, 400))
            for mode in ("bitmap", "multicolour"):
                add(mode + suffix, f"{mode.title()} / {label}",
                    dict(profile_name="c64-multicolour", c64_mode=mode, dither=dither, scale=2), (640, 400))
        elif family == "atari2600":
            for standard, size in (("ntsc", (512, 384)), ("pal", (608, 456))):
                for mode in ("bitmap", "playfield", "repeat", "mirror"):
                    add(f"{standard}-{mode}{suffix}", f"{standard.upper()} / {mode} / {label}",
                        dict(profile_name=f"atari2600-{standard}", atari_mode=mode,
                             dither=dither, scale=2), size)
        elif family == "amiga":
            for resolution, limits in (("lores", (2, 4, 8, 16, 32)), ("hires", (2, 4, 8, 16))):
                scale = 2 if resolution == "lores" else 1
                add(f"{resolution}-bitmap{suffix}", f"{resolution} / unrestricted / {label}",
                    dict(profile_name=f"amiga-{resolution}", dither=dither, scale=scale), (640, 512))
                for count in limits:
                    add(f"{resolution}-{count}{suffix}", f"{resolution} / {count} colours / {label}",
                        dict(profile_name=f"amiga-{resolution}", amiga_mode="constrained", colours=count,
                             dither=dither, scale=scale), (640, 512))
        elif family == "bbc":
            for constraint in ("bitmap", "constrained"):
                for mode in (0, 1, 2, 4, 5):
                    add(f"mode{mode}-{constraint}{suffix}", f"Mode {mode} / {constraint} / {label}",
                        dict(profile_name=f"bbc-mode{mode}", bbc_mode=constraint, dither=dither,
                             scale=1 if mode == 0 else 2), (640, 512))
        elif family == "cpc":
            for constraint in ("bitmap", "constrained"):
                for mode in range(3):
                    add(f"mode{mode}-{constraint}{suffix}", f"Mode {mode} / {constraint} / {label}",
                        dict(profile_name=f"cpc-mode{mode}", cpc_mode=constraint, dither=dither,
                             scale=1 if mode == 2 else 2), (640, 400))
        elif family in {"megadrive", "snes"}:
            profiles = (("megadrive-320", (640, 480)), ("megadrive-256", (597, 448)),
                        ("megadrive-320-pal", (640, 480)), ("megadrive-256-pal", (640, 480))) if family == 'megadrive' else (("snes", (597, 448)),)
            modes = ('bitmap', 'tiles') if family == 'megadrive' else ('bitmap', 'tiles', 'indexed')
            for profile, size in profiles:
                for mode in modes:
                    add(f'{profile}-{mode}{suffix}', f'{profile} / {mode} / {label}',
                        dict(profile_name=profile, **{family + '_mode': mode}, dither=dither, scale=2), size)
        elif family in {'nes', 'mastersystem', 'gameboy'}:
            if family == 'nes':
                profiles = (('nes', (640, 480)),)
                modes = ('bitmap', 'attributes')
            elif family == 'mastersystem':
                profiles = (('mastersystem', (512, 384)), ('mastersystem-224', (597, 448)),
                            ('mastersystem-240', (640, 480)))
                modes = ('bitmap', 'tiles')
            else:
                profiles = (('gameboy', (640, 576)),)
                modes = ('bitmap', 'tiles')
            for profile, size in profiles:
                for mode in modes:
                    add(f'{profile}-{mode}{suffix}', f'{profile} / {mode} / {label}',
                        dict(profile_name=profile, **{family + '_mode': mode}, dither=dither,
                             scale=4 if family == 'gameboy' else 2), size)
            if family == 'gameboy':
                add(f'gameboy-tiles-grey{suffix}', f'Game Boy / grey tiles / {label}',
                    dict(profile_name='gameboy', gameboy_mode='tiles', palette_name='gameboy-grey',
                         dither=dither, scale=4), (640, 576))
        elif family == 'cga':
            add(f'bitmap{suffix}', f'320 / unrestricted RGBI / {label}',
                dict(profile_name='cga-320', cga_mode='bitmap', palette_name='cga', dither=dither, scale=2), (640, 480))
            for number in (0, 1):
                for intensity in ('low', 'high'):
                    palette = f'cga-pal{number}-{intensity}'
                    add(f'pal{number}-{intensity}{suffix}', f'320 / palette {number} {intensity} / {label}',
                        dict(profile_name='cga-320', cga_mode='constrained', palette_name=palette, dither=dither, scale=2), (640, 480))
            add(f'mono{suffix}', f'640 / monochrome / {label}',
                dict(profile_name='cga-640', cga_mode='constrained', dither=dither, scale=1), (640, 480))
        elif family == 'ega':
            for profile in ('ega-320', 'ega-640-200', 'ega-640'):
                for mode in ('bitmap', 'constrained'):
                    options = dict(profile_name=profile, ega_mode=mode, dither=dither, scale=2 if profile=='ega-320' else 1)
                    if mode == 'bitmap':
                        options['palette_name'] = 'ega'
                    add(f'{profile}-{mode}{suffix}', f'{profile} / {mode} / {label}', options, (640, 480))
            add(f'classic{suffix}', f'640x350 / fixed RGBI / {label}',
                dict(profile_name='ega-640', ega_mode='constrained', palette_name='ega-default', dither=dither, scale=1), (640, 480))
        else:
            raise ValueError(f"unknown example family: {family}")

    if family == "teletext":
        for palette in ("c64", "spectrum"):
            add(f"mosaic-{palette}", f"Mosaic / {palette} palette",
                dict(profile_name="teletext", teletext_mode="mosaic", palette_name=palette, scale=6), (480, 450))
        add("mosaic-large", "Mosaic / 160x150 logical",
            dict(profile_name="teletext", teletext_mode="mosaic", width=160, height=150, scale=3), (480, 450))
        add("mosaic-saturated", "Mosaic / saturation 1.5",
            dict(profile_name="teletext", teletext_mode="mosaic", saturation=1.5, scale=6), (480, 450))
    if family == "c64":
        for palette in ("teletext", "spectrum"):
            add(f"bitmap-{palette}", f"Unrestricted / {palette} palette",
                dict(profile_name="c64-multicolour", c64_mode="bitmap", palette_name=palette, scale=2), (640, 400))

    if family == "atari2600":
        for standard, size in (("ntsc", (512, 384)), ("pal", (608, 456))):
            add(f"{standard}-chunky", f"{standard.upper()} / playfield / 8-line blocks / dither",
                dict(profile_name=f"atari2600-{standard}", atari_mode="playfield", atari_row_height=8,
                     dither="floyd-steinberg", scale=2), size)
            add(f"{standard}-bitmap-c64", f"{standard.upper()} / unrestricted C64 palette",
                dict(profile_name=f"atari2600-{standard}", palette_name="c64", scale=2), size)

    if family == "amiga":
        for mode in ("ehb", "ham"):
            for suffix, size in (("", (640, 512)), ("-ntsc", (640, 400))):
                for dither in ("none", "floyd-steinberg"):
                    ending = "-dither" if dither != "none" else ""
                    label = "Floyd-Steinberg" if ending else "no dither"
                    add(f"{mode}{suffix}{ending}", f"{mode.upper()} / {'NTSC' if suffix else 'PAL'} / {label}",
                        dict(profile_name=f"amiga-lores{suffix}", amiga_mode=mode, dither=dither, scale=2), size)
        for palette in ("c64", "cpc"):
            add(f"lores-bitmap-{palette}", f"lores unrestricted / {palette} palette",
                dict(profile_name="amiga-lores", palette_name=palette, scale=2), (640, 512))
        for resolution in ("lores", "hires"):
            add(f"{resolution}-ntsc-dither", f"{resolution} / NTSC / constrained / Floyd-Steinberg",
                dict(profile_name=f"amiga-{resolution}-ntsc", amiga_mode="constrained", dither="floyd-steinberg",
                     scale=2 if resolution == "lores" else 1), (640, 400))

    if family == "bbc":
        for palette in ("cpc", "spectrum"):
            add(f"mode1-bitmap-{palette}", f"Mode 1 unrestricted / {palette} palette",
                dict(profile_name="bbc-mode1", palette_name=palette, scale=2), (640, 512))

    if adjusted:
        # Compare source adjustments separately from the neutral baseline.
        for variant in tuple(variants):
            options = variant.options
            constrained = (options.get("teletext_mode") == "mosaic" or
                           options.get("spectrum_mode") == "attributes" or
                           options.get("c64_mode") in {"hires", "multicolour"} or
                           options.get("cpc_mode") == "constrained" or
                           options.get("bbc_mode") == "constrained" or
                           options.get("amiga_mode") in {"constrained", "ehb", "ham"} or
                           options.get("atari_mode") in {"playfield", "repeat", "mirror"} or
                           options.get("megadrive_mode") == 'tiles' or
                           options.get("snes_mode") in {'tiles', 'indexed'} or
                           options.get("nes_mode") == 'attributes' or
                           options.get("mastersystem_mode") == 'tiles' or
                           options.get("gameboy_mode") == 'tiles' or
                           options.get("cga_mode") == 'constrained' or
                           options.get("ega_mode") == 'constrained')
            if constrained and not any(key in options for key in ("palette_name", "width", "saturation")):
                add(variant.slug + "-adjusted", variant.label + " / hue +20, G x1.15",
                    dict(options, hue_shift=20, green_gain=1.15), variant.size)
    return variants


# Representative modes for a compact cross-machine dithering comparison.
DITHER_EXAMPLES = {
    "teletext": ("mosaic",), "spectrum": ("attributes",),
    "c64": ("multicolour",), "cpc": ("mode1-constrained",),
    "bbc": ("mode0-constrained",), "amiga": ("lores-32", "ehb", "ham"),
    "atari2600": ("ntsc-playfield",),
    "megadrive": ("megadrive-320-tiles",), "snes": ("snes-tiles", "snes-indexed"),
    "nes": ("nes-attributes",), "mastersystem": ("mastersystem-tiles",),
    "gameboy": ("gameboy-tiles", "gameboy-tiles-grey"),
    "cga": ('pal0-low', 'pal0-high', 'pal1-low', 'pal1-high', 'mono'),
    "ega": ('ega-320-constrained', 'ega-640-constrained', 'classic'),
}


def dither_variants_for(family: str) -> list[Variant]:
    """Hold source settings/palette limits fixed and compare five dithers."""
    baselines = {variant.slug: variant for variant in variants_for(family)}
    result = []
    for slug in DITHER_EXAMPLES[family]:
        base = baselines[slug]
        label = base.label.removesuffix(" / no dither")
        for dither, size, suffix, title in (
            ("none", None, "none", "No dither"),
            ("floyd-steinberg", None, "fs", "Floyd-Steinberg"),
            *[("bayer", size, f"bayer{size}", f"Bayer {size}x{size}") for size in (2, 4, 8)],
        ):
            options = dict(base.options, dither=dither)
            if size is not None:
                options["bayer_size"] = size
            result.append(Variant(f"{slug}-{suffix}", f"{label} / {title}", options, base.size))
    return result


def check_constraints(image: IndexedImage, options: dict) -> None:
    """Check actual output, including constraints shared across cells."""
    image.validate()
    if options.get('cga_mode') == 'constrained':
        from retroimg.palettes.cga import CGA_PALETTES, CGA_MONO
        profile = options['profile_name']
        allowed = CGA_MONO if profile == 'cga-640' else CGA_PALETTES[options.get('palette_name', 'cga-pal1-high')]
        if image.palette != allowed:
            raise AssertionError('CGA fixed palette constraint violated')
    if options.get('ega_mode') == 'constrained':
        from retroimg.palettes.ega import EGA_RGB, EGA_DEFAULT
        values = image.palette.rgb_values()
        if len(values)>16 or any(EGA_RGB.snap(rgb)!=rgb for rgb in values):
            raise AssertionError('EGA colour limit/precision violated')
        if options['profile_name'] != 'ega-640' and not set(values)<=set(EGA_DEFAULT.rgb_values()):
            raise AssertionError('EGA 200-line RGBI constraint violated')
    if options.get('nes_mode') == 'attributes':
        from retroimg.palettes.nes import NES
        values = image.palette.rgb_values()
        if len(values) != 16 or len(set(values[::4])) != 1 or not set(values) <= set(NES.rgb_values()):
            raise AssertionError('NES palette banks/shared backdrop violated')
        for y in range(0, image.height, 16):
            for x in range(0, image.width, 16):
                if len({image.pixels[dy][dx] // 4 for dy in range(y, y + 16) for dx in range(x, x + 16)}) != 1:
                    raise AssertionError('NES 16x16 attribute constraint violated')
    if options.get('mastersystem_mode') == 'tiles':
        from retroimg.palettes.mastersystem import MASTERSYSTEM_RGB
        if len(image.palette.colours) != 32 or any(MASTERSYSTEM_RGB.snap(rgb) != rgb for rgb in image.palette.rgb_values()):
            raise AssertionError('Master System colour precision/bank limit violated')
        for y in range(0, image.height, 8):
            for x in range(0, image.width, 8):
                if len({image.pixels[dy][dx] // 16 for dy in range(y, y + 8) for dx in range(x, x + 8)}) != 1:
                    raise AssertionError('Master System 8x8 bank constraint violated')
    if options.get('gameboy_mode') == 'tiles':
        from retroimg.palettes.gameboy import GAMEBOY, GAMEBOY_GREY
        if image.palette not in (GAMEBOY, GAMEBOY_GREY):
            raise AssertionError('Game Boy four-shade palette violated')
    for family, count in (('megadrive', 4), ('snes', 8)):
        if options.get(family + '_mode') == 'tiles':
            from retroimg.palettes.megadrive import MEGADRIVE_RGB
            from retroimg.palettes.snes import SNES_RGB
            grid = MEGADRIVE_RGB if family == 'megadrive' else SNES_RGB
            values = image.palette.rgb_values()
            if len(values) != count * 16 or any(grid.snap(rgb) != rgb for rgb in values):
                raise AssertionError('Console bank capacity/colour precision violated')
            if len(set(values[::16])) != 1:
                raise AssertionError('Console shared backdrop violated')
            for y in range(0, image.height, 8):
                for x in range(0, image.width, 8):
                    banks = {image.pixels[dy][dx] // 16 for dy in range(y, y + 8) for dx in range(x, x + 8)}
                    if len(banks) != 1:
                        raise AssertionError('Console tile uses multiple banks')
    if options.get('snes_mode') == 'indexed':
        from retroimg.palettes.snes import SNES_RGB
        if len(image.palette.colours) > 256 or any(SNES_RGB.snap(rgb) != rgb for rgb in image.palette.rgb_values()):
            raise AssertionError('SNES 8bpp palette limit/precision violated')
    if options.get("atari_mode") in {"playfield", "repeat", "mirror"}:
        height = options.get("atari_row_height", 2)
        if image.width != 160 or image.palette.name not in {"atari2600-ntsc", "atari2600-pal"}:
            raise AssertionError("Atari playfield width/palette violated")
        for y in range(0, image.height, height):
            band = image.pixels[y:y + height]
            row = band[0]
            if any(other != row for other in band) or len(set(row)) > 2:
                raise AssertionError("Atari band pattern/colour constraint violated")
            if any(len(set(row[x:x + 4])) > 1 for x in range(0, 160, 4)):
                raise AssertionError("Atari four-clock blocks violated")
            mode = options["atari_mode"]
            if mode == "repeat" and row[:80] != row[80:]:
                raise AssertionError("Atari repeated halves violated")
            if mode == "mirror" and row[:80] != row[80:][::-1]:
                raise AssertionError("Atari mirrored halves violated")
    if options.get("teletext_mode") == "mosaic":
        page_from_indexed(image)
    if options.get("spectrum_mode") == "attributes":
        spectrum_from_indexed(image)
    if options.get("amiga_mode") in {"ehb", "ham"}:
        if any(channel % 17 for rgb in image.palette.rgb_values() for channel in rgb):
            raise AssertionError("Amiga 4-bit channel precision violated")
        if options["amiga_mode"] == "ehb":
            values = image.palette.rgb_values()
            if len(values) != 64 or any(values[i + 32] != tuple((v // 17 >> 1) * 17 for v in values[i]) for i in range(32)):
                raise AssertionError("Amiga EHB linked half-bright palette violated")
    if options.get("amiga_mode") == "constrained":
        limit = options.get("colours", 16 if "hires" in options["profile_name"] else 32)
        used = {index for row in image.pixels for index in row}
        if len(image.palette.colours) > limit or len(used) > limit:
            raise AssertionError("Amiga screen colour limit violated")
        if any(channel % 17 for rgb in image.palette.rgb_values() for channel in rgb):
            raise AssertionError("Amiga 4-bit channel precision violated")
    if options.get("bbc_mode") == "constrained":
        mode = int(options["profile_name"][-1])
        used = {index for row in image.pixels for index in row}
        if len(used) > {0: 2, 1: 4, 2: 8, 4: 2, 5: 4}[mode]:
            raise AssertionError("BBC global colour limit violated")
    if options.get("cpc_mode") == "constrained":
        mode = int(options["profile_name"][-1])
        used = {index for row in image.pixels for index in row}
        if len(used) > (16, 4, 2)[mode]:
            raise AssertionError("CPC global ink limit violated")
    if options.get('c64_mode') == 'hires':
        for y in range(0, image.height, 8):
            for x in range(0, image.width, 8):
                used = {image.pixels[y + dy][x + dx] for dy in range(8) for dx in range(8)}
                if len(used) > 2:
                    raise AssertionError('C64 hires cell colour limit violated')
    if options.get("c64_mode") == "multicolour":
        possible_backgrounds = set(range(len(image.palette.colours)))
        for y in range(0, image.height, 8):
            for x in range(0, image.width, 4):
                used = {image.pixels[y + dy][x + dx] for dy in range(8) for dx in range(4)}
                if len(used) > 4:
                    raise AssertionError("C64 cell colour limit violated")
                if len(used) == 4:
                    possible_backgrounds.intersection_update(used)
        if not possible_backgrounds:
            raise AssertionError("C64 cells have no legal image-wide background")


def command_for(source: dict, relative_output: str, options: dict) -> str:
    command = ["retroimg", "convert", f"/path/to/{source['file']}", relative_output]
    for key, value in options.items():
        flag = {"profile_name": "profile", "palette_name": "palette"}.get(key, key.replace("_", "-"))
        command.extend(("--" + flag, str(value)))
    return shlex.join(command)


def write_indexes(output: Path, manifest: dict) -> None:
    """Build both a Markdown index and an offline HTML contact-sheet browser."""
    public_only = manifest["public_only"]
    heading = "retroimg public examples" if public_only else "retroimg local comparisons"
    intro = ("Documented public-domain/CC0 photographs and a locally generated chart." if public_only else
             f"{len(manifest['sources'])} local sources. User-supplied images are marked local-only; use the public gallery for publication material.")
    md = [f"# {heading}", "", intro, "",
          "Neutral colour adjustments unless labelled. Photos use cover fit; the diagnostic chart uses contain fit.",
          "Comparison sheets are JPEG overviews; individual output PNGs preserve exact pixels.", ""]
    sections = []
    credits = ["# Source credits", ""]
    for source in manifest["sources"]:
        identifier = source["id"]
        status = "Public example" if source["public"] else "Local-only example"
        title = source["title"]
        md.extend([f"## {title}", "", f"{status}. {source['credit']}. {source['rights']}", "",
                   f"[Source preview]({identifier}/source-preview.png)", ""])
        credits.extend([f"## {title}", "", source["credit"], "", source["rights"], "",
                        f"Source SHA-256: `{source['sha256']}`", ""])
        if source.get("rights_url"):
            credits.extend([f"[Rights terms]({source['rights_url']})", ""])
        if source.get("notes"):
            credits.extend([source["notes"], ""])
        if source.get("rights_evidence"):
            credits.extend([f"[Additional rights statement]({source['rights_evidence']})", ""])
        link = ""
        if source.get("source"):
            md.extend([f"[Source and rights statement]({source['source']})", ""])
            credits.extend([f"[Source and rights statement]({source['source']})", ""])
            link = f'<a href="{escape(source["source"], quote=True)}">Source and rights statement</a>'
        parts = [f'<section><h2>{escape(title)}</h2><p><strong>{status}</strong> — {escape(source["credit"])}</p>',
                 f'<p>{escape(source["rights"])} {link}</p>',
                 f'<a href="{identifier}/source-preview.png"><img class="source" src="{identifier}/source-preview.png" alt="Source preview"></a>']
        for family in manifest["families"]:
            prefix = f"{identifier}/{family}"
            entries = [entry for entry in manifest["outputs"] if entry["source"] == identifier and entry["family"] == family]
            md.extend([f"### {family.title()}", "", f"[Comparison sheet]({prefix}/comparison.jpg) · [Commands]({prefix}/commands.md)", ""])
            parts.extend([f'<details><summary>{family.title()} — {len(entries)} conversions</summary>',
                          f'<a href="{prefix}/comparison.jpg"><img class="sheet" src="{prefix}/comparison.jpg" alt="{family} comparison sheet" loading="lazy"></a>',
                          f'<p><a href="{prefix}/commands.md">Reproduction commands</a></p><ul>'])
            for entry in entries:
                md.append(f'- [{entry["label"]}]({entry["png"]})')
                parts.append(f'<li><a href="{entry["png"]}">{escape(entry["label"])}</a> — {entry["colours_used"]} colours</li>')
            md.append("")
            parts.append('</ul></details>')
        parts.append('</section>')
        sections.append("\n".join(parts))
    css = """body{font-family:system-ui,sans-serif;background:#17191c;color:#eee;max-width:1200px;margin:auto;padding:24px;line-height:1.5}
    a{color:#8cc9ff}section{margin:32px 0;padding:20px;background:#24272d;border-radius:8px}
    img{max-width:100%;height:auto}.source{max-height:300px}details{margin-top:16px}summary{cursor:pointer;font-size:1.2em}
    .sheet{margin-top:16px}li{margin:6px 0}"""
    html = (f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{heading}</title><style>{css}</style><body><h1>{heading}</h1><p>{intro}</p>'
            '<p>Photos: cover fit. Diagnostic chart: contain fit. Neutral adjustments unless labelled. '
            'JPEG sheets are overviews; linked PNGs retain exact pixels.</p><p><a href="CREDITS.md">Credits</a> · '
            '<a href="manifest.json">Settings, checksums and colour counts</a></p>' + "\n".join(sections) + '</body></html>')
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (output / "CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def export_public_gallery(local: Path, output: Path, manifest: dict) -> None:
    """Copy only documented public examples, including all associated metadata.

    Require a fresh directory so older private files cannot survive an export.
    """
    import shutil

    if output.exists():
        raise ValueError("public export requires a new output directory")
    selected = [source for source in manifest["sources"] if source["public"]]
    identifiers = {source["id"] for source in selected}
    public = dict(manifest, public_only=True, sources=selected,
                  outputs=[entry for entry in manifest["outputs"] if entry["source"] in identifiers])
    output.mkdir(parents=True)
    for source in selected:
        identifier = source["id"]
        (output / identifier).mkdir()
        shutil.copy2(local / identifier / "source-preview.png", output / identifier / "source-preview.png")
        for family in manifest["families"]:
            shutil.copytree(local / identifier / family, output / identifier / family)
    write_indexes(output, public)


def generate(sources_dir: Path, output: Path, families: tuple[str, ...], public_only: bool = False, *,
             dither_comparison: bool = False, source_ids: Sequence[str] | None = None) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    sources = [source for source in catalog if not public_only or source["public"]]
    if source_ids is not None:
        unknown = set(source_ids) - {source["id"] for source in sources}
        if unknown:
            raise ValueError("unknown or excluded source IDs: " + ", ".join(sorted(unknown)))
        sources = [source for source in sources if source["id"] in source_ids]
    missing = [source["file"] for source in sources if not (sources_dir / source["file"]).is_file()]
    if missing:
        raise ValueError("missing source images: " + ", ".join(missing))
    # Requiring fresh output also keeps public-only runs from retaining old
    # local-only images and makes the manifest describe every generated file.
    if output.exists():
        raise ValueError("gallery requires a new output directory")
    output.mkdir(parents=True)
    font = ImageFont.load_default()
    manifest = dict(version=1, public_only=public_only, families=list(families), sources=[], outputs=[])
    for record in sources:
        source = dict(record)
        path = sources_dir / source["file"]
        source["sha256"] = sha256(path.read_bytes()).hexdigest()
        directory = output / source["id"]
        directory.mkdir()
        with Image.open(path) as original:
            original.verify()
        with Image.open(path) as original:
            preview = ImageOps.contain(original.convert("RGB"), (640, 450))
            preview.save(directory / "source-preview.png")
        manifest["sources"].append(source)
        for family in families:
            variants = (dither_variants_for(family) if dither_comparison
                        else variants_for(family, source.get("adjusted", False)))
            target = directory / family
            target.mkdir()
            columns = 5 if dither_comparison or family == "bbc" else (3 if family in {"cpc", "amiga", "atari2600"} else 2)
            tile_height = max(450, max(variant.size[1] for variant in variants))
            rows = (len(variants) + columns - 1) // columns
            sheet = Image.new("RGB", (640 * columns, (tile_height + 36) * rows), "#202020")
            draw = ImageDraw.Draw(sheet)
            commands = [f"# {source['title']}: {family} comparisons", "", f"Fit: {source['fit']}. Neutral adjustments unless labelled.", ""]
            for index, variant in enumerate(variants):
                options = dict(variant.options, fit=source["fit"])
                dst = target / (variant.slug + ".png")
                started = perf_counter()
                indexed = convert_file(path, dst, **options)
                elapsed = perf_counter() - started
                check_constraints(indexed, options)
                with Image.open(dst) as rendered:
                    if rendered.size != variant.size:
                        raise AssertionError(f"unexpected preview size: {dst}")
                    colours = rendered.convert("RGB").getcolors(maxcolors=len(indexed.palette.colours))
                    allowed = set(indexed.palette.rgb_values())
                    if colours is None or any(rgb not in allowed for _, rgb in colours):
                        raise AssertionError(f"preview contains off-palette colours: {dst}")
                    x, y = (index % columns) * 640, (index // columns) * (tile_height + 36)
                    sheet.paste(rendered, (x + (640 - rendered.width) // 2, y + 36 + (tile_height - rendered.height) // 2))
                draw.text((x + 8, y + 10), variant.label, fill="white", font=font)
                relative = dst.relative_to(output).as_posix()
                command = command_for(source, relative, options)
                commands.extend([f"## {variant.label}", "", "```bash", command, "```", ""])
                manifest["outputs"].append(dict(
                    source=source["id"], family=family, label=variant.label, png=relative,
                    settings=options, elapsed_seconds=round(elapsed, 6), preview_size=list(variant.size), logical_size=[indexed.width, indexed.height],
                    palette=indexed.palette.name, colours_used=len(colours),
                    sha256=sha256(dst.read_bytes()).hexdigest(), command=command,
                ))
            sheet.save(target / "comparison.jpg", quality=95)
            (target / "commands.md").write_text("\n".join(commands), encoding="utf-8")
            print(f"{source['id']} / {family}: {len(variants)} conversions checked", flush=True)
    write_indexes(output, manifest)
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-dir", type=Path, default=BUNDLED_SOURCES,
                        help="source directory (default: bundled samples/sources; use --public-only with bundled files)")
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for generated files")
    parser.add_argument("--family", choices=("all", *FAMILIES), default="all")
    parser.add_argument("--public-only", action="store_true", help="exclude user-supplied sources without documented redistribution rights")
    parser.add_argument("--dither-comparison", action="store_true",
                        help="compare no dither, Floyd–Steinberg and Bayer 2/4/8 on representative modes")
    parser.add_argument("--source", action="append", dest="source_ids",
                        help="select a source ID from sources.json (repeatable; default: all eligible sources)")
    parser.add_argument("--public-output", type=Path, help="also copy public examples to a separate new directory")
    args = parser.parse_args(argv)
    if args.public_output is not None and args.public_output.exists():
        parser.error("--public-output must be a new directory")
    families = FAMILIES if args.family == "all" else (args.family,)
    manifest = generate(args.sources_dir, args.output_dir, families, args.public_only,
                        dither_comparison=args.dither_comparison, source_ids=args.source_ids)
    if args.public_output is not None:
        export_public_gallery(args.output_dir, args.public_output, manifest)
    print(f"Done: {len(manifest['outputs'])} checked PNGs; index: {args.output_dir / 'index.html'}", flush=True)


if __name__ == "__main__":
    main()
