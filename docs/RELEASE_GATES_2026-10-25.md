# Release qualification checkpoint — 2026-10-25

Base audited: `fdc678a78a48832535efc4d56977d0aafb45bca9`, fetched origin/main, includes #33. [Base CI](https://github.com/MakeItEzzz555/Gridline/actions/runs/40139402104) concluded success. This is not current-branch CI or independent native acceptance.

## Version and package evidence

- Latest published release: historical `v0.5.0`, title Architect Agent Superpowers, 2026-10-21. Preserve it and its tags.
- Current root portable manifest, Codex compatibility manifest, nested Claude plugin, Claude marketplace, Gemini extension and skill registry declare **0.7.0**. The new distribution metadata must match them.
- `git log v0.5.0..fdc678a` includes ownership-safe installer fixes, coordinated CAD, rebranding, spec impact/MCP, source-detail gates, native readback and topology hardening. It is not just a branding patch. Tentative **0.8.0** next minor is a proposal, not an existing or approved release. Final selection depends on the accepted diff; no versions bumped here.
- Root plugin.json is required portable discovery; .codex-plugin/plugin.json is a compatibility adapter. Claude's actual plugin lives under providers/claude, selected by .claude-plugin/marketplace.json. Gemini uses root gemini-extension.json and GEMINI.md. Canonical skill references and scripts must ship with each skill.
- Existing ci.yml checks Linux CAD tests and provider parity plus Windows topology/GLB and PowerShell installation. No dedicated release/artifact/attestation workflow exists at this base. Do not equate validation CI with release qualification.

## Root cleanup decision

No root files moved. README.md, LICENSE, plugin.json, gemini-extension.json and provider entry points stay. tests/check_repo.py explicitly requires INSTALL_PROMPT.md; README and provider docs link to the root roadmap/install documents. Public links are also consumers. Any future move needs a complete reverse-link and extracted-installer audit plus compatibility redirects. No deletion is justified just to shorten the root listing.

## Gates for an approved candidate

| Gate | Status / required evidence |
| --- | --- |
| Independent security/architect/Ponytail review | NOT_RUN; current review is same-agent only. CodeRabbit cannot be assumed available or passed. |
| Tagged source and asset provenance | NOT_BUILT; resolve exact source commit, never infer it from target_commitish. |
| Deterministic provider archives, SHA256SUMS, release manifest, SBOM/third-party notices, attestation | NOT_BUILT. No unsigned archive is silently trusted. |
| Native Blender geometry and corruption regression on final candidate SHA | NOT_TESTED for this package; preserve #33 checks and receipt dimensions. |
| Native AutoCAD copy edit/AUDIT/plot/roundtrip | NOT_TESTED; #15 approval/revision controls and explicit copy-write scope apply. No current project/session altered. |
| Real Claude/Codex/Gemini A→B install/update/rollback | NOT_TESTED; temporary-home installer tests are not model activation evidence. |
| Malicious/tampered archive, traversal, symlink and interrupted-update tests | Required before any new archive installer exists. Checker performs no archive processing. |
| Final candidate Linux/Windows CI | Must be checked at final head, not base or superseded head. |
| Professional/regulatory acceptance | NOT_RUN; no certified BIM or Cyprus compliance claim. |
| Owner release publication approval | REQUIRED after gates; unmerged PR authorization is not stable release approval. |

## Remaining issue dependency register

All ten issues remain open; none are closed by release discovery or book records.

| Issue | Status | Next acceptance dependency |
| --- | --- | --- |
| #10 | PARTIAL | Actual external 40-sheet ground truth and measured recall |
| #11 | BLOCKED for IFC release claim | Separate schema/IDS fixtures and independent reference validation |
| #12 | PARTIAL | Real host matrix, permission/revision/rollback tests |
| #13 | PARTIAL | Semantic IFC/native revisions, quantities and human review |
| #14 | BLOCKED for reconstruction claim | Ambiguity/scale benchmark and human confirmation workflow |
| #15 | BLOCKED for authoritative native writes | Typed state/proposals, approval, concurrency and native rollback |
| #16 | PARTIAL | Native CAD edit/plot/DWG roundtrip on approved copies |
| #29 | PARTIAL | Final object-role, native/GLB and visual acceptance before closure |
| #32 | BLOCKED for oblique/curved claim | Supported geometry kernel, independent readback and corruptions |
| #36 | PARTIAL | Meaningful API contracts and final tool coverage scope |

Previously closed #27/#28/#34/#35 remain regression obligations. No re-closure or comment is needed without new evidence. #33's rate-limited incremental CodeRabbit pass remains REVIEW_NOT_RUN, not an approval.

Cross-repository rollout to tuck-bit/widget kits waits for accepted Gridline manifest/checker behavior and each repository's own inspected contracts and tests. Grapharium has no assumed plugin contract. No other repository or public release changed in this package.

## This package's executed validation and bounded review

- `python3 tests/check_repo.py` and `python3 scripts/sync-provider-skills.py --check`: PASS, 30 skills, 62 activation fixtures.
- `GRIDLINE_REQUIRE_CAD_TESTS=1 uv run --offline --with ezdxf==1.4.5 --with matplotlib==3.11.2 --with pypdf==6.21.2 python -m unittest discover -s tests -v`: **130 tests, OK, no skips**, 62.071 seconds after final parser change. Seven new tests cover SemVer precedence, unknown/offline behavior, untrusted URL/draft/preview rejection, size/encoding/decoder errors, redirects, opt-in networking and manifest consistency. Existing temporary-home installer tests cover interrupted per-item replacement/backup restoration; no new installer or full A/B upgrade was implemented.
- `bash scripts/validate-native.sh`: PASS with Claude Code **2.1.308** strict plugin/marketplace validation and Codex CLI **0.164.0** isolated marketplace/plugin installation. Claude reports catalog icon missing; validator explicitly says its safety/policy directory review is separate. Gemini CLI absent, NOT_TESTED. No model calls or active-session configuration changes.
- `python3 scripts/check-updates.py --check-network`: live endpoint reported LOCAL_AHEAD for checkout 0.7.0 versus published v0.5.0. Artifact/source authentication remains NOT_CHECKED. Default invocation tested to avoid network.
- Same-agent Ponytail/security review covered the new CLI, manifests, existing installer ownership/backups, checker caller, docs and tests. No arbitrary feed/URL, download, hook execution, file replacement, settings mutation or credential loading added. Expected workload: a user-triggered local command, no daemon. An initial parser-depth test wrongly assumed a fixed Python recursion limit; replaced with a deterministic decoder-error test before final suite. No independent reviewer approval claimed.

Status: DONE for the read-only checker/version-consistency precursor; PARTIAL for update/release system. Standards activation, native release acceptance, real-provider upgrades, verified archives/attestation and cross-repository adoption remain separate dependencies. This is a checkpoint before a fresh-session candidate phase, not permission to publish.
