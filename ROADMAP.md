# Roadmap

The project evolves incrementally around usefulness, portability, safety, and measured context cost.

## Direction

First users: small practices and independent architects, Cyprus and the wider EU first, with standards that stay configurable for anywhere. The principle: **one source of truth, deliverables derived from it, a checker before anything is presented, and a named architect who signs.**

## Community-driven priority update (2026-10-22)

See [next AEC phases and official integration research](docs/NEXT_AEC_PHASES.md).

**Community feedback follow-up (2026-10-22):** **P0 [authoritative model state and agent transaction safety](https://github.com/MakeItEzzz555/Gridline/issues/15)** is a blocking prerequisite for *all* future agent-authorized native CAD/BIM writes. The local signed-component ledger now verifies the latest approved head transition even when a restore reuses a previous content hash; full host transaction/readback, external anti-rollback, generalized project state and professional approvals remain open. **P1 [actual AutoCAD DXF/WG round-trip acceptance](https://github.com/MakeItEzzz555/Gridline/issues/16)** is a separate deliverable from ezdxf syntactic validation: run native AUDIT, editing, plots, scale/XREF checks and DWG readback on a licensed host. These are not shipped capabilities. Supporting documentation: [state and AutoCAD research](docs/NEXT_AEC_PHASES.md#additional-community-feedback-state-safety-and-native-dxf-readback).

**MCP read safety (2026-10-29):** descriptor-relative no-follow project JSON snapshots now prevent ancestor/leaf symlink swap escapes and enforce post-stat read bounds on supported POSIX hosts. The Windows/pathname compatibility fallback is not race-proof; secure Windows handle-based confinement remains open. Neither path is an immutable multi-file transaction snapshot.

1. **Cross-sheet dependency/impact review (Phase 1):** in progress. Read-only spec revision impact follows indexed host/level relationships, catches grid and document-setting changes, conservatively flags all indexed sheets for those changes and dependent schedules where applicable, and explicitly labels partial coverage; opt-in Gridline local read-only MCP server. Unknown top-level document fields also conservatively flag all indexed sheets, preventing silent false negatives as the building spec evolves; their schedule dependencies still require manual review. Missing model host/level/receiving-room references now flag review even for identical inputs; room changes follow declared receiving-room door dependencies, but geometric room-wall adjacency remains unindexed. Next: actual drawing/PDF cross-reference extraction, room-wall adjacency modeling, and real 40-sheet case fixtures.
2. **IFC 4.3 / IFC4 / IFC2X3 schema and IDS gate (Phase 2):** local IfcOpenShell, IfcTester and buildingSMART-style validation; fail-closed release controls, geometry and project standards tested separately.
3. **Native AEC MCP integrations (Phase 3):** official Autodesk Revit 2027.2 local MCP (read first); Autodesk Assistant's AutoCAD/Civil3D preview (respect actual host/client restrictions); Rhino.Compute, Graphisoft JSON API, Blender bpy and FreeCAD local APIs through bounded adapters.
4. **Editable 2D → coherent 3D → IFC (Phase 4):** source-of-truth dimensions, topology checks, native geometry, GUID tracking, roundtrip verification; render/mesh preview is not certified BIM.
5. **Scanned annotated floor plans (Phase 5):** calibration, confidence, annotation/OCR separation, human review, adversarial tests. No one-shot scan-to-BIM claims.

Other P1 agent routing/reviewer evaluations and standards-profile improvements remain planned; they are not replaced by visual demos.

## Next, in order

**Evaluation infrastructure completed (unreleased):** offline scoring of recorded provider activations, provenance and baseline regression gates. Real provider-native observation capture and repeated-run behavioral benchmarks remain open.
1. **Agent reliability (P1).** Read-only reviewer agents; baseline activation and negative-trigger evals on the existing cases; more negative cases.
2. **Audit existing drawings.** Run the standards checks (layers, ByLayer properties, text heights, title blocks, sheet register) on a practice's *own* DXF files, not only generated ones. Most offices already have drawings; checking them is immediate value.
3. **Sections and elevations from the same spec.** Levels, wall heights, sills and opening heights are already in the spec; derive elevations and a simple section, plus door/window type legends and a finishes schedule.
4. **Live AutoCAD loop.** A recipe for autocad-mcp (AutoCAD LT 2024+ on Windows): open the generated DXF, read back entity counts per layer, plot to PDF, and compare against `check`.
5. **IFC from the same spec.** Walls, openings and spaces through IfcOpenShell for Revit/Archicad import and IDS checks.
6. **Revisions and issue.** Revision table and clouds, register history per revision, transmittals.
7. **Cyprus/EU reference pack.** Planning and building-control sources as data with authority, edition, effective date and limitations; no rule is applied without its citation.
8. **Quality benchmark.** The same tasks with and without the pack across providers: drawing validity, coordination errors, unsupported assumptions, human corrections.

## Done
- [x] Full lifecycle skill coverage from briefing/site feasibility through construction administration, handover and post-occupancy.
- [x] Coordinated CAD pipeline: one spec -> standard-layered DXF sheets, PDFs, schedules, sheet register, and an independent checker (0.6.0).
- [x] ISO 13567 and US NCS standards profiles with office overrides (0.6.0).
- [x] Self-contained skills on every install path; ownership-safe, rollback-safe installers (0.5.1).
- [x] Conceptual SVG/DXF drawing fallback with schema and tests.
- [x] Revit, Rhino/Grasshopper, AutoCAD/DWG and IFC/BCF/IDS workflow skills.
- [x] Provider-neutral activation fixtures and structural coverage tests.

## Later
- Optional MCP connectors for BIM/model metadata and approved regulation sources.
- A2A/remote architecture specialists where providers support them.
- Curated country/city regulation packs kept separate from universal skills.
- Optional local computer-vision helpers for drawing comparison.
- End-to-end example project workflows.

## Non-goals
- Pretending AI output is professional certification.
- Hard-coding one country's rules into universal skills.
- Huge permanent system prompts.
- Silent destructive editing of production BIM/CAD files.
