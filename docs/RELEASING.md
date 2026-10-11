# Maintainer guide — TakePath beta releases

This page is for repository maintainers. The [README](../README.md) is for people using TakePath.

## Release policy

- `main` is the development branch. A passed **unit-test** run does not imply native recording/replay has been tested.
- Beta tags have a hyphen, for example `v1.2.0-beta.1`. The release workflow marks tags containing `-` as GitHub **Pre-release**.
- The publish job runs only for `v*` tags and only after Windows, both macOS, and Linux packaging jobs succeed.
- Don't reuse an existing release tag for newer commits. Increment the beta number.
- The generated applications are unsigned; macOS bundles are not notarized. macOS/Linux X11 remain preview.

## Before tagging `v1.2.0-beta.1`

1. Review and merge the release-polish PR. Ensure all **Core tests** checks for that merged `main` revision pass.
2. Go to **Actions → Cross-platform Release → Run workflow**, select `main`, and run it. A manually dispatched run builds packages and exposes Actions artifacts **without publishing a release**.
3. Wait for Windows x64, macOS x64, macOS arm64, and Linux X11 to complete successfully. This only confirms package generation.
4. Download `windows-assets` from the Actions run. On a Windows 10/11 machine, extract and test `TakePath-windows-x64.exe` and the one-folder portable ZIP.
5. Work through [the 1.2.0 acceptance checklist](../RELEASE_CHECKLIST.md). The minimum pre-beta smoke tests include recording/replay, moving and resizing a browser window, adaptive wait, F8 abort, and secure dummy-field protection.
6. Review [1.2.0 beta notes](../CHANGES_V12.md) and make sure known limitations are accurately stated.

## Create the beta release

Run in a local checkout with a clean working tree:

```bash
git checkout main
git pull --ff-only origin main
git log -1 --oneline
git tag -a v1.2.0-beta.1 -m "TakePath 1.2.0 Beta 1"
git push origin v1.2.0-beta.1
```

The tag starts **Actions → Cross-platform Release**. When every build job succeeds, the publish job uploads the Windows, macOS and Linux binaries and `SHA256SUMS.txt` and produces the GitHub Release.

Open [Releases](https://github.com/jiniyasshah/TakePath/releases) and confirm:

- The version/tag and release notes are correct.
- **Pre-release** is shown, not Stable/Latest.
- All nine expected downloadable assets are present.
- The published Windows build launches and the checksums match.

If the tag build fails, correct the branch and create `v1.2.0-beta.2` instead of moving or reusing `v1.2.0-beta.1`.

## Stable release criteria

Do not promote to `v1.2.0` stable just because CI passes. Complete native tests for the advertised platforms, address any security or accuracy regressions, and assess code signing/notarization and multi-monitor/display-scaling behavior.
