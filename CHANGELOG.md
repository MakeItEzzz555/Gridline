# Changelog

## Unreleased — Blender native-scene proof (2026-10-24)

- Add opt-in local Blender headless scene/export bridge for supported building-spec walls, doors and windows, with explicit millimetre-to-metre conversion, new-output-only policy, independent .blend/.glb native readback, input/artifact hashes and known coverage limitations.
- Document that image-reference reconstruction, IFC/BIM semantics, complex detailing and AutoCAD native acceptance are still separate gates; downloadable AutoCAD installer alone is not a verified host.


## Unreleased — recorded skill activation evaluation (2026-10-24)

- Add an offline scorer for real Codex, Claude Code and Gemini CLI activation observations, with per-skill recall, negative-control rates, SHA-256 provenance, baseline comparison and optional per-case regression gates.
- Add 19 deterministic tests; CI discovers them automatically. This validates scoring logic, not live model activation accuracy.

## Unreleased — AutoCAD Mac read inspection

- Add a manual, opt-in AutoLISP inspector, bounded disposable-copy preparation, bundle doctor and evidence receipts; no automatic host writes or security preference changes.
- Fix the native-AUDIT-reproduced overall paper-space viewport layer defect; fresh A-101/A-102 copies pass native no-repair AUDIT. Native edit/plot/DWG roundtrip remains unverified.

## Unreleased — trustworthy local drawing verification

- Preserve failure receipts on CSV parser errors and fail incomplete builds when any required PDF is not generated.

- Require explicit mm units, finite typed geometry, valid level elevation/height and vertically hosted openings; document building-spec.v1 while accepting legacy version omission.
- Independently measure supported DXF wall/opening/room primitives and multiplicity, with optional portable element associations. Detect seeded deletion, movement, resize and duplication even when labels and schedules remain unchanged.
- Require PDF page/vector/scale checks and register-date agreement. Add pinned pypdf to the CAD CI job and reject accidental missing CAD dependencies there.
- Retain byte-bound verification receipts, validator/dependency versions, source revision and explicit unsupported coverage. Preserve existing CLI/report keys and synchronized portable provider copies.
- Native AutoCAD, semantic 3D, complete image/detail reconstruction, atomic output publication and professional acceptance remain separate pending gates.

## Unreleased — source-detail intake gates

- Add versioned ProjectBrief/SourceDetailLedger validation, provenance-bound confirmations, prioritized missing-geometry questions and explicit concept/exact/BIM gates.
- Add an incomplete villa fixture and adverse tests without changing the existing 2D CLI or authorizing model writes.

## Unreleased — community progress documentation (2026-10-23)

- Documented implemented skills, DXF/PDF/schedule generation, read-only revision-impact checks and Gridline's local MCP review tool with direct PR evidence.
- Published an issue-by-issue [community progress ledger](docs/COMMUNITY_PROGRESS_2026-10-23.md). Issues #10–#16 stay open because their complete acceptance criteria have **not** been met.
- Clarified that library-level checks do not prove complete geometric correctness, native AutoCAD compatibility, IFC/IDS validation, or autonomous BIM editing. This entry describes documentation updates, **not shipped verifier repairs**.


## 0.7.0 — Gridline rebrand and installer migration

- Rename the public project, provider plugin identities, documentation and install instructions to **Gridline**.
- Add safe recognition of legacy per-path ownership ledgers for existing global installer users.
- Document native plugin ID migration, Git remote updates and preserved backup history.


## 0.6.0 - 2026-10-22
- Added a coordinated CAD pipeline to `architectural-drawing-generation` (`scripts/aec_cad.py`). One building spec produces, per sheet, a DXF (model-space plan plus a paper-space sheet with a frame using ISO 5457 margins, a title block within ISO 7200's 180 mm width, status stamp, scale bar, north arrow and a locked viewport at scale) and a vector PDF, plus room/door/window schedules and a sheet register.
- Added `aec_cad.py check`, which reads the outputs back and fails on off-standard layers, colour/lineweight overrides, text below 2.5 mm plotted, empty title fields, missing stamps or viewports, and certain drawing tags, room-area annotations, schedule fields or register entries that disagree with the **building specification**. Independent full geometry comparison was not implemented in v0.6.0.
- Added standards profiles (`references/standards/iso13567.json`, `ncs.json`) and office profiles that `extend` them.
- The drawing skill now applies drafting defaults without being asked (line hierarchy, text sizes, tags, dimension chains, grids, sheets, status stamps) and requires a passing check before presenting a drawing.
- Optional dependency: `ezdxf` (and `matplotlib` for PDF). Without them the pipeline exits with an install message and `aec_draw.py` remains available.

## 0.5.1 - 2026-10-21
- Fixed: the conceptual drawing engine, its schema and example now ship inside `skills/architectural-drawing-generation/` (`scripts/`, `references/`). Before, the Claude plugin, `npx skills` and global-installer paths installed the skill without the script it calls. Root `scripts/aec_draw.py`, `schemas/` and `examples/concept-plan.drawing.json` moved there.
- Fixed: provider sync and repository checks compare whole skill folders, not only `SKILL.md`.
- Installers record what they install, refuse to replace same-named skills or agents they did not install unless `--force`/`-Force` is given, check every host before changing any, and move previous versions to a timestamped backup instead of copy-then-delete. If a copy or move fails, that item's previous version is put back and the staged copy removed, so an interrupted upgrade never leaves a skill missing; the ledger records each item as it is replaced. Backup folders include the process ID, so runs in the same second never share one. Updating an install made before 0.5.1 needs `--force` once.
- Tests run the drawing engine from every installed location (including a real `npx skills add --copy` check done for this release) and cover conflict refusal, forced replacement, restore from backup, updates, failures injected while copying or placing an item, and same-second runs.
- `docs/RESEARCH.md` now links its sources; drawing documentation states the six supported primitives.

## 0.5.0 - 2026-10-21
- Expanded the canonical architecture/AEC skill suite from 11 to 30 focused skills covering the full project lifecycle.
- Added site feasibility, precedent research, concept/schematic design, interiors, drawing generation, technical documentation, life safety/accessibility, structural/MEP/civil coordination, envelope/performance, sustainability, materials/specifications, cost/VE, construction administration, handover/FM, visualization, openBIM/IFC and AutoCAD/DWG workflows.
- Added six specialist subagents for drawing production, civil/site, openBIM, building performance, technical documentation and construction administration.
- Added a dependency-free JSON-to-SVG/DXF conceptual drawing engine, schema, example and unit tests.
- Rebuilt the README around beginner-first one-click agent installation, universal Agent Skills installation, native provider paths, lifecycle coverage, tool routing and explicit professional boundaries.
- Added AEC lifecycle, research, tool-integration and drawing-output documentation plus reusable project/drawing/site/RFI/handover templates.
- Expanded activation coverage to every stable skill and strengthened repository/CI checks for drawing assets and unit tests.

## 0.3.0 - 2026-10-11
- Added the provider-neutral `rhino-grasshopper-workflow` skill for Rhino 3D, Grasshopper, RhinoCommon, and Rhino Python work with explicit data-tree, unit/tolerance, bake/export, verification, and rollback guidance.
- Routed Rhino/Grasshopper tasks from `architecture-orchestrator` and added activation regression cases, keeping Revit work under `revit-workflow` and general IFC/DWG/DXF/SVG work under `cad-bim-automation`.
- Marked the Rhino / Grasshopper roadmap milestone complete.

## 0.2.0 - 2026-10-09
- Added the provider-neutral `revit-workflow` skill for Revit, pyRevit, Dynamo, and Revit API tasks with explicit dry-run, transaction, worksharing, verification, and rollback guidance.
- Added Revit-specific routing plus activation regression cases while preserving generic IFC/DWG/DXF/SVG work under `cad-bim-automation`.
- Made global installers discover canonical skills and agents dynamically so future additions do not require hard-coded installer lists.
- Made Linux and Windows CI installer smoke tests derive expected skill/agent counts dynamically.
- Added `scripts/validate-native.sh` with safe Claude strict validation, isolated Codex marketplace/plugin installation, and Gemini extension validation when each CLI is available.
- Documented the maintainer native-validation path and marked the first Revit workflow milestone complete.

## 0.1.1 - 2026-10-01
- Modernized the portable OpenAI plugin manifest to the current Agent Plugins layout and metadata.
- Added a native repo marketplace for verified two-command Codex plugin installation.
- Made Claude plugin components explicit and added strict manifest-validation compatibility.
- Added bounded turn/time budgets to Claude and Gemini specialist subagents.
- Added beginner-safe `auto` runtime detection to global installers while preserving explicit/all targets.
- Added canonical skill registry, provider-neutral activation eval cases, eval documentation, and stronger CI contract checks.
- Added Linux and Windows installer smoke-test jobs to CI.
- Updated GitHub Actions to the current Node 24 generations (`checkout@v7`, `setup-python@v7`).
- Added update instructions for clone installs, Claude plugins, and Gemini extensions.
- Corrected Codex documentation to avoid unnecessary global AGENTS.md routing context.

## 0.1.0 - 2026-10-01
- Initial public repository.
- Nine portable architecture/AEC Agent Skills.
- Beginner-first ZIP and CLI guidance.
- Codex user-scoped installation adapter.
- Claude Code marketplace/plugin adapter with specialist subagents.
- Gemini CLI extension adapter with specialist subagents.
- Provider-neutral global-adoption prompt and project template.
- Repository validation and provider-sync tooling.
