# Reproducible candidate artifacts

This maintainer pipeline builds **UNQUALIFIED_CANDIDATE** bundles from an exact, locally available Git commit. It does not create a Git tag, GitHub Release, marketplace upload, attestation, automatic update or publication approval. Current manifests remain 0.7.0; these archives do not claim a new stable version.

## Build and verify

From a reviewed Gridline checkout, substitute the full 40-character commit SHA:

```bash
python3 scripts/build-release.py build --source-sha FULL_COMMIT_SHA --out /tmp/gridline-candidate
python3 scripts/build-release.py verify --source-sha FULL_COMMIT_SHA --out /tmp/gridline-candidate
```

`--repo /path/to/trusted/checkout` selects another local Gridline checkout. There is no network access or fallback to a moving branch/tag. Output must be a new directory; existing paths are never replaced. A failed write may leave an incomplete candidate directory; verification blocks it. Inspect it and choose another output path rather than automatically deleting files.

The tool reads Git objects at the pinned commit, not dirty/untracked working files. It verifies regular-file modes, tree membership and Git blob identities against `git archive`; export-ignore/substitution, symlinks and submodules are rejected. Git runs locally with a timeout, and snapshots/ZIP payloads are capped at 32 MiB and 10,000 files. Source snapshot capture is in memory; use only reviewed local repositories. Git configuration/executable and the selected checkout are part of the maintainer trust boundary.

Stable three-part manifest versions are currently supported. Do not bump a version merely to build a candidate. Prerelease-version syntax is explicitly unsupported until the repository adopts it. The archive filenames include both manifest version and source-SHA prefix; the manifest stores the full commit and tree SHAs.

## Outputs

- `gridline-VERSION-SHAPREFIX-source.zip`: complete tracked source tree, with required root README, LICENSE, portable plugin.json, Codex compatibility/marketplace, Gemini extension/context, skills, agents, documentation and standalone installers. This preserves existing entry points instead of moving root files.
- `gridline-VERSION-SHAPREFIX-claude.zip`: `providers/claude` placed at the ZIP root, plus the root LICENSE. The Claude plugin remains self-contained. Its synchronized skill folders must exactly match canonical skill folders; the root skill registry is not itself a mirrored skill.
- `file-inventory.json`: per-archive file path, byte size, SHA256 and executable mode. This is a file inventory, **not a dependency SBOM or license audit**.
- `release-manifest.json`: product/version, exact source commit/tree, artifact hashes/sizes, inventory hash and explicit unresolved qualification gates. `publish_allowed` is always false.
- `SHA256SUMS`: hashes of the two ZIPs, inventory and manifest. It does not hash itself.

ZIP members are sorted, stored without compression, and use fixed timestamps and explicit regular-file modes. This avoids clock, filesystem order, timezone and zlib-version differences. The source ZIP serves the existing Codex/Gemini/standalone entry points; duplicate identical ZIPs per client are unnecessary.

## Verification and trust

The verifier reconstructs candidate bytes from the **trusted local pinned Git source**, checks every file and independently reads ZIP entries without extracting/executing them. Rewriting a manifest and SHA256SUMS cannot make modified content match that source. Wrong source SHA, extra/missing files, different bytes, link/special entries, traversal, Windows device/drive aliases, case/Unicode collisions and file/directory conflicts are blocked.

This verifies correspondence to the selected source and deterministic bundle format. It does not authenticate the publisher, establish that the checkout came from the intended repository, scan source for secrets, validate legal compliance or approve native host behavior. Independently verify repository ownership/source provenance before trusting the pin. Checksums obtained from the same compromised channel alone are insufficient.

The public CLI has no extraction/install command. Tests materialize already-validated bytes only into disposable directories. Never execute scripts from an unreviewed package merely because its checksums are internally consistent.

## CI and provider acceptance

The existing CI validation job runs the regression suite, builds/verifies candidate bundles and retains them as `gridline-unqualified-SHA` workflow artifacts for seven days. Artifact retention is for review, not a stable release. GitHub's [official upload action](https://github.com/actions/upload-artifact) is pinned to v7.0.2 commit `cf430e030ddbb5b0abf93d22962f4752f3646cd9`; repository permissions remain `contents: read`. No signing key, write-scoped release token or deployment environment is added. GitHub recommends immutable action pins in its [secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use).

Tests cover byte-identical builds, dirty/untracked exclusion, version/provider-mirror drift, altered payload/checksum/manifest, malicious ZIP entries, Git links/submodules/export transforms, and runnable drawing engines from real source/Claude archives. A disposable POSIX filesystem fixture uses the existing trusted Bash installer for version A → B, blocks tampered B before installation, preserves a foreign skill, and restores A plus its local customization from the install backup. This is not a real Claude/Codex/Gemini activation/update qualification. The Bash upgrade fixture is explicitly skipped on Windows; Windows runs package tests and the existing PowerShell installer smoke separately.

Before stable publication, independently complete professional/security review, source/release approval, secret/license/SBOM review, publisher attestation, final native Blender and authorized AutoCAD copy acceptance, real provider clean install/update/rollback and final-head CI. The manifest leaves all these gates unresolved. Do not change its gate fields to approve publication; the verifier rejects metadata differing from the pinned-source candidate contract.

## Rollback boundary

This pipeline replaces no installation. Existing installers retain their ownership checks and per-item backups; they are not an all-items atomic updater. Review candidate A/B source and permissions before consented installation. Preserve the current item, restore the matching reviewed backup and start a fresh provider session. Test fixtures prove a bounded temporary-home recovery path, not every live provider or native CAD workflow.

## Implementation receipt (2026-10-25)

Base: `fdc678a78a48832535efc4d56977d0aafb45bca9`. This independent packaging branch does not include unmerged book/update/standards PRs #37–#39. No version bump, merge or publication is implied.

Local final checks: repository validator and full-folder provider parity PASS; pinned offline CAD suite (`GRIDLINE_REQUIRE_CAD_TESTS=1 uv run --offline --with ezdxf==1.4.5 --with matplotlib==3.11.2 --with pypdf==6.21.2 python -m unittest discover -s tests -v`) passes **131 tests, no skips**, 63.634 seconds. Eight release-specific tests pass. The hostile duplicate-ZIP fixture intentionally emits a duplicate-name warning. The POSIX A/B test is a temporary-home fixture, not a real provider activation receipt; Windows explicitly skips that one Bash recovery test and retains separate PowerShell smoke coverage.

Same-agent bounded Ponytail/security review traced Git inputs, archive metadata/readback, manifests/inventory/checksums, installer ownership/backups, tests and CI. No user paths are replaced; untrusted archive contents are not executed by the packager/verifier. The first test run assumed an unknown commit would raise ValueError; corrected the test to also recognize the fail-closed Git subprocess error already handled by the CLI. No independent reviewer approval, SBOM/attestation, native CAD acceptance or complete real-provider upgrade qualification is claimed. Provider/token savings are unavailable; no model calls or downloads were launched.
