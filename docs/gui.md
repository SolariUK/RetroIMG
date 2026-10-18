# Desktop frontend for Windows and Linux

The optional PySide6/Qt Widgets desktop frontend uses the same conversion engine,
constraints and JSON presets as the CLI. It includes all system profiles and a
separate original-colour pixelation workflow. The CLI needs no Qt installation.

## Run from a checkout

Activate your Python virtual environment, then:

```bash
python -m pip install -e ".[gui]"
retroimg-gui
# Or open an image immediately:
python -m retroimg.gui /path/to/photo.jpg
```

Install and run the frontend on your Windows or Linux **desktop**. An SSH/VS Code
remote terminal does not itself provide a desktop display. Automated tests can
use Qt's offscreen backend; interactive use requires a graphical session.

## Editing

- Open or drop a local image. Use the mouse wheel over either preview to zoom
  around the pointer, and drag to pan. Each panel zooms independently; its zoom
  selector shows the current percentage and offers fit-to-panel, 100%, 200%,
  400% and 800%. Wheel zoom ranges from 1% to 3200%.
- Choose a machine, profile and conversion mode. **Palette only** converts using
  the chosen palette; **Hardware constrained** also applies the system's colour,
  attribute or tile rules. The description beneath the selector explains them.
  Variants such as HAM6, EHB and repeated/mirrored playfields remain separate.
  CLI identifiers and saved presets retain their existing names (`bitmap`,
  `attributes`, `tiles`, etc.).
- New machine/profile selections default to the first hardware-constrained mode.
  Palette only remains selectable, and loading a preset preserves its chosen
  mode. C64 hires has two local colours per 8×8 cell; C64 multicolour uses a
  shared background plus three local colours per 4×8 cell.
- Available modes, palettes, Amiga screen-colour counts and Atari band height
  follow the shared registry. Custom dimensions show the relevant cell multiples.
  Bayer matrix size appears only for Bayer dithering.
- Source adjustments run before palette conversion. Display controls follow
  enlargement: RF, chromatic aberration, LCD/CRT treatment, bloom and final display
  brightness. Independent effects remain available for every machine.
- Source and Display each have a reset button. Source reset restores neutral
  adjustments. Display reset clears the effects, restores neutral display
  brightness and enables automatic enlargement. Each reset affects only its tab.
- Automatic enlargement is enabled initially. It chooses an integer scale for
  roughly a 640-pixel longest edge, accounting for the selected profile, custom
  logical resolution and pixel aspect. Typical defaults are 1× for 640-column
  profiles, 2× for Mega Drive/Spectrum and 4× for Game Boy. The native conversion
  resolution is preserved. Turn off Automatic enlargement to set a fixed scale;
  the resulting output dimensions are shown beneath the control. Loading a
  preset preserves its numeric scale and switches to manual enlargement.
- LCD, scanlines and CRT grille enforce minimum output enlargement 3. Bloom
  radius appears when bloom is enabled. Pixelation exposes only its block size.
- Changes are applied after a short pause. Rendering runs in a cancellable child
  process. Display-only changes reuse the most recent indexed conversion.
  Superseded results cannot overwrite the latest requested preview.
- Export saves the **full rendered image**, independent of panel size or zoom.
  Export is unavailable while settings are pending, invalid or cancelled. PNG
  preserves rendered RGB pixels; JPEG uses ordinary lossy image encoding.
  The source image cannot be overwritten through export.

Fit-to-panel can alter fine dithering, grille or scanline patterns. Use 100% to
judge the actual saved pixels. Increasing the output enlargement is distinct
from zooming the preview panel.

## Presets

The preset list includes built-in recipes and the same per-user JSON directory
as the CLI. Apply a listed preset, load a file, or save the current conversion.
Changing presets updates the available controls. Pixelation does not use retro
conversion presets. Use `--presets-dir /path/to/presets` for a separate directory.

## Portable downloads

Versioned builds are attached directly to
[GitHub Releases](https://github.com/SolariUK/RetroIMG/releases). Download
`retroimg-gui-VERSION-windows-x64.zip` or `retroimg-gui-VERSION-linux-x64.zip`
and extract it once. A shared `SHA256SUMS.txt` accompanies release downloads.

The **Desktop GUI test builds** GitHub Actions workflow builds Windows x64 and
Linux x64 development bundles natively. Download a successful run's application
artifact (`retroimg-gui-...-test.zip`) and extract it once. Its `.zip.sha256`
checksum is a separate download. Keep the complete `retroimg-gui` folder
together. Double-click `retroimg-gui.exe` on Windows, or run `./retroimg-gui` on
Linux. No separate Python installation is required. If extraction loses the
Linux executable bit, run `chmod +x retroimg-gui` first.

Linux builds depend on desktop system libraries and are not universal across all
distributions. CI installs the EGL/OpenGL runtime libraries (`libegl1`, `libgl1`)
even for offscreen GUI tests: Qt's GUI module links to them at import time.
Portable Linux builds use Ubuntu 22.04 and also install `libxcb-cursor0` so
PyInstaller can bundle it with the X11 plugin. Local Ubuntu GUI builds need these
libraries too: `sudo apt install libegl1 libgl1 libxcb-cursor0`.
Windows and Linux still need hands-on checks
for display scaling, file dialogs, dragging, panning and desktop integration.

```bash
python -m pip install -e ".[dev,gui,bundle]"
python scripts/build_portable.py --gui --output-dir dist/gui
python scripts/check_gui.py dist/gui/retroimg-gui-0.2.1-linux-x64-test.zip
```

Use a fresh build directory. The archive contains `BUILD.json`, application and
dependency metadata/licences, a README and the complete Qt runtime needed by the
application. Qt Widgets is provided by the Essentials package; Qt WebEngine and
the larger Addons package are not required. Windows GUI builds do not open a
console window. Local builds default to development test bundles. Add `--release`
to omit the test suffix and mark release metadata; neither mode uploads anything.
The [release workflow](releases.md) creates draft releases for review. Portable
downloads are folders rather than installers.

The automated check starts the extracted application offscreen outside the
checkout and exercises its actual child process, a CLI-equivalent export,
conversion caching and shared presets.
