# Development

Use Python 3.10 or newer. From a checkout, create a virtual environment and
install development tools. Include `guided` to exercise optional path completion.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,guided]"
python -m pytest -q
```

Windows PowerShell (activation is optional):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,guided]"
.\.venv\Scripts\python.exe -m pytest -q
```

For a base installation use `.[dev]`. Completion tests skip when the optional
library is absent; the regression suite separately checks conversion and
guided entry with completion imports blocked. Installing without an extra does
not uninstall optional packages already present; use a fresh environment to
check the base dependencies.

## Package verification

In the development environment:

```bash
python -m build --outdir /path/to/new-dist
python scripts/check_distribution.py --dist-dir /path/to/new-dist
python scripts/check_distribution.py --dist-dir /path/to/new-dist --extra guided
```

The checks require exactly one wheel and one source archive. Each is installed
in a separate temporary virtual environment outside the repository, then checked
for version consistency, CLI registration, real conversion, presets, piped guided
input and presence/absence of the completion extra. Dependency installation needs
package-index access. Temporary environments and images are removed afterwards.

The source archive includes tests, examples, documentation and reference images;
the wheel contains the converter and software licence. The `[guided]` extra
works for either artifact. These commands do not publish a release.

## Automated checks

[GitHub Actions](.github/workflows/checks.yml) runs tests on Linux and Windows
with Python 3.10 and 3.13, both with and without the completion extra. A separate
matrix builds and checks wheel/source installations on both operating systems.
The workflow runs on pushes, pull requests and manual dispatch. Native Windows
terminal interaction still benefits from a manual check: start `retroimg guided`,
use Tab in paths with spaces, and try cancellation and a new output filename.

## Changes and examples

Keep target rules under `retroimg/targets`, reusable constraints under
`retroimg/constraints`, and previews separate from logical conversion. See
[architecture](docs/architecture.md) and [representations](docs/representations.md).
Preserve default bitmap behaviour and unrestricted palette/profile combinations.
Add regression coverage for changes that affect output or constraint validation.

The version lives in `retroimg/__init__.py`; setuptools metadata and
`retroimg --version` both use it. Record user-visible changes in
[CHANGELOG.md](CHANGELOG.md). Keep unreleased work marked as such.

Use the bundled [reference sources](samples/README.md) for reproducible public
examples. Keep large galleries and temporary experiments outside the repository.
See [examples/README.md](examples/README.md) for gallery generation and
`python examples/generate_samples.py --help` for curated sheets. Retain source
credits and rights records alongside published comparisons.
