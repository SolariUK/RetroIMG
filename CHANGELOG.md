# Changelog

## 0.2.1 — Unreleased

- Accelerated Teletext mosaics with large RGB-grid palettes using exact small-cell
  partition fitting, avoiding millions of palette pairs per cell while preserving
  conversion error, palette tie order and all dithering modes.
- Preserved application ZIPs during draft-release assembly and improved missing
  download diagnostics.

## 0.2.0 — Desktop preview

- Added version-tagged native builds and draft GitHub releases with validated
  Windows/Linux desktop and Windows CLI ZIPs, shared checksums and release notes.
  Actions application ZIPs now download directly, requiring one extraction.
- Installed Qt's Linux EGL/OpenGL runtime dependencies in GUI CI jobs, including
  offscreen package checks, and exposed GUI subprocess errors in package logs.
- Added independent Source/Display reset buttons and pointer-centred mouse-wheel
  zoom in both desktop previews, with a live percentage and retained fit choices.
- Made the first hardware-constrained mode the desktop default for new profile
  selections, preserving explicit preset modes. Added C64 hires constraints with
  two independent colours per 8x8 cell, retained selectors, CLI/preset integration
  and gallery recipes, alongside existing unrestricted and multicolour modes.
- Accelerated SNES palette-bank fitting and indexed modes with exact batched
  integer error searches, reusable palette-refinement work and spatial nearest
  searches for diffusion. Improved exact C64 cell searches and Bayer pruning;
  reference conversion pixels and palette tie order are preserved.
- Added an optional Windows/Linux Qt Widgets frontend with context-sensitive
  settings for all profiles/modes, original/result previews, HiDPI-aware integer
  zoom, shared presets, pixelation and full-size PNG/JPEG export. Rendering runs
  in a cancellable child process and reuses indexed conversions for display-only
  changes. Includes native desktop build and extracted-bundle checks.
- Kept desktop previews stationary during progress/status changes and sorted
  machine choices by their displayed names. Accelerated exact Atari palette and
  playfield searches and shared tile-palette fitting/Bayer lookups, preserving
  conversion pixels and palette tie order.
- Standardised desktop/guided mode labels as Palette only and Hardware constrained,
  with separate descriptions and distinct specialised variants. Existing CLI and
  preset identifiers remain compatible. Accelerated EGA and other 16-colour
  conversions, including exact floating-point diffusion searches.
- Made desktop enlargement automatic by default using the guided frontend's
  conservative size rule, accounting for profile geometry, pixel aspect, custom
  dimensions and display-treatment minimums. Manual enlargement and loaded
  preset scales are preserved; the intended output dimensions are shown.
- Added independent RF-style horizontal colour bleed and trailing smear before
  optical display effects, with separate luma/chroma filtering, CLI/guided/preset
  controls and NES examples combining RF with chromatic aberration, CRT and bloom.
- Added independent radial chromatic aberration before display surface effects,
  with linear-light fractional sampling, CLI/guided/preset controls, and night
  examples combining colour separation with CRT aperture grille and bloom.
- Added independent highlight bloom, combining with LCD, scanlines or CRT grille
  in an ordered display pipeline before final display brightness. Includes
  strength/radius controls, guided/preset support and full-size comparison crops.
- Added generic original-colour pixelation with a pixel block-size control,
  standalone CLI command, guided workflow and full-size examples. Fixed blocks
  preserve image dimensions and clip partial edge blocks without stretching.
- Added separate display brightness after rendering effects, with a neutral
  default, CLI/guided/preset controls and a compensated CRT example. Source
  brightness remains a pre-conversion adjustment; indexed data is unaffected.
- Added optional CRT aperture-grille rendering combined with scanlines, using
  the existing strength control and subtle default. Includes CLI/guided/preset
  support, full-size Mega Drive examples, scanlines-only comparison and crops.
- Improved arbitrary-palette Bayer mixing with a local-spacing contrast penalty
  and realizable matrix coverage, reducing isolated dark/bright speckles while
  preserving adjacent shade ramps, two-colour coverage and palette constraints.
  No-dither and Floyd–Steinberg output are unchanged; comparison assets refreshed.
- Added optional smooth scanlines aligned to logical rows, with linear-light
  dimming, adjustable strength, CLI/guided/preset support and separate Mega Drive
  macaws examples. Conversion codes and output dimensions remain unchanged.
- Added an optional Game Boy LCD display treatment with inset cells and shadows,
  adjustable strength, CLI/guided/preset support, and separate full-size examples
  and detail crops. Available with every profile; indexed conversion is unchanged.
- Added CGA standard four-colour/monochrome graphics and EGA RGBI/selected RGB6
  screens, guided palette choices, register models and comparison panels.
- Added NES background attributes, Master System Mode 4 tile palettes and
  original Game Boy four-shade backgrounds, with green/grey previews, retained
  register/index models, guided options, presets and comparison panels.
- Organised palettes consistently into machine-family modules, with a separate
  registry and compatibility imports; palette values and ordering are unchanged.
- Added Mega Drive/Genesis and SNES profiles, shared tile-palette bank fitting,
  opaque constrained previews and retained hardware register/index data.
  SNES also offers a selected 256-colour background; both join guided mode,
  presets, all dithers and the expanded ten-panel sample set.
- Added constrained modes for Teletext mosaics, ZX Spectrum attributes, C64
  multicolour, Amstrad CPC, BBC Micro, Amiga indexed/EHB/HAM6 and Atari 2600
  playfields. Unrestricted bitmap conversion remains available.
- Added palette-aware Bayer dithering alongside none and Floyd–Steinberg.
- Added brightness, contrast, saturation, hue rotation and individual RGB
  channel gains, including guided entry and portable preset settings.
- Curated eight width-limited documentation panels with multiple modes,
  greener C64 settings, reproducible conversion commands and an explicit
  refresh command; comprehensive galleries remain optional.
- Enlarged comparison sheets to 1328 pixels wide and split them into at most
  three rows per sheet. Converted previews retain their generated pixels and
  picture proportions, avoiding additional resampling of dithering patterns.
- Added a guided command builder, portable JSON presets and optional
  cross-platform path completion through the `guided` install extra.
- Added a Windows x64 portable test-build workflow, bundled guided launcher,
  source/executable parity checks and downloadable Actions ZIP artifacts.
- Separated target models and reusable colour constraints; added regression
  tests, public-domain/CC0 reference sources and reproducible gallery tools.
- Added consistent package/CLI version reporting, development installation
  extras, package smoke checks, Linux/Windows CI and the MIT software licence.

This records the current development milestone; no release or package upload
has been made by this housekeeping pass. Reference photographs retain the
individual rights documented in [samples/README.md](samples/README.md).
