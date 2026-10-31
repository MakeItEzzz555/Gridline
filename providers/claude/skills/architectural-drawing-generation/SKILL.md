---
name: architectural-drawing-generation
description: Create and coordinate architectural drawings and vector deliverables including site plans, floor plans, roof plans, reflected ceiling plans, elevations, sections, details, diagrams, legends and schematic blueprints. Use when the user asks to draw, draft, generate a plan/section/elevation/detail, or turn structured geometry into SVG/DXF/CAD output.
---

# Architectural Drawing Generation

Produce drawings an architect could put in front of a client or consultant: one source of truth, office-standard layers, correct scale and sheet, and a passing check before anything is presented. Apply every default below without being asked.

## Choose the path

1. **Native host connected** (AutoCAD, Revit, Archicad, Rhino through a trusted MCP or add-in): inspect the open document and version first. For AutoCAD, prefer generating the DXF with the pipeline below and opening or inserting it (`OPEN`, `INSERT`, `XREF`) over drawing entity by entity through the bridge: the file is reviewable, checkable and undoable as one step.
2. **No host**: use the bundled coordinated pipeline, `scripts/aec_cad.py` (needs `pip install ezdxf==1.4.5 matplotlib==3.11.2 pypdf==6.21.2` for generation and verification).
3. **Diagram only, or ezdxf unavailable**: `scripts/aec_draw.py` renders simple SVG/DXF from six primitives. Say it is a diagram, not a drawing set.

Paths are relative to this SKILL.md's directory.

## Coordinated pipeline (`scripts/aec_cad.py`)

Write one building spec, then derive everything from it. Never hand-edit an output; change the spec and rebuild.

```bash
python3 scripts/aec_cad.py build SPEC.json OUT/ [--standard iso13567|ncs|office.json]
python3 scripts/aec_cad.py check SPEC.json OUT/ [--standard ...]
```

- Spec format: `references/building-spec.v1.schema.json` and `references/example-house.building.json` (levels, grids, walls with thickness, openings hosted on walls by offset, rooms as inside-face polygons, sheets, project/title data). Explicit `units: "mm"`, finite numeric geometry, named levels with elevation/positive height, and window sills are required. Openings must fit horizontally and vertically. Legacy specs may omit `schema_version`; new specs should set `"schema_version": "building-spec.v1"`.
- `build` writes, per sheet, a DXF with the plan in model space at 1:1 and a paper-space layout (frame with ISO 5457 margins, a title block within ISO 7200's 180 mm width with attributes, status stamp, scale bar, north arrow, a locked viewport at the sheet scale), a vector PDF, and `room-schedule.csv`, `door-schedule.csv`, `window-schedule.csv`, `sheet-register.csv`.
- `check` independently measures supported wall outlines, opening jamb/frame/leaf/swing primitives and room boundaries against the spec, including multiplicity. Missing, moved, resized, rotated or duplicated critical primitives fail even if tags/CSVs match. New geometry carries `GRIDLINE` XDATA; legacy geometry is matched by position and reported as inferred identity. Handles/XDATA do not prove native roundtrip identity.
- PDF rendering honors nonplot layer settings; room boundaries remain in the DXF for area/editing/readback but are omitted from plotted output. PDF checks measure only plotted layers.
- PDF checks require pypdf: one page at the stated size, document identity where present, and independently measured straight plan segments at the intended plot mapping/scale. Missing PDFs or validators fail. Raster visibility, clipping, fonts, door-arc plotting, text collisions, grid/dimension/hatch geometry, topology, 3D and native hosts remain explicitly unverified.
- Standards/title/tag/schedule checks still run, including the register date. `check-report.json` and append-only `receipts/<id>.json` bind exact consumed spec/profile/output bytes, validator file/dependency hashes/versions and source Git SHA (or `UNKNOWN` after standalone installation). Inspect `coverage` and `unverified_items`; a local PASS covers supported 2D checks only.
- **Run `check` before presenting a drawing and report its scope and warnings.** Also visually review the PDF and obtain the appropriate professional review. Build each revision in a fresh output directory: atomic publication is a separate pending gate.

## Room-entry door intent

For new ordinary single-hinged room-entry doors, prefer `"opens": "into_room"` with an explicit `receiving_room` ID and `hinge: start|end` along the directed host wall. Ask for the served room when ambiguous; never infer it from a global left/right or room name. This is a user design preference, not a universal code rule. Fire/egress/accessibility conflicts need project-specific adopted sources and professional review before choosing the swing.

Legacy `left|right` remains relative to the directed wall and is preserved, including reviewed outward exceptions. If `receiving_room` is supplied, its existence, host level and adjacency are validated without forcing the explicit swing inward. Migrate only with explicit design review; existing example-house geometry is unchanged. New room intent validates near-face adjacency and samples the swing sector against the room polygon; this catches obvious room-boundary conflicts but does not establish obstacle, furniture, other-door or statutory clearance compliance. Concave polygons need visual/professional review. Door schedules for associated-room documents additionally record intent, receiving room and resolved wall side. Sliding/double doors are not supported by this pipeline; an explicit unsupported `operation` fails rather than being drawn as single-hinged. The Blender preview retains closed slabs and records intent as metadata; it does not show or verify an open 3D swing.

## Standards

- These profiles follow the published structure of each standard as far as public sources allow; they are not certified implementations. Say "layered to the ISO 13567 profile", never "ISO 13567 compliant", unless the office has checked the profile against the standard text.
- Default to the project's office standard. Without one, use `iso13567` in Europe and most of the world and `ncs` in the US, and tell the user which you used.
- Profiles live in `references/standards/`. An office profile is a JSON file with `"extends": "iso13567"` (or `"ncs"`) that overrides only what differs, such as layer names, text sizes or statuses. Read the profile's `notes` before relying on its layer codes.

## Drafting defaults (always)

- **Source of truth:** every dimension comes from the brief, survey or model. A missing value is `UNKNOWN` and a question for the user; never a guess. Units, datum and north are stated.
- **Detail completeness:** inventory every supplied requirement and every interpretable image, maquette or top-down drawing detail with source, element ID, dimensions, confidence, implementation and verification state. Resolve conflicts and absent scale/hidden geometry with the user. Unsupported details stay `UNKNOWN`/`BLOCKED`; a plausible render or local plan PASS cannot establish that nothing is missing. Never discard such details merely because this generator cannot represent them.
- **Line hierarchy (weights from the ISO 128 series):** cut walls are heaviest (0.50 external, 0.35 internal) with solid poché; openings 0.25; dimensions and grids 0.18; the sheet frame 0.70. Everything is ByLayer.
- **Text (heights from the ISO 3098 series):** nothing plots below 2.5 mm, the profile minimum (ISO 3098 also allows 1.8 mm; offices can change it). Notes and tags 2.5, room names 3.5, grid bubbles and titles 5, sheet titles 7. Model-space text height = plotted height × scale.
- **Plans:** doors show leaf and swing, windows show frame and glass, every opening is tagged and appears in its schedule, every room shows name and area. Exterior dimensions run as two chains (openings, then overall) outside the building, with text reading from the bottom or right. Grid lines run past the dimensions with bubbles at both ends.
- **Sheets:** standard scales only (1:20, 1:50, 1:100, 1:200…), standard paper sizes, sheet numbers to the office pattern (`A-101`), the title block fully filled, a scale bar and north arrow. If the plan does not fit, change the scale or the sheet, never the drawing.
- **Status:** anything not formally issued carries a `NOT FOR CONSTRUCTION` stamp. `FOR CONSTRUCTION` and `AS BUILT` require a named checker, and the pipeline refuses them without one.
- **Review the output visually** (render the PDF to an image) for collisions between text, tags, dimensions and grids before presenting it; the checker cannot see overlaps.

## Scope today

The pipeline draws plans: walls, doors, windows, rooms, grids, dimensions, sheets and schedules. Sections, elevations, details, stair/furniture plan symbols, ceilings and site plans are not generated by this 2D pipeline. The separate optional component adapter below generates bounded 3D visual props. Produce those in a native host, or describe exactly what is needed, rather than faking them with primitives.

## Optional installed Blender 3D preview (experimental)

The bundled `scripts/blender_native.py` may generate a NEW Blender `.blend` plus `.glb` from supported typed walls/levels and hosted door/window openings when Blender is already installed and the user authorizes a new output directory. First run `python3 scripts/blender_native.py doctor`, then `python3 scripts/blender_native.py build SPEC.json NEW_OUT` from this skill directory; both the worker and shared `building_spec.py` validator ship with this skill. The worker does NOT control an existing Blender window, install a Blender MCP, render from photos, generate semantic IFC, or issue drawing approval. Native source and GLB must independently reopen, and missing roof/levels/material detail must be presented as unsupported—not invented from a reference image. See repository `docs/BLENDER_NATIVE_BRIDGE.md` where available.

## Verification and boundaries

For optional ARCHIMESH source discovery, use `python3 scripts/archimesh_doctor.py`;
exit 0 means inventory completion, not geometry acceptance or licensing clearance.
An explicit, hash-approved official 1.2.5 source can be used with
`python3 scripts/archimesh_components.py catalog|validate|build|verify`. The component
adapter is qualified only on Blender 5.2.3 and POSIX new-output publication. Pick a
bounded kind from the catalog and obtain **all** dimensions, position, orientation
and materials from reviewed source data. See `references/example-components.json`
for synthetic fixtures and `references/example-house.components.json` for exact
canonical opening bindings. Do not copy fixture dimensions into a real design.
Build requires `--addon-source` and `--approve-addon-sha256`; it uses disposable
factory/background processes and never installs/enables an add-on in a user profile.
Frozen meshes, hierarchy, identity, UV/normals, source anchors and native/GLB
readback are checked; parametric panels, rooms, host cuts and live edits remain
unsupported. Retain the separately reported receipt hash for later `verify
--expected-receipt-sha256 PIN`. No original model is overwritten.

`component_state.py` supplies a version3 signed canonical source-proposal ledger for components, levels, walls, openings and rooms;
OpenSSL verifies detached Ed25519 owner signatures. Never accept an owner label as
approval or sign on the owner's behalf. `build --state-db DB --owner-key-sha256 PIN`
requires the selected committed head. Typed replacements preserve identities, host/level references and required attributes; revalidate geometry; flag indexed drawing/schedule impacts; and check every signed transition before trusting a revision. Unindexed dependencies and Revit/AutoCAD live transaction/rollback acceptance remain gated by #15.

`cc0_assets.py` provides an explicitly enabled Poly Haven texture catalog and
bounded three-channel 1K JPG cache. Never download without network consent and the
exact approved plan hash. Builds consume local verified cache bytes only; explicit
physical UV tile sizes are required. Preserve provider/CC0/source/hash provenance;
synthetic fixture acceptance is distinct from real downloaded asset acceptance.
`component_ifc.py` exports and independently checks bounded source-bound IFC4 on IfcOpenShell 0.9.0.post1 with pytest for EXPRESS validation; explicit requirements and `--state-db`, trusted source receipt/owner key pins are mandatory. It verifies spatial structure, rooms, source IDs, units/materials/quantities, raw/evaluated geometry and host/void/filling relationships. `--verify --expected-ifc-receipt-sha256 PIN` reopens immutable snapshots without rewriting published artifacts. This is not client IDS/MVD interoperability or professional/regulatory acceptance; do not claim full BIM compliance. Detailed repository usage/gates are in
`docs/ARCHIMESH_INTEGRATION.md`. The new API worker is GPL-2.0-or-later; read
`references/BLENDER-LICENSING.md`. Other MIT grants remain preserved.

- Report the files produced, the standard used, the `check` result and the warnings, and every assumption you made.
- A generated drawing is a drafted proposal. It needs review by a qualified architect before it is issued, permitted or built from.
- For file or model changes in a native host, compare the result against a pre-change baseline and report changed, skipped and failed items. Never claim the host changed something unless it confirms it.


## Read-only client revision impact (pilot)

For changes to windows, walls, rooms, levels, grids, project units, drafting standards or sheet revisions,
compare explicit before/after project JSONs using:
`python3 scripts/revision_impact.py before.building.json after.building.json --out impact.json`

The report enumerates changed IDs, `changed_document_fields` (units, standard, schema_version and unclassified top-level site/datum/material fields), schedules and **indexed** drawings requiring review. Unclassified document-field changes conservatively flag every indexed sheet, but their schedule dependencies remain a manual-review gap. Grid changes and document-setting changes conservatively flag every indexed sheet because there is no per-sheet grid/style dependency index; unit changes also flag dimensional schedules. Other edits follow declared host/level, receiving-room door and sheet-reference links. The additive `stale_model_references` field flags missing wall/room levels, missing opening hosts, and missing or cross-level receiving rooms in either revision. These unresolved links require review of all indexed sheets and dimensional schedules, even when both input files are identical; no replacement geometry or IDs are inferred.
Sections, elevations, unindexed PDFs and hand markups remain UNKNOWN unless
explicitly linked using each sheet's `references` mapping (openings/walls/rooms/levels).
Do not claim a visual/DWG/BIM content comparison from this result alone.

For MCP-compatible agents, an optional local read-only stdio server lives at
`scripts/gridline_mcp.py`. It requires the official Python MCP SDK v2 and an
explicit `GRIDLINE_MCP_PROJECT_ROOT` directory. It exposes only revision-impact
comparison and capabilities; it does not modify drawings or connect to Autodesk. On supported POSIX hosts it reads bounded JSON snapshots from no-follow, descriptor-relative handles; on Windows and other hosts without those primitives, the compatible pathname fallback is not race-proof against concurrent directory replacement. Only use a trusted project directory there.
See repository `docs/NEXT_AEC_PHASES.md` for host/vendor adapter gates.

## Source-detail intake gate

Before exact 3D work, `python3 scripts/project_brief.py references/incomplete-villa.brief.json` demonstrates the versioned brief/ledger gate. Use an actual project brief: unknown plot boundary, floor-to-floor heights or roof block exact intake; concept stays explicitly provisional. Records preserve source, approvals and detail coverage. This advisory CLI never authorizes native writes and does not replace geometry/host validation or the future transaction manager.
