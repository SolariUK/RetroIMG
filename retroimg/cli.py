from __future__ import annotations

import argparse
import sys
from pathlib import Path

from retroimg import __version__
from retroimg.convert import convert_file
from retroimg.ordered import BAYER_SIZES, DITHER_MODES
from retroimg.palettes import PALETTES
from retroimg.profiles import PROFILES


def build_parser(*, conversion_defaults: dict | None = None) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert images to constrained retro display styles.")
    p.add_argument("--version", action="version", version=f"retroimg {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="convert an image")
    convert.add_argument("input", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--profile", choices=sorted(PROFILES), default="teletext")
    convert.add_argument("--palette", choices=sorted(PALETTES))
    convert.add_argument("--width", type=int)
    convert.add_argument("--height", type=int)
    convert.add_argument("--fit", choices=("cover", "contain", "stretch"), default="cover")
    convert.add_argument("--dither", choices=DITHER_MODES, default="none")
    convert.add_argument("--bayer-size", type=int, choices=BAYER_SIZES,
                         help="Bayer matrix size (default: 4; requires --dither bayer)")
    for name in ("brightness", "contrast"):
        convert.add_argument(f"--{name}", type=float, default=1.0,
                             help=f"finite non-negative {name} multiplier (default: 1)")
    convert.add_argument("--saturation", type=float, default=1.0)
    convert.add_argument("--hue-shift", type=float, default=0.0,
                         help="hue rotation in degrees; +120 maps red to green (default: 0)")
    for channel in ("red", "green", "blue"):
        convert.add_argument(f"--{channel}-gain", type=float, default=1.0,
                             help=f"non-negative {channel} multiplier (default: 1)")
    convert.add_argument("--scale", type=int, default=8, help="integer preview enlargement")
    convert.add_argument(
        "--teletext-mode",
        choices=("bitmap", "mosaic"),
        default="bitmap",
        help="Teletext rendering constraint: bitmap preserves the raw 80x75 style; mosaic limits each 2x3 cell to two colours",
    )

    convert.add_argument(
        "--spectrum-mode",
        choices=("bitmap", "attributes"),
        default="bitmap",
        help="Spectrum constraint: bitmap uses unrestricted palette colours; attributes fits shared-brightness ink/paper in 8x8 cells",
    )
    convert.add_argument(
        "--c64-mode",
        choices=("bitmap", "multicolour"),
        default="bitmap",
        help="C64 constraint: bitmap uses unrestricted palette colours; multicolour fits one shared background plus three local colours per 4x8 cell (requires c64-multicolour profile)",
    )
    convert.add_argument(
        "--cpc-mode",
        choices=("bitmap", "constrained"),
        default="bitmap",
        help="CPC constraint: bitmap allows unrestricted palette colours; constrained selects 16/4/2 global inks for cpc-mode0/1/2",
    )

    convert.add_argument(
        "--bbc-mode", choices=("bitmap", "constrained"), default="bitmap",
        help="BBC constraint: bitmap allows unrestricted palette colours; constrained selects 2/4/8/2/4 steady colours for bbc-mode0/1/2/4/5",
    )

    convert.add_argument(
        "--amiga-mode", choices=("bitmap", "constrained", "ehb", "ham"), default="bitmap",
        help="Amiga constraint: bitmap is unrestricted; constrained selects a screen palette; ehb and ham use six-bit low-resolution graphics codes",
    )
    convert.add_argument(
        "--atari-mode", choices=("bitmap", "playfield", "repeat", "mirror"), default="bitmap",
        help="Atari constraint: unrestricted bitmap, independent 40-block playfield, or repeated/mirrored 20-block halves",
    )
    convert.add_argument(
        "--megadrive-mode", choices=("bitmap", "tiles"), default="bitmap",
        help="Mega Drive: unrestricted 9-bit bitmap or 8x8 tiles selecting four shared palette banks",
    )
    convert.add_argument(
        "--snes-mode", choices=("bitmap", "tiles", "indexed"), default="bitmap",
        help="SNES: unrestricted 15-bit bitmap, 4bpp palette-bank tiles, or a 256-colour 8bpp background",
    )
    convert.add_argument(
        "--atari-row-height", type=int,
        help="scanlines sharing one playfield pattern and colour pair (default: 2; requires an Atari playfield mode)",
    )
    convert.add_argument(
        "--colours", type=int,
        help="selected screen-colour limit for Amiga constrained mode: 2/4/8/16/32 (hires maximum 16; default is the profile maximum)",
    )

    convert.add_argument("--preset", help="built-in/user preset ID or JSON file; explicit conversion flags override it")
    convert.add_argument("--presets-dir", type=Path, help="user preset directory (default: platform config directory)")
    if conversion_defaults is not None:
        convert.set_defaults(**conversion_defaults)

    guided = sub.add_parser("guided", help="build a conversion command interactively")
    guided.add_argument("input", type=Path, nargs="?", help="input image (prompted when omitted)")
    guided.add_argument("output", type=Path, nargs="?", help="output image (prompted when omitted)")
    guided.add_argument("--print-only", action="store_true", help="show the command without converting")

    guided.add_argument("--preset", help="start from a preset ID or JSON file")
    guided.add_argument("--presets-dir", type=Path, help="directory for user presets")
    presets = sub.add_parser("presets", help="list built-in and user presets")
    presets.add_argument("--presets-dir", type=Path, help="directory for user presets")

    sub.add_parser("palettes", help="list available palettes")
    sub.add_parser("profiles", help="list available target profiles")
    return p


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "presets":
        from retroimg.presets import list_presets
        entries, errors = list_presets(parser, args.presets_dir)
        for entry in entries:
            print(f"{entry.identifier}: {entry.name} - {entry.description}")
        for error in errors:
            print(error, file=sys.stderr)
        return
    if args.command == "convert" and args.preset:
        from retroimg.presets import load_preset
        from retroimg.settings import default_settings, merge_settings
        try:
            preset = load_preset(args.preset, parser, args.presets_dir)
            defaults = default_settings(parser)
            marker = object()
            explicit = vars(build_parser(conversion_defaults={key: marker for key in defaults}).parse_args(argv))
            overrides = {key: explicit[key] for key in defaults if explicit[key] is not marker}
            for key, value in merge_settings(preset.settings, overrides, defaults).items():
                setattr(args, key, value)
        except ValueError as exc:
            parser.error(str(exc))
    if args.command == "guided":
        from retroimg.guided import run_guided
        try:
            arguments = run_guided(args.input, args.output, parser=parser, print_only=args.print_only,
                                   preset_reference=args.preset, presets_dir=args.presets_dir)
        except ValueError as exc:
            parser.error(str(exc))
        if arguments is not None:
            try:
                main(arguments)
            except (OSError, ValueError) as exc:
                parser.exit(1, f"Conversion failed: {exc}\n")
        return

    if args.command == "convert":
        indexed = convert_file(
            args.input,
            args.output,
            profile_name=args.profile,
            palette_name=args.palette,
            width=args.width,
            height=args.height,
            fit=args.fit,
            dither=args.dither,
            bayer_size=args.bayer_size,
            brightness=args.brightness,
            contrast=args.contrast,
            saturation=args.saturation,
            hue_shift=args.hue_shift,
            red_gain=args.red_gain,
            green_gain=args.green_gain,
            blue_gain=args.blue_gain,
            scale=args.scale,
            teletext_mode=args.teletext_mode,
            spectrum_mode=args.spectrum_mode,
            c64_mode=args.c64_mode,
            cpc_mode=args.cpc_mode,
            bbc_mode=args.bbc_mode,
            amiga_mode=args.amiga_mode,
            atari_mode=args.atari_mode,
            megadrive_mode=args.megadrive_mode,
            snes_mode=args.snes_mode,
            atari_row_height=args.atari_row_height,
            colours=args.colours,
        )
        print(
            f"Wrote {args.output}: {indexed.width}x{indexed.height}, "
            f"palette={indexed.palette.name}, profile={args.profile}, dither={args.dither}, "
            f"teletext-mode={args.teletext_mode}, spectrum-mode={args.spectrum_mode}, "
            f"c64-mode={args.c64_mode}, cpc-mode={args.cpc_mode}, bbc-mode={args.bbc_mode}, "
            f"amiga-mode={args.amiga_mode}, atari-mode={args.atari_mode}, "
            f"megadrive-mode={args.megadrive_mode}, snes-mode={args.snes_mode}, palette-size={len(indexed.palette.colours)}"
        )
    elif args.command == "palettes":
        for name, palette in sorted(PALETTES.items()):
            print(f"{name:12} {len(palette.colours):2} colours  {palette.description}")
    elif args.command == "profiles":
        for name, profile in sorted(PROFILES.items()):
            g = profile.geometry
            print(f"{name:12} {g.width}x{g.height}  palette={profile.default_palette}  {profile.description}")
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
