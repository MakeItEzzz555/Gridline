# Provider Support

## Universal Agent Skills

For compatible hosts, use `npx skills@latest add MakeItEzzz555/Gridline --all -g`. Native provider packaging remains available below.

## OpenAI Codex

Native plugin install:

```bash
codex plugin marketplace add MakeItEzzz555/Gridline
codex plugin add gridline@gridline
```

The direct installer copies canonical skills into the current user's Codex skill directory. It deliberately does not add permanent routing prose to global AGENTS.md; skill metadata is sufficient for discovery and avoids extra always-on context.

## Claude Code
Claude Code supports personal skills, user-level subagents, and plugins. This repository is a Claude marketplace whose plugin lives in `providers/claude`. `scripts/validate-native.sh` runs Claude's strict plugin and marketplace validators when the CLI is available.

## Gemini CLI
The repository root is a Gemini CLI extension. Gemini discovers root `skills/` and `agents/` components. Canonical skills can also be copied into user scope. When Gemini CLI is installed, `scripts/validate-native.sh` probes its extension-command help before invoking an advertised `validate` command. The [current official reference](https://geminicli.com/docs/extensions/reference/) lists install/update/link commands but no standalone validator. Missing validator support is reported as NOT_TESTED; it does not establish extension installation, activation or rollback acceptance.

## Other agents
Canonical `skills/<name>/SKILL.md` directories follow the open Agent Skills pattern: YAML frontmatter plus Markdown instructions. Compatible tools can import or copy these directories.

Provider adapters may add subagents, manifests, hooks, policies, or MCP integrations, but reusable architecture knowledge belongs in the canonical skills.


## Versioning and updates

All provider manifests share one repository version. See [UPDATING.md](UPDATING.md) for provider-native update commands.
