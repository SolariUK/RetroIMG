from __future__ import annotations

import argparse
from pathlib import Path

from retroimg.convert import convert_file
from retroimg.palettes import PALETTES
from retroimg.profiles import PROFILES


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert images to constrained retro display styles.")
    sub = p.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert", help="convert an image")
    convert.add_argument("input", type=Path)
    convert.add_argument("output", type=Path)
    convert.add_argument("--profile", choices=sorted(PROFILES), default="teletext")
    convert.add_argument("--palette", choices=sorted(PALETTES))
    convert.add_argument("--width", type=int)
    convert.add_argument("--height", type=int)
    convert.add_argument("--fit", choices=("cover", "contain", "stretch"), default="cover")
    convert.add_argument("--dither", choices=("none", "floyd-steinberg"), default="none")
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

    sub.add_parser("palettes", help="list available palettes")
    sub.add_parser("profiles", help="list available target profiles")
    return p


def main() -> None:
    args = build_parser().parse_args()

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
        )
        print(
            f"Wrote {args.output}: {indexed.width}x{indexed.height}, "
            f"palette={indexed.palette.name}, profile={args.profile}, dither={args.dither}, "
            f"teletext-mode={args.teletext_mode}, spectrum-mode={args.spectrum_mode}, "
            f"c64-mode={args.c64_mode}, cpc-mode={args.cpc_mode}"
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
