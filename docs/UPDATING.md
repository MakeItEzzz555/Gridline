# Updating Gridline

## Clone-based install

Pull the latest version and reinstall only runtimes already present on the machine.

### macOS / Linux

```bash
git pull --ff-only
bash scripts/install-global.sh auto
```

### Windows PowerShell

```powershell
git pull --ff-only
powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1 auto
```

The installers stay user-scoped. Each host home gets a `.gridline.installed` list of the skill and agent paths this pack installed. Only those are replaced on update; the previous version is moved (never deleted) to `backups/gridline-<timestamp>/` in that home.

If a skill or agent with the same name exists but is not on that list (another pack, a plugin-manager install, or an install made before 0.5.1), the installer changes nothing and exits with code 4, listing the paths. Check those paths first. To replace them anyway, re-run with `--force` (`-Force` on Windows); they are moved to the backup folder.

If an install stops partway (for example, a full disk), every item is either its previous version or the new one, never missing. Items already replaced stay updated; re-run the installer to finish.

To restore an item, move it back from the backup folder over the installed copy.

## Claude Code plugin

```bash
claude plugin update gridline@gridline
```
## Gemini CLI extension

```bash
gemini extensions update gridline
```

Restart the Gemini CLI session after an extension update so new components are loaded.

## Maintainer verification

```bash
python3 scripts/sync-provider-skills.py --check
python3 tests/check_repo.py
bash -n scripts/install-global.sh
```

If Claude Code is installed:

```bash
claude plugin validate --strict ./providers/claude
claude plugin validate --strict .
```


## Rebranding from Architect Agent Superpowers to Gridline (0.7.0)

The project and repository are now **Gridline**. New installations use
`MakeItEzzz555/Gridline` and the plugin/extension ID `gridline`.
Individual skill names and agent names have not changed.

- **Bash / PowerShell:** The new `.gridline.installed` ledger also recognizes
  paths in the previous `.architect-agent-superpowers.installed` ownership
  ledger, so a normal update preserves existing skills without requiring
  `--force` or `-Force`. Foreign skills are still protected. Old backup
  folders remain untouched; new backups use `backups/gridline-<timestamp>/`.
- **Native plugins / extensions:** The new `gridline` identifier may be seen
  as a separate package by Claude, Codex and Gemini. Check your provider's
  installed-plugin list and uninstall the old
  `architect-agent-superpowers` identity via the official provider commands
  before installing `gridline`. Avoid removing shared skills or unrelated
  extensions. Reload your agent afterwards.
- **Existing Git clones:** Update the remote after the GitHub repository
  rename with `git remote set-url origin https://github.com/MakeItEzzz555/Gridline.git`.
  Your checkout folder does not need to change.
- Old tags, Git commit history, external URLs and existing backup directories
  are intentionally not rewritten.

## Opt-in release discovery (read-only)

```bash
python3 scripts/check-updates.py
python3 scripts/check-updates.py --check-network
python3 scripts/check-updates.py --release-json /path/to/captured-release.json --installed-version 0.7.0
```

The first command performs no network request. Only `--check-network` consents to one fixed public GitHub API request, with a ten-second timeout, 1 MiB response limit and no redirect following. No credentials, hooks, downloads, settings changes, installation or background polling are involved. `--release-json` is offline evidence, not authentication of a release.

Statuses: UNKNOWN (not requested, offline or invalid evidence), UPDATE_AVAILABLE, CURRENT, LOCAL_AHEAD. Unavailable/invalid evidence exits 2; valid classifications and intentional network-off mode exit 0. The installed version defaults to **this checkout's** root manifest, not a provider cache. Supply the actual provider-installed version when comparing a separate installation. CURRENT means version precedence matches; it does not attest installed bytes. Build metadata does not affect SemVer precedence. Only stable published releases are accepted; previews are not offered.

`distribution.json` records version and provider paths, but `release_qualification: NOT_VERIFIED` deliberately prevents representing this metadata as a qualified release manifest. The checker always reports artifact verification NOT_CHECKED and source SHA null: GitHub's release `target_commitish` may be a branch, not immutable provenance. Resolve the tag to its commit and verify an approved artifact/checksum/attestation independently before installing. A checksum from the same compromised source alone does not authenticate the publisher.

### Provider behavior verified against official documentation, 2026-10-25

- **Claude Code:** [official update documentation](https://code.claude.com/docs/en/discover-plugins) says third-party marketplace auto-update defaults off. Users may enable it in `/plugin` → Marketplaces. `claude plugin marketplace update gridline` refreshes the listing; `claude plugin update gridline@gridline` updates the installed plugin. Start a fresh session or follow the installed CLI's supported reload instruction. Gridline does not change that setting.
- **Gemini CLI:** [extension reference](https://geminicli.com/docs/extensions/reference/) documents `gemini extensions update gridline` and explicit install `--auto-update`. Restart after updates. Gridline does not enable auto-update or skip consent. This host is NOT_TESTED locally.
- **Standalone Codex skills:** inspect a pinned source diff and permissions, then explicitly run the existing installer for the intended host. Its ownership ledger and per-item backups remain the update path. Reinstalling owned paths replaces local edits too; save customizations separately and compare backups before continuing. A linked skill follows its source checkout; it does not need an invented marketplace notifier. Start a new session for verification.
- **Public ChatGPT/Codex Plugin Directory:** [OpenAI submission documentation](https://developers.openai.com/plugins/deploy/submission) requires a new ZIP for bundled skills/metadata, followed by review. Hosted MCP tool scanning is separate. A GitHub tag does not update the uploaded bundle.

### Safe manual rollback

Stop new provider sessions, preserve the current installed item in a separate recovery folder, and restore the matching item from its timestamped backup. Validate it and start a fresh session. Restore all intended items from the same reviewed revision; the existing installer is atomic per item, **not an all-items transaction**. Do not remove ownership ledgers or foreign skills. Existing tests exercise interrupted replacement and backup restoration in temporary homes. A complete real-provider version A → B → rollback acceptance remains NOT_TESTED; this read-only checker does not implement an updater.

Release qualification and next dependencies: [2026-10-25 release gap record](RELEASE_GATES_2026-10-25.md).
