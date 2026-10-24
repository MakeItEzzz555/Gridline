# ProjectBrief and SourceDetailLedger v1

Related issue #15 (partial foundation only). The dependency-free intake CLI asks geometric questions before styling, and never launches a native application or writes a model.

```sh
python3 skills/architectural-drawing-generation/scripts/project_brief.py \
  skills/architectural-drawing-generation/references/incomplete-villa.brief.json
```

The supplied example has **metric/mm CONFIRMED**, **plot boundary UNKNOWN**, **floor-to-floor heights UNKNOWN**, **roof UNDECIDED/UNKNOWN**. EXACT_3D returns NEEDS_INPUT (exit 1) with those three prioritized questions. CONCEPT returns READY_CONCEPT_ONLY with visible blockers and provisional=true; it does not supply missing values. CONFLICT blocks both modes. BIM_DELIVERY additionally requires unimplemented IFC/schema/IDS/semantic/host acceptance and cannot become READY from intake alone. Invalid input exits 2.

## Work-package scope

Starts independently from main `0a2e9aefa204b90b685556d1fb0c714f719d371b`, without depending on unmerged Blender PR #23. Scope: typed runtime validation, versioned records, exact-record approval hash, prioritized questions, example fixture, existing-spec translation check, portable provider parity and adverse tests. No model editor, image interpreter, approval service, persistent transaction/event store, IFC exporter, native writes or web UI. The gate is advisory until a later authoring caller explicitly integrates it; existing 2D CLI behavior remains unchanged.

## Contract

ProjectBrief `schema=gridline-project-brief.v1`, `mode=CONCEPT|EXACT_3D|BIM_DELIVERY` embeds a separately versioned `ledger` with `schema=gridline-source-detail-ledger.v1`, positive revision and up to 1000 records. See the executable fixture for complete field names.

Every record preserves key, literal source text, value, unit, source kind/location (pixel region for images), confidence, revision, evidence, target element IDs, status and disposition. Status is CONFIRMED / PROPOSED / UNKNOWN / CONFLICT / BLOCKED. Disposition is MAPPED / OUT_OF_SCOPE / UNKNOWN / BLOCKED. MAPPED requires targets; all other dispositions require a reason. Explicit OUT_OF_SCOPE is visible in coverage and never satisfies a mandatory geometric prerequisite. Every supplied record appears in coverage; unapproved or unresolved in-scope records block exact intake.

CONFIRMED requires evidence plus `approval.by` and `approval.record_sha256`. The hash is SHA-256 of canonical sorted compact JSON for the **entire record excluding approval** (`approval_hash`). Editing value, units, source, targets or revision invalidates the approval. This is change detection, **not authentication**: anyone editing the JSON can recompute the hash or impersonate the approver. This module does not authorize native writes, overwrite records, implement human approval history or replace issue #15's future durable transaction manager. Store prior approved inputs immutably and obtain actual human acceptance outside this CLI.

Required exact inputs: explicit mm/m project unit, measured simple nondegenerate plot polygon (3–128 vertices, no duplicate closing vertex), positive floor-to-floor heights with units, and an approved roof type with a dimensioned geometry source. Survey legality, roof source contents, spatial alignment, floor datum and jurisdiction are not certified by the presence of a string. READY means these **intake checks** passed; no model completeness or native acceptance follows from it.

When an image record is supplied, reference_scale in mm/pixel and the full detail category inventory become required: openings, facade profiles, roof/parapet, storeys, balconies, railings, frames/mullions, finishes, color/roughness, edges, stairs, landscape, lighting, camera and occluded geometry. The CLI cannot determine whether a real image has been fully inventoried; operators must supply actual image observations. Single-view unknown scale/perspective/occlusion/reverse-side geometry must stay UNKNOWN/BLOCKED. OUT_OF_SCOPE requires an explicit reason and confirmed scope decision. No image files are loaded or uploaded; source locations are inert data. Missing images are not replaced with the sample house.

`to_building_spec(brief, building)` validates an **existing** building-spec.v1 dictionary and checks its mm level heights against approved floor-to-floor heights (m converted explicitly to mm). It deep-copies the source, generates no geometry and adds no defaults. It does not translate roof/site/reference detail into geometry, and the output remains subject to the existing CAD/Blender geometry checks and separate host receipts. This preserves the 2D contract instead of silently extending its semantics.

## Validation and limits

Ten deterministic tests cover exact example, provisional concept, conflict, duplicate keys, missing units, stale approvals, impossible height values, degenerate/crossing plot boundaries, confirmed-but-blocked records, single unscaled image inventory, BIM gates and source-spec height mismatch. Targeted tests precede the pinned CAD-required regression suite. Provider copies remain byte-identical. Independent read-only review found and prompted fixes for blocked dispositions and degenerate boundaries. No actual source-reference fidelity or professional review is claimed.
