# Gridline 0.8.1 qualification scope

This patch corrects rotated 270-degree door arcs, nonplot room boundaries crossing PDF doorways, supplied-room validation for explicit legacy swings, and a native paper-space scale enum mistake. New room-relative intent is opt-in; reviewed legacy sides are preserved. Source, artifact, signature, CI and delegated owner approval bindings belong to the separate final `release-qualification.json` attachment. This document alone is not publication approval.

## Executed acceptance

- Final runtime regression: **176 tests, zero skips, 107.275 seconds**, clean existing pinned CAD environment; repository and Claude parity checks PASS. Eight invalid explicit-room cases and the native scale regression failed before their fixes.
- AutoCAD Mac 2027 opened the final synthetic fixture and reported **zero AUDIT errors**. Literal layout scale now displays **1 mm = 1 drawing unit**, A3 landscape. A native PDF plot measures the declared 900 mm leaf at 1:100 and omits the nonplot room boundary. The PDF was rendered and visually inspected.
- A disposable native DWG was saved/reopened/AUDITed (zero errors), then a centered door tag's alignment point was edited by +100 mm, saved and exported to DXF. Independent readback matches all eight supported geometry primitives; tag anchor delta and handle identity are retained. An initial insertion-point-only edit was normalized by native centered-text layout; the alignment-aware edit is the measured result. No original drawing/session was edited; original active document restored.
- Fresh Blender 5.2.3 LTS room-entry and house scenes pass independent `.blend`/GLB readback. All 11 native/GLB corruption seeds reject. No claim of an open-door 3D sweep: conceptual doors remain closed slabs with intent in scene metadata.
- Claude strict plugin/marketplace validation and isolated Codex plugin manager install PASS. Actual pinned Gemini 0.65.0 validates the source in an isolated home. Final-source lifecycle/rollback and live publication evidence are retained in the external qualification directory and final release attachment.

[Native acceptance](evidence/release-0.8.1/native-acceptance.json), [native PDF measurements](evidence/release-0.8.1/native-pdf-measurement.json), [native plot](evidence/release-0.8.1/native-plot.pdf), [plot raster](evidence/release-0.8.1/review-native-plot-1.png), [runtime test hashes](evidence/release-0.8.1/validation.json).

## Honest compatibility limits

AutoCAD substitutes missing unused setup fonts; native superscript glyph rendering differs. Its native PDF contains a duplicate `/PageMode` dictionary key, so independent native measurements used a permissive parser; the generated-PDF verifier remains strict. These observations are not generic external-PDF or universal native DWG acceptance. One synthetic native roundtrip does not close all #16 criteria. Existing-project transactional editing remains #15, semantic IFC/IDS remains #11/#13, and general topology remains #32. Those issues stay OPEN.

## Standards and professional scope

Inward room-entry swing remains a user preference, subject to applicable fire/egress/accessibility review. Fresh primary-source triage identified the [national open-data KDP 400/2020 record](https://www.data.gov.cy/index.php/el/resource/kanonismoi-pyroprostasias) and read the [ETEK May 2024 guide](https://www.etek.org.cy/uploads/2024/news/eb72fb8066.pdf), pp. 1–2. The guide identifies the 2020 commencement but explicitly excludes subsequent amendments and does not replace the regulation. Direct gazette retrieval was unavailable in the initial browser attempt. Current consolidated adoption and project-specific applicability remain UNKNOWN; no numeric predicate or universal inward requirement is activated.

All 15 book coverage/access limits remain in the [book map](POST_RELEASE_BOOK_COVERAGE_2026-10-25.md); B14 remains unresolved and no full paid text was read. No release receipt certifies a real project's architectural or regulatory adequacy. Professional project approval is outside this source/guidance release's compatibility claim and remains required before issue/construction.

## Review and authority

One coding agent performed bounded Python/security/architecture/Ponytail review with the connected schema, callers, schedules, 3D compiler, provider copies and tests. CodeRabbit's review of d9dafa4 found the explicit-room early-return bug; the fix and adversarial regression are included. No independent human professional approval or final-head CodeRabbit approval is inferred. The owner's explicit instruction to finalize and ship authorizes merge/publication and an agent-posted exact owner-account release statement under delegation, as allowed by RELEASE_ARTIFACTS.md. The delegation is not independent human review.

Keep #43 OPEN/PARTIAL for its project-professional acceptance criterion even after the code repairs merge. Publish only after final-source CI, candidate integrity, publisher attestations, scoped provider/native evidence, license/secret inventory and exact delegated approval are verified. Preserve historical tags and all worktrees.
