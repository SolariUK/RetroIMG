"""Generate checked visual examples and a portable gallery, without new dependencies.

Run with retroimg installed (e.g. the project's virtualenv Python). This is a
visual integration run, separate from the fast pytest suite. It never downloads
sources or publishes files to a remote service.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shlex

from PIL import Image, ImageDraw, ImageFont, ImageOps

from retroimg.convert import convert_file
from retroimg.model import IndexedImage
from retroimg.targets.spectrum import spectrum_from_indexed
from retroimg.targets.teletext import page_from_indexed

FAMILIES = ("teletext", "spectrum", "c64", "cpc")
CATALOG = Path(__file__).with_name("sources.json")


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
            for mode in ("bitmap", "multicolour"):
                add(mode + suffix, f"{mode.title()} / {label}",
                    dict(profile_name="c64-multicolour", c64_mode=mode, dither=dither, scale=2), (640, 400))
        elif family == "cpc":
            for constraint in ("bitmap", "constrained"):
                for mode in range(3):
                    add(f"mode{mode}-{constraint}{suffix}", f"Mode {mode} / {constraint} / {label}",
                        dict(profile_name=f"cpc-mode{mode}", cpc_mode=constraint, dither=dither,
                             scale=1 if mode == 2 else 2), (640, 400))
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

    if adjusted:
        # Compare source adjustments separately from the neutral baseline.
        for variant in tuple(variants):
            options = variant.options
            constrained = (options.get("teletext_mode") == "mosaic" or
                           options.get("spectrum_mode") == "attributes" or
                           options.get("c64_mode") == "multicolour" or
                           options.get("cpc_mode") == "constrained")
            if constrained and not any(key in options for key in ("palette_name", "width", "saturation")):
                add(variant.slug + "-adjusted", variant.label + " / hue +20, G x1.15",
                    dict(options, hue_shift=20, green_gain=1.15), variant.size)
    return variants


def check_constraints(image: IndexedImage, options: dict) -> None:
    """Check actual output, including constraints shared across cells."""
    image.validate()
    if options.get("teletext_mode") == "mosaic":
        page_from_indexed(image)
    if options.get("spectrum_mode") == "attributes":
        spectrum_from_indexed(image)
    if options.get("cpc_mode") == "constrained":
        mode = int(options["profile_name"][-1])
        used = {index for row in image.pixels for index in row}
        if len(used) > (16, 4, 2)[mode]:
            raise AssertionError("CPC global ink limit violated")
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
             "All five local sources. User-supplied images are marked local-only; use the public gallery for publication material.")
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


def generate(sources_dir: Path, output: Path, families: tuple[str, ...], public_only: bool = False) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    sources = [source for source in catalog if not public_only or source["public"]]
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
            variants = variants_for(family, source.get("adjusted", False))
            target = directory / family
            target.mkdir()
            columns = 3 if family == "cpc" else 2
            rows = (len(variants) + columns - 1) // columns
            sheet = Image.new("RGB", (640 * columns, 486 * rows), "#202020")
            draw = ImageDraw.Draw(sheet)
            commands = [f"# {source['title']}: {family} comparisons", "", f"Fit: {source['fit']}. Neutral adjustments unless labelled.", ""]
            for index, variant in enumerate(variants):
                options = dict(variant.options, fit=source["fit"])
                dst = target / (variant.slug + ".png")
                indexed = convert_file(path, dst, **options)
                check_constraints(indexed, options)
                with Image.open(dst) as rendered:
                    if rendered.size != variant.size:
                        raise AssertionError(f"unexpected preview size: {dst}")
                    colours = rendered.convert("RGB").getcolors(maxcolors=len(indexed.palette.colours))
                    allowed = set(indexed.palette.rgb_values())
                    if colours is None or any(rgb not in allowed for _, rgb in colours):
                        raise AssertionError(f"preview contains off-palette colours: {dst}")
                    x, y = (index % columns) * 640, (index // columns) * 486
                    sheet.paste(rendered, (x + (640 - rendered.width) // 2, y + 36 + (450 - rendered.height) // 2))
                draw.text((x + 8, y + 10), variant.label, fill="white", font=font)
                relative = dst.relative_to(output).as_posix()
                command = command_for(source, relative, options)
                commands.extend([f"## {variant.label}", "", "```bash", command, "```", ""])
                manifest["outputs"].append(dict(
                    source=source["id"], family=family, label=variant.label, png=relative,
                    settings=options, preview_size=list(variant.size), logical_size=[indexed.width, indexed.height],
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
    parser.add_argument("--sources-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for generated files")
    parser.add_argument("--family", choices=("all", *FAMILIES), default="all")
    parser.add_argument("--public-only", action="store_true", help="exclude user-supplied sources without documented redistribution rights")
    parser.add_argument("--public-output", type=Path, help="also copy public examples to a separate new directory")
    args = parser.parse_args(argv)
    if args.public_output is not None and args.public_output.exists():
        parser.error("--public-output must be a new directory")
    families = FAMILIES if args.family == "all" else (args.family,)
    manifest = generate(args.sources_dir, args.output_dir, families, args.public_only)
    if args.public_output is not None:
        export_public_gallery(args.output_dir, args.public_output, manifest)
    print(f"Done: {len(manifest['outputs'])} checked PNGs; index: {args.output_dir / 'index.html'}", flush=True)


if __name__ == "__main__":
    main()
