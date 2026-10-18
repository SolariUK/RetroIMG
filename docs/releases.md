# Preparing GitHub releases

The [Prepare draft release workflow](../.github/workflows/release.yml) builds
Windows/Linux x64 desktop applications and a Windows x64 command-line application.
It runs tests and checks each extracted bundle, then creates a **draft preview
release** with the three application ZIPs and one shared `SHA256SUMS.txt`.
Users download a release ZIP directly and extract it once.

## Prepare a version

1. Set the application version in `retroimg/__init__.py`.
2. Add the matching `docs/releases/VERSION.md` release notes, including download
   names and platform requirements. Keep the changelog accurate.
3. Commit and push the changes. Create an annotated tag for that exact commit:
   `git tag -a vVERSION -m 'RetroIMG VERSION'`, then `git push origin vVERSION`.
   Replace `VERSION` with the new application version; use a new tag rather than
   moving an existing release tag.

The tag triggers the release workflow. Its version must exactly match the
application version, and release notes must exist in the tagged checkout.
Each native build records the version and commit in `BUILD.json`; the assembly
step verifies that all three bundles have the expected platform, version and
commit and are marked as release builds before calculating their checksums.
Release ZIP names omit the development `-test` suffix.

The workflow uses GitHub's built-in repository token. No personal access token
or local GitHub CLI login is needed. Only the final draft-creation job requests
write access; build jobs have read access.

## Review and publish

When all jobs pass, open the repository's
[Releases page](https://github.com/SolariUK/RetroIMG/releases) while signed in
with write access. Review the draft notes and its four downloadable assets,
and test the applications on the intended desktops. The workflow leaves
**This is a pre-release** selected; adjust that if appropriate, then click
**Publish release** when ready. Draft creation does not publish the release.
For a regular release featured in the repository sidebar, clear the pre-release
checkbox and select **Set as latest release** before publishing.

After publishing, give that version its own released changelog section and start
a fresh **Unreleased** section for subsequent work. Keep the application version
unchanged until preparing the next versioned release.

For an existing tag, the workflow can also be started from **Actions → Prepare
draft release → Run workflow**, choosing branch **main** and entering the tag.
Use this after repairing release automation: **Re-run jobs** on an old run uses
that run's original workflow definition, including the old settings. Application
builds still check out the requested version tag. Re-running updates assets
only while the release is still a draft; it refuses to overwrite an already
published release. It retains existing draft notes so edits made on GitHub
are not lost. Use a new version and tag for a subsequent published release.

## Test builds versus releases

Ordinary pushes continue to produce temporary Actions test builds, with
`-test.zip` names and 14-day retention. The application ZIP and its matching
`.zip.sha256` checksum are separate direct downloads, without another ZIP wrapper.

Release builds use the same builder and extracted-application checks. To make
a local release-style bundle, add `--release` to `scripts/build_portable.py`.
Local builds do not create tags or upload/publish a GitHub release. The first
preview uses tag `v0.2.0` with GitHub's pre-release flag; that flag is separate
from the application version recorded in the package.

The assembly job downloads application ZIPs with `skip-decompress: true` so
GitHub preserves the original release archives instead of extracting them.
