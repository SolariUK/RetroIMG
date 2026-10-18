# Windows portable test build

This page covers the console build. The optional [desktop frontend](gui.md) has
its own Windows/Linux test bundles and graphical launcher.

This is a development test build of the CLI, including guided mode and Tab path
completion. It bundles Python and its dependencies; no separate Python or pip
installation is needed. The Windows build targets **Windows 10/11, x64**.

## Download and run

1. Open [Windows portable test build on GitHub Actions](https://github.com/SolariUK/RetroIMG/actions/workflows/windows-portable.yml).
2. Select a successful run. Under **Artifacts**, download `retroimg-windows-x64-...`.
3. Extract that download, then extract the enclosed
   `retroimg-0.2.0-windows-x64-test.zip` into a writable folder.
4. Keep the complete `retroimg` folder together, including `_internal`.
5. Double-click **Start guided.cmd**, or open PowerShell in that folder:

```powershell
.\retroimg.exe --version
.\retroimg.exe guided
.\retroimg.exe convert "C:\path\to\image.jpg" output.png --profile cpc-mode0 --cpc-mode constrained --dither bayer --scale 2
```

This is a console application. To use the guide, launch the `.cmd` helper or
pass `guided` explicitly; double-clicking `retroimg.exe` alone does not start a GUI.
Output images are saved to the paths you choose. Relative paths are resolved
from the terminal's current working directory.

Presets normally use `%APPDATA%\retroimg\presets`. To keep presets in your
current portable working folder instead:

```powershell
.\retroimg.exe guided --presets-dir .\presets
```

`BUILD.json` records the version, Git commit and bundled dependency versions.
`SHA256SUMS.txt` accompanies the downloadable ZIP. The software licence is in
`LICENSE.txt`; dependency metadata and licence files are retained under `_internal`.

## What to test

- Run a conversion with your own JPEG or PNG, using paths containing spaces.
- Try guided mode, Tab completion, cancellation, saving and loading a preset.
- Try your CPC blue-gain/brightness/contrast recipe and another target family.
- Keep a note of the commit in `BUILD.json` when reporting problems.

The workflow runs the regression suite, then tests the **extracted executable**
outside the checkout. It compares every supported profile/mode with the Python
converter, and checks JPEG input/output, built-in and file presets, and piped
guided input. Interactive console behaviour still needs a real Windows terminal.

## Build from a checkout

With a Python development environment activated on Windows:

```powershell
python -m pip install -e ".[dev,guided,bundle]"
python scripts/build_portable.py
python scripts/check_portable.py dist/portable/retroimg-0.2.0-windows-x64-test.zip
```

Use a new output directory for another build, for example
`python scripts/build_portable.py --output-dir dist/another-test`.
Builds use PyInstaller's portable-folder mode, packaged as a ZIP. Running the
builder on Linux produces a native Linux test bundle, not a Windows executable.
The GitHub workflow uses a Windows runner to produce the Windows build.

Test artifacts are retained for 14 days. The workflow can also be started using
**Run workflow** on its Actions page. These are temporary test downloads; no
GitHub Release or package-index publication is created.
