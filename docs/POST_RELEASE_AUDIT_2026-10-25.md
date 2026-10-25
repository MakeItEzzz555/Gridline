# Bounded post-release audit — 2026-10-25

**PARTIAL; release decision: NO-GO for a new stable build.** The drawing patch is reviewable; fresh native acceptance and release qualification are absent. Original main, every existing worktree, dirty checkpoints and native sessions were preserved. One coding agent, bounded self-review, no Musk-5, installations, native project writes, inference or benchmark trials.

## Baseline and scope

Remote main/latest release reconfirmed as v0.8.0, source `f521969934758ac5625239ea65229190a5a6114e`, tree `9e3d1739db667c7f0e4a364fd9271f1081e40575`. Original checkout remains `a1c7797e151edde8cf6e8d76807da901de708bf2`. Patch branch: `fix/post-release-door-audit-20261025`, isolated `/tmp/gridline-post-release-audit-20261025`. No PR #37–#42 reimplementation or issue #15 transaction engine.

Read the verified execution handoff/final receipt, post-release plan, original books dossier, master implementation plan, research/rules/release masterplan, AGENTS, ROADMAP and open issue criteria. Historical proposals were assessed against current implementation rather than treated as completed requirements. Relevant skills: Headroom, Agent Reach/GitHub CLI, Python, QA, security, Gridline drawing/regulation research, Apple Design and Ponytail. Prompt Master was scope-checked (no prompt rewrite requested). This is geometric drawing work, not web/native UI implementation: no generated UI concepts, browser dependency or aesthetic redesign. Apple guidance applies to predictable spatial mapping, legibility and user control; no gesture/motion/transparency surface changed.

## Claim/evidence ledger

All source links below refer to files in this branch, whose baseline is the source above. Final reviewed source SHA and exact-head CI belong in the PR/final external handoff; do not treat a working-tree artifact as a signed release.

| Claim / source | Evidence and counterexample | Status / priority / fix |
| --- | --- | --- |
| Correct single-door arcs: `aec_cad.py:draw_plan` | Released example rotated 15° gives D02 a 270° arc; standalone directed wall at 105° reproduces. Exact floating-point comparison of angle difference to 90 is unsafe. Baseline readback rejects it. | FAIL at baseline, fixed by hinge/side orientation signs. Regression + visual artifacts PASS; P1. |
| Room-relative intent: schema, `building_spec.py:door_opens`, CAD/schedules/readback/Blender compiler | Old schema accepts only wall-relative sides, cannot bind served room. New opt-in `into_room` + explicit `receiving_room`, both hinges and wall reversal/rotation verified using an independent rectangular-room oracle. Legacy sides preserved. | Baseline capability gap; patch PASS for supported mode. Sampled room-sector diagnostics are not complete collision analysis; P1 design correctness. |
| Clean opening plotting: `aec_cad.py:write_pdf` | `plot=false` room polygons were nevertheless rendered, drawing a line across the opening. New negative vector test fails before fix and retains the leaf after fix. | Baseline FAIL; nonplot layer visibility now honored by render context. PDF verifier excludes nonplot requirements; DXF polygons retained. P1. |
| Native 3D door correctness: `blender_native.py:compile_scene`, worker, topology | Closed slab preview does not implement a swing. Compiler retains intent metadata but no new native scene was authored. Blender doctor reports 5.2.3 LTS, CLI_VERIFIED, model readback NOT_TESTED. | PARTIAL. No 3D swing acceptance or new topology claim. Do not remove structural headers to erase a top-down edge. |
| Independent geometry: `aec_readback.py:plan_requirements`, `tests/test_door_intent.py` | Generator and readback share input intent resolution; agreement alone is insufficient. Separate inverse-rotation rectangular-room oracle checks arc sector, hinge face, radius and leaf alignment. PDF negative oracle checks the declared room edge independently. | PASS for bounded fixture geometry; arbitrary polygon/physical collision correctness PARTIAL. |
| Books and rules: bibliography/ledger, registry/selector | Fifteen installed review paragraphs and 45 claims exist; exact technical pages generally absent. B14 publisher ISBN unresolved. Static selector is metadata triage, not local-law activation. | PARTIAL. [All-15 coverage/gaps](POST_RELEASE_BOOK_COVERAGE_2026-10-25.md). No book was fully read; no numeric code rule added. |
| Qualification: `scripts/qualify-release.py:gate_evidence` | Separate gate paths, gate name/status/tree and scope enforced. A maintainer can still write a fabricated or stale-content PASS bound to the current tree. These are explicitly trusted maintainer assertions, not proof of underlying work. | PASS for documented trust boundary; independent human/professional review NOT_RUN for this patch. No authenticity claim for local assertions. |
| Live provenance: `live_ci`, `qualification`, `build-release.py:verify` | Qualifier binds exact source/tree, immutable candidate hashes, GitHub Actions app/check names, publisher workflow/main/SHA attestation policy and an owner comment binding source/manifest/evidence. Maintainer control of workflows and approval account remains trusted. | Baseline receipt exists; all nine retained public-download assets rehashed MATCH. New-source CI/signature/approval NOT_RUN until separately recorded. |
| Owner independence: final release handoff/receipt | Prior owner-account comment was posted by an assistant under delegated ship authority; it was disclosed and was not a separate human review. Qualifier validates account/content, not the human behind it. | PASS for disclosure, independence NOT_ESTABLISHED. A new qualification cannot reuse the old approval. |
| Installer/update/distribution: build/qualification and existing tests | User-trusted symlinked parent homes remain documented P2. Archive path/case/symlink protections, candidate tampering, gate identity and update/recovery threat cases are exercised by existing regressions. Local A→B fixtures do not prove public delivery. | Bounded regression PASS if final suite passes; no new remotely exploitable defect demonstrated. Native/provider activation NOT_RUN. No whole-repository security clearance. |
| Provider/license/dependencies | Retained v0.8.0 receipt records isolated CLI lifecycle, artifact/license inventory, public Gemini install and scoped native evidence reuse. CAD deps reused from existing clean environment: ezdxf 1.4.5, matplotlib 3.11.2, pypdf 6.21.2. Source drawings here are original synthetic fixtures. | Prior evidence scope retained; fresh patch provider/native acceptance NOT_RUN. Manager validation is not model activation. Public directory submission still NOT_SUBMITTED. |

## Door scope and migration

Explicit legacy `left|right` remains relative to host-wall start→end. It is never automatically flipped. New ordinary hinged room-entry proposals should name the served room and use `into_room`; ambiguity requires input/review. Explicit sides preserve reviewed exceptions. Association probes use 0.01 mm computational tolerance and near-face probes, not regulatory clearances. Sector samples at declared leaf width detect obvious room-boundary conflicts; concave polygons, obstacles, furniture and other doors still require review. Single-hinged is the only supported door operation; explicit sliding/double operation fails rather than inventing geometry. The simple primitive `aec_draw.py` diagram path has no hosted door semantics and is unchanged.

Door schedules gain intent/receiving/resolved columns only for documents that opt into room association; legacy CSV format remains unchanged. Schema, canonical scripts, portable dependencies and Claude mirrors change together. 3D boxes remain closed slabs, with room/swing metadata in the scene element record and an explicit unverified item. Wall topology and native worker geometry remain unchanged.

The line removed here is the **nonplot room-area boundary in plotted output**, not a structural header, wall cap, threshold or manufacturing joint. DXF keeps those boundaries on their existing nonplot layer, so they can still be visible during model-space editing. Coincident wall-cap/jamb edges are retained and not claimed resolved. General wall junction seams / native overhead representations remain outside this demonstrated PDF fix; historical #28 is not reopened on speculation.

## Cyprus authority check

Checked 2026-10-25: [official building-permission workflow](https://www.gov.cy/bsc/en/licensing-procedures/building-permission/) identifies district permission and project/designer documentation. [Limassol district authority](https://eoalemesos.org.cy/en/building-permits) identifies accessibility Regulation 61HA and fire Regulation 61IA; its [interpretation-guide landing page](https://eoalemesos.org.cy/en/fire-protection-interpretation-guide) does not expose enough clause text in this retrieval to approve a swing. The Ministry's indexed KDP 400/2020 result mentions escape-direction provisions/exceptions, but direct PDF retrieval returned 404; the Ministry sector page returned 403. No current consolidated clause/adoption or project-specific applicability is established. No thresholds from secondary copies or another jurisdiction were activated.

Inward bedroom swing is therefore a **user design preference**, subject to project-specific fire/egress/accessibility review. A competent local professional must resolve any conflict using current applicable sources before issue/construction; no universal inward rule or professional compliance is asserted.

## Artifacts and validation

[Evidence directory](evidence/post-release-door-audit/) contains exact synthetic specs, before/after/room-entry DXFs and PDFs, model-space SVG/PNG crops and SHA256 inventory. [Before](evidence/post-release-door-audit/before-door.png) shows 270° and the room line; [after](evidence/post-release-door-audit/after-door.png) shows 90° with the nonplot room line omitted; [room intent](evidence/post-release-door-audit/room-entry-door.png) opens toward the declared bedroom. Crops intentionally exclude some annotation; full sheet PDF also inspected using actual PDF rasterization (`sips`), not generated concept art. This is visual rendering evidence, not native CAD acceptance.

Regression commands use the existing clean environment via `PATH=/tmp/gridline-rc-reviewfix-venv-20261025/bin:$PATH GRIDLINE_REQUIRE_CAD_TESTS=1`. Before-fix logs: `/tmp/gridline-door-before.log` (49 matrix/arc subcase failures) and `/tmp/gridline-door-nonplot-before.log` (one negative plotting failure). Targeted `python3 -m unittest discover -s tests -p test_door_intent.py -v` passes six tests, including 48 geometric subcases, malformed/ambiguous room cases, coordinated build/check and schedule tampering. Baseline rotated output check fails with four ARC errors; corrected output and new-room output pass supported 2D checks with the expected unchecked-professional warning.

Full regression: **174 tests, zero skips, 75.705 seconds, PASS**; repository/provider checks PASS. [Machine validation record](evidence/post-release-door-audit/validation.json) records commands, environment and tested file hashes. Bounded self-review SHA and remote checks are recorded in the final PR/handoff. A local supported-2D PASS does not certify architectural correctness, arbitrary clearances, native interoperability or release readiness.

## Issue reconciliation and release gates

New issue [#43](https://github.com/MakeItEzzz555/Gridline/issues/43) owns these demonstrated drawing defects and remains OPEN/PARTIAL until merged and acceptance is complete. Existing #10/#11/#12/#13/#14/#15/#16/#32/#36 remain OPEN; no original acceptance contract is satisfied in full by this patch. #16 native roundtrip and #13 semantic BIM remain explicit dependencies; #15 proposal/approval boundaries and #33 independent geometry work are preserved. #36 broad docstring coverage is not fixed by these focused docstrings.

| New-source gate | Decision / dependency |
| --- | --- |
| Targeted deterministic drawing tests / visual outputs | PASS within the scope above |
| Repository/provider parity / full regression | Record exact final result in PR/handoff |
| Bounded Ponytail self-review | One pass; no independent architectural or CodeRabbit approval implied |
| Reviewed branch / exact-head Linux and Windows CI / remote SHA / merge conflict state | Record exact final head in PR/handoff |
| Fresh native CAD / 3D acceptance | NOT_RUN. Preserve sessions and #15/#16 authorization boundary; closed 3D metadata is not a swing test |
| Adopted local clause / professional design acceptance | NOT_RUN; source/adoption/applicability remains unresolved |
| New stable candidate, SBOM, SHA256SUMS, signed attestation, real provider lifecycle | NOT_RUN for a new version; v0.8.0 receipts are source-bound and cannot qualify this patch |
| Separate owner-bound new-candidate approval / merge | NOT_RUN; no historical delegated approval reused |
| Publication | NO-GO; no release, tag rewrite, merge or directory submission performed |

The proposed next release is **0.8.1** for backward-compatible opt-in intent and rendering corrections, subject to actual reviewed scope and current remote versions at release time. Existing manifest versions remain synchronized at 0.8.0 with an Unreleased changelog; no unqualified build is advertised as 0.8.1. Build/sign/approve only from exact accepted source after required gates pass.

Usage: provider token/cache/cost receipts unavailable; no attributable savings claimed. Headroom was used on large source context (retrieval hash `bfd040986c363f9f38088873`); exact edited sources were read locally. Its configured proxy was unreachable, so no automatic traffic compression is claimed.

## Source navigation for review

Baseline/review scope as above; these exact working-source files are SHA256-bound in `validation.json`.

| File | Relevant definition line |
| --- | --- |
| [skills/architectural-drawing-generation/scripts/building_spec.py](../skills/architectural-drawing-generation/scripts/building_spec.py) | 12 (`shape_errors`), 97 (`door_opens`) |
| [skills/architectural-drawing-generation/scripts/aec_cad.py](../skills/architectural-drawing-generation/scripts/aec_cad.py) | 296 (`draw_plan`), 484 (`write_pdf`), 526 (`build`), 620 (`check_outputs`) |
| [skills/architectural-drawing-generation/scripts/aec_readback.py](../skills/architectural-drawing-generation/scripts/aec_readback.py) | 19 (`plan_requirements`), 140 (`pdf_check`) |
| [skills/architectural-drawing-generation/scripts/blender_native.py](../skills/architectural-drawing-generation/scripts/blender_native.py) | 40 (`compile_scene`) |
| [skills/architectural-drawing-generation/references/building-spec.v1.schema.json](../skills/architectural-drawing-generation/references/building-spec.v1.schema.json) | 1; complete schema/regression fixture |
| [tests/test_door_intent.py](../tests/test_door_intent.py) | 1; complete schema/regression fixture |
| [tests/test_drawing_verification.py](../tests/test_drawing_verification.py) | 1; complete schema/regression fixture |
