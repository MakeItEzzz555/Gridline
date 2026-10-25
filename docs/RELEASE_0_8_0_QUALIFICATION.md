# 0.8.0 candidate qualification — 2026-10-25

**PARTIAL — stable publication blocked.** This branch integrates PRs #37–#40 from main `fdc678a78a48832535efc4d56977d0aafb45bca9`. Seven manifests propose 0.8.0. No tag, release, marketplace upload or merge is implied. The historical v0.5.0 tag remains unchanged.

## Delivered scope

- **DONE:** 15 individually recorded books, 45 bounded claims, original practice references and Claude parity. Full paid texts were not read. B14 still lacks a publisher-verified ISBN; catalogue metadata is not publisher evidence. See [coverage and claims](RESEARCH.md).
- **DONE:** offline-by-default update discovery, version consistency and real provider-specific update instructions. No unattended installation or universal marketplace notification.
- **DONE:** versioned source/jurisdiction triage with fail-closed rule activation. Cyprus adopted clauses, national/local applicability and professional signoff remain unverified. Design books are not binding codes.
- **DONE:** deterministic source/Claude candidate archives, exact Git provenance, inventory, tracked-file SPDX SBOM, SHA256SUMS and hostile-input/A→B/rollback fixture tests. [Artifact contract](RELEASE_ARTIFACTS.md).
- **PARTIAL:** envelope/assembly/material/site/drawing-stage/native-authoring playbooks are source-cited review guidance. They do not supply validated engineering dimensions, lawful paid-standard clauses or project-specific professional acceptance.
- **PARTIAL:** root compatibility is preserved additively; README, LICENSE, plugin.json, Gemini/Codex/Claude entry points and installer paths remain. No root deletion or migration is needed for this candidate.

## Open-issue acceptance matrix

| Issue | Status | Evidence or next dependency |
| --- | --- | --- |
| [#10](https://github.com/MakeItEzzz555/Gridline/issues/10) | PARTIAL | Existing spec revision checks do not parse an independent 40-sheet external CAD/PDF set. Need seeded corpus, source-addressed findings and measured missed defects. |
| [#11](https://github.com/MakeItEzzz555/Gridline/issues/11) | BLOCKED for release claim | IFC schema + independent IDS validation and valid/adverse IFC2X3/4/4X3 fixtures are not implemented. GLB is not IFC. |
| [#12](https://github.com/MakeItEzzz555/Gridline/issues/12) | PARTIAL | Blender CLI and read-only AutoCAD inspection exist. Other licensed hosts, adapter security/rollback and version-specific native smoke evidence remain. |
| [#13](https://github.com/MakeItEzzz555/Gridline/issues/13) | PARTIAL | Bounded native Blender/GLB authoring/readback exists. Semantic IFC entities, GUIDs, quantities, IDS and revision round trips remain. |
| [#14](https://github.com/MakeItEzzz555/Gridline/issues/14) | PARTIAL | Intake confidence gates are precursors. Calibrated per-element scan reconstruction and genuine degraded benchmarks remain. |
| [#15](https://github.com/MakeItEzzz555/Gridline/issues/15) | BLOCKED for existing-project writes | Canonical versioned state, typed proposals, optimistic concurrency, approval, atomic native transactions and crash/rollback proofs remain. This candidate authorizes no live-project edits. |
| [#16](https://github.com/MakeItEzzz555/Gridline/issues/16) | BLOCKED for DWG claim | ezdxf checks do not establish native AutoCAD AUDIT, fonts/XREF/layout/PDF scale or editable DWG/DXF round trips. Requires licensed-host safe-copy acceptance. |
| [#29](https://github.com/MakeItEzzz555/Gridline/issues/29) | DONE for bounded reproduced defect | #33 merged to main. Fresh Blender 5.2.3 LTS full-villa native/GLB readback passes (442 meshes), seven native faults reject. Existing selection on/off/render evidence and role/inventory checks remain applicable. No blanket thin-member deletion or original-file mutation. [Evidence](VILLA_TOPOLOGY_REPAIR_2026-10-24.md). |
| [#32](https://github.com/MakeItEzzz555/Gridline/issues/32) | BLOCKED for geometry-support claim | Mixed oblique/curved joins remain explicitly unsupported; need a bounded robust kernel and independent adverse/native proofs. Orthogonal examples cannot close this ticket. |
| [#36](https://github.com/MakeItEzzz555/Gridline/issues/36) | PARTIAL | New release APIs document contracts, but the reported original 15-file/78-function coverage scope and meaningful domain docstrings need measured completion. A rate-limited CodeRabbit rerun is not approval. |

BLOCKED here describes a release claim or external acceptance dependency, not a claim that an unimplemented feature cannot be developed. Each unfinished issue stays open until its own acceptance criteria pass.

## Remaining stable-release gates

1. Exact integrated-head Linux/Windows CI and artifact equality; review the actual integration diff and recorded counterexamples. Same-agent Ponytail review does not provide independent architect/security approval.
2. Complete runtime/dependency/license/secret review and publisher attestation. The SPDX SBOM lists tracked files only; NOASSERTION fields are unresolved, not approvals.
3. Final-source provider clean install, update and rollback: Claude/Codex isolated validation is partial; Gemini runtime is unavailable. Public Plugin Directory bundles require separate upload/review, not a GitHub tag.
4. Native acceptance must match advertised executable capabilities. Existing Blender receipts cover the bounded experimental orthogonal sample/villa only. DWG round trips, semantic IFC/IDS and additional host adapters are future capabilities; they block those claims, not a guidance-only or explicitly limited release. Preserve unsupported labels.
5. Obtain the required reviewed merge decision and qualified publication approval. Do not auto-merge the open PRs. Do not convert an unqualified candidate to stable by editing its manifest status.

## Future roadmap, separate from candidate release blockers

Issues #10–#16, #32 and #36 remain open. They are not prerequisites for an explicitly limited skill/guidance release unless release notes promise those missing capabilities. Completing the entire master plan still requires their acceptance criteria and professional/adoption evidence. #15 remains mandatory before existing-project writes. TuckBit and widget-kit reuse need separate repository-specific reviewed PRs; Grapharium applies only if it distributes skills.

## Counterexamples and corrections retained

- Wrong B14 ISBN13 and publisher attribution were corrected; lawful catalogue evidence does not close the publisher gap.
- Windows Git line endings and original ZIP filename normalization changed packaging behavior; canonical blob checks and raw-name regressions now cover them.
- Git replacement refs could substitute B while requesting pinned A; object reads disable replacement refs and test this exact attack.
- Source/envelope guidance and Eurocode transition dates do not prove local adoption; activation stays disabled.
- Orange selection lines are overlays; measured parapet/guard duplicate volume was a separate geometry defect. The repair preserves explicit roles and intentional thin members.
- During integration, Codex initially ran a local merge in the original checkout. It aborted the conflict, retained a checkpoint branch, and restored the exact clean original `a1c7797e151edde8cf6e8d76807da901de708bf2`. No remote main or user project was changed. All subsequent integration work uses the isolated worktree.

No independent agents, native inference experiments, new MCPs, paid book copies or native application-session changes were used. Temporary native outputs and logs require retention outside ephemeral /tmp before relying on them long term.

## Combined validation receipt

The pinned offline CAD suite passes **156 tests, zero skips** in 66.223 seconds. The existing CSV-reader ResourceWarning is retained as a nonfatal limitation. Repository/provider checks pass. Thirteen release-specific tests pass after adding the commit-timestamp assertion. Fresh full-villa native/GLB readback passes; all seven native corruption seeds reject. The [machine receipt](evidence/release-0.8.0/qualification.json) records exact code, original-source and generated-file hashes. CI and artifact checks must still be read at the final pushed SHA.

## Follow-up qualification (same bounded release phase)

The [follow-up receipt](evidence/release-0.8.0/followup.json) reviews exact original candidate bb215149ad3e. Actual provider lifecycle commands now pass in isolated homes: Claude local marketplace update 0.7.0→0.8.0 and uninstall/reinstall rollback; Codex native-plugin remove/reinstall lifecycle with version readback; actual-source standalone installer A/B and manual backup rollback preserving customization/foreign skills. This establishes CLI/filesystem lifecycle behavior, not model activation, Git marketplace auto-update or every operating system. Public Directory submission and Gemini remain NOT_RUN/NOT_TESTED.

Optional CAD dependencies are installed separately, not bundled. OSV returned no matching advisories for the 16 observed package versions. A clean pip-free environment contains 15 CAD distributions with 3,272 recorded files verified and no mismatches. The original pip tooling environment has nine unexplained RECORD mismatches, including six Windows EXEs differing from the SHA256-verified publisher wheel. It was preserved unchanged; those EXEs were not executed. The fresh clean environment passes the original 156-test suite (69.080s, zero skips); follow-up tests cover validator-command absence and real validation failure. This evidence does not certify dependency provenance universally or replace a cross-platform dependency lock.

The tracked-file high-signal private-key/GitHub-token/AWS-key pattern scan found no matches in 275 tracked files. It is a limited scan, not complete secret clearance. The candidate SHA matches remote PR/commit and previously verified CI packages; the commit is unsigned and publisher attestation remains absent. Root MIT and dependency license files are inventoried; no rights or professional legal certification is implied.

A Gemini validation bug was found: validate-native.sh invoked an assumed extension validator. It now probes installed command help and reports NOT_TESTED if unsupported; advertised validator failures still fail the script. The current [official command reference](https://geminicli.com/docs/extensions/reference/) lists installation/update/link but no standalone validate command. Actual Gemini runtime testing needs an authorized isolated CLI installation.

Release blockers still include final-head independent review, unresolved source/attestation and rights clearance, Gemini acceptance or an explicitly approved compatibility exclusion, final-head CI/artifact checks and a reviewed merge/publication decision. CodeRabbit's previous rate-limit status is not approval. No issue #15 implementation starts until release qualification and the required fresh bounded phase.

Final follow-up checks: **158 tests, zero skips, 65.248s** in the clean pip-free environment; repository/provider parity and shell syntax PASS. The updated native-provider script passes installed Claude validators and an isolated Codex plugin install; Gemini is explicitly skipped as absent. Independent-review and isolated-Gemini authorizations remain pending. No stable qualification, merge or publication is implied.
