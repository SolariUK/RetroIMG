# Changelog

## 0.2.0 — Unreleased

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
