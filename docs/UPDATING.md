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

## Candidate artifact verification

Maintainers can build and verify pinned, reproducible source/Claude archives using [the release artifact pipeline](RELEASE_ARTIFACTS.md). These are explicitly unqualified review artifacts; neither their checksums nor a green packaging job authorizes installing or publishing a stable release.
