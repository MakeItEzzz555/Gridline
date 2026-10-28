<div align="center">

<img src="assets/brand/gridline-logo.png" alt="Gridline — architectural drafting logo and wordmark" width="720" />

### From brief to blueprint to handover.

**30 portable AI Agent Skills + 12 specialist agents for architecture, BIM, CAD and multidisciplinary AEC workflows.**

[![validate](https://github.com/MakeItEzzz555/Gridline/actions/workflows/ci.yml/badge.svg)](https://github.com/MakeItEzzz555/Gridline/actions/workflows/ci.yml)
![Agent Skills](https://img.shields.io/badge/Agent%20Skills-portable-2563eb)
![AEC](https://img.shields.io/badge/AEC-architecture%20%2B%20BIM%20%2B%20civil-475569)
[![license](https://img.shields.io/badge/license-MIT%20%2B%20GPL--2.0--or--later-blue)](skills/architectural-drawing-generation/references/BLENDER-LICENSING.md)

**[Copy the install prompt](#install-with-your-ai-agent-copy-once)** · **[Current status](#what-gridline-actually-ships--october-2026)** · **[Skills](#the-30-superpowers)** · **[Drawings](#coordinated-cad-drawings)** · **[Tools](#cad--bim--aec-tools)** · **[Research](docs/RESEARCH.md)**

https://github.com/user-attachments/assets/a397a1b3-0f50-4d00-948a-62c9537144d8

</div>

---

Gridline gives capable AI coding/agent tools a structured way to help with the **full building-project lifecycle**: programming and feasibility, site analysis, concept design, plans/sections/elevations, BIM/CAD workflows, structural/MEP/civil coordination, technical documentation, performance, quantities/cost, construction administration, handover and post-occupancy.

It is not one giant “act like an architect” prompt. Each specialist is discovered only when relevant, keeping the always-loaded context small and the workflow auditable.

## What Gridline actually ships — October 2026

Gridline combines **30 portable AEC skills and 12 specialist agents** with runnable drafting and review utilities. The descriptions below distinguish **implemented software**, **partial review coverage**, and **planned capabilities**. Architectural validation is not professional certification.

| Capability | Current evidence and scope |
| --- | --- |
| Agent installation and skill routing | Cross-provider packages, portable skill directories, a one-copy installation prompt, provider activation fixtures, and reversible/ownership-aware global installers ([v0.5.0–0.5.1](CHANGELOG.md)) |
| Conceptual drawings | Dependency-free JSON-to-SVG/DXF engine for six supported primitives; output remains **conceptual, not for construction** ([drawing details](docs/DRAWING_OUTPUTS.md)) |
| Specification-derived CAD plan sheets | Structured building JSON → standard-layered **DXF plans**, paper-space layouts/title blocks, required vector PDFs, room/door/window schedules and a sheet register, with ISO 13567 / NCS profiles and office overrides ([PR #6](https://github.com/MakeItEzzz555/Gridline/pull/6)) |
| Local drawing checks | `aec_cad.py check` independently measures supported wall/opening/room primitives and PDF straight-vector plot mapping, plus selected drafting/title/tag/schedule invariants. Receipts bind input/output/validator hashes and coverage. **This is supported local 2D verification, not complete geometry, PDF visual fidelity or native AutoCAD acceptance.** ([verification scope](docs/DRAWING_OUTPUTS.md)) |
| Read-only revision-impact review | Compare two building specs to list changed openings, walls, rooms/levels, affected **indexed** sheets and impacted schedules. Coverage is partial: declared host/level links and grid/document-setting changes are tracked, but room-wall adjacency and unrelated CAD/PDF drawings are not independently inspected ([PR #9](https://github.com/MakeItEzzz555/Gridline/pull/9), [issue #10](https://github.com/MakeItEzzz555/Gridline/issues/10)) |
| Local read-only MCP server | Optional **Gridline-owned** stdio MCP review server exposes revision comparison and capability discovery. It **does not connect to or edit** AutoCAD, Revit or other native applications ([PR #9](https://github.com/MakeItEzzz555/Gridline/pull/9)) |
| Professional host integration | Revit, AutoCAD, Rhino/Grasshopper, IFC/Bonsai and related **workflow guidance** exists in skills. Native MCP tool connections, host acceptance testing and controlled model writes are **not yet shipped** ([issue #12](https://github.com/MakeItEzzz555/Gridline/issues/12)) |
| Local Blender 3D proof (experimental) | `scripts/blender_native.py` can generate a **new** native .blend + .glb from supported building-spec walls/levels/doors/windows and independently reopen/measure outputs in a locally installed Blender version. Does **not** create detailed roofs/interiors or reconstruct architecture from a reference photo; this is a CLI bridge, **not a native Blender MCP** ([scope and usage](docs/BLENDER_NATIVE_BRIDGE.md)) |
| Optional ARCHIMESH components (0.9.0) | Typed component catalog, explicit pinned-source execution, disposable Blender 5.2.3 native/GLB readback, signed local proposals and opt-in CC0 texture cache. The local ledger now also rejects a head rewind to an older signed content hash without an approved transition. Source-bound IFC4 and real texture readback are tested; professional/client and live-host gates remain explicit ([usage, evidence and limits](docs/ARCHIMESH_INTEGRATION.md)). |

### Verified limitations and next engineering gates

The independent [Gridline/Codex technical audit](docs/GRIDLINE_CODEX_AUDIT_AND_DISCUSSION_2026-10-22.md) reproduced a critical defect in the old checker: deleting one opening LINE while preserving tags/schedules still returned PASS. [PR #21](https://github.com/MakeItEzzz555/Gridline/pull/21) adds independent readback and adversarial tests for supported primitives. Full geometric completeness, raster visibility and native acceptance remain separate gates; the checker is not construction-ready certification.

Other gates remain open: [cross-sheet comparison and 40-sheet reference fixtures (#10)](https://github.com/MakeItEzzz555/Gridline/issues/10), [IFC schema/IDS validation (#11)](https://github.com/MakeItEzzz555/Gridline/issues/11), [real CAD/BIM adapters (#12)](https://github.com/MakeItEzzz555/Gridline/issues/12), [editable 2D→3D/BIM (#13)](https://github.com/MakeItEzzz555/Gridline/issues/13), [scanned/hand-marked plans (#14)](https://github.com/MakeItEzzz555/Gridline/issues/14), [human-approved revision state/transactions (#15)](https://github.com/MakeItEzzz555/Gridline/issues/15), and [native AutoCAD open/AUDIT/edit/plot/round-trip evidence (#16)](https://github.com/MakeItEzzz555/Gridline/issues/16).

**These are implementation issues, not completed product claims.** The [community progress ledger](docs/COMMUNITY_PROGRESS_2026-10-23.md) records delivered pieces, proof, remaining acceptance criteria, and why issues stay open. Contributions, professional CAD sample sets and critical reviews are welcome.

## Install with your AI agent — copy once

**No terminal knowledge required.** Open Codex, Claude Code, Gemini CLI, Cursor, OpenCode, Copilot, or another filesystem-capable agent and paste this:

<!-- AGENT_INSTALL_PROMPT_START -->
```text
Install Gridline for my current user.
Official source: https://github.com/MakeItEzzz555/Gridline

First inspect the official README, INSTALL_PROMPT.md, skills/manifest.json and installer/provider docs. Detect which compatible agent runtimes are already installed.

Prefer the standard Agent Skills installer when supported:
npx skills@latest add MakeItEzzz555/Gridline --all -g

Otherwise use this repository's documented native Codex/Claude/Gemini method or reversible global installer. Preserve existing skills/configuration and back up conflicts. Do not use sudo/root, modify my architecture projects, read credentials, delete unrelated skills, or install third-party MCP servers/plugins.

Install only Gridline for the detected hosts. Verify the installed stable-skill count against skills/manifest.json and use documented provider list/validate commands when available. Report PASS/FAIL per host, installed and backup paths, update/uninstall instructions, and whether I need to reload or start a fresh session.

Stop rather than guessing if a command, path, host or permission model is unclear. Do not claim installation succeeded until the filesystem/provider confirms it.
```
<!-- AGENT_INSTALL_PROMPT_END -->

[Full install prompt, alternatives and safety notes](INSTALL_PROMPT.md).
## One command

For Agent Skills hosts supported by the community `skills` installer:

```bash
npx skills@latest add MakeItEzzz555/Gridline --all -g
```

To opt out of that CLI's documented anonymous telemetry:

```bash
DISABLE_TELEMETRY=1 npx skills@latest add MakeItEzzz555/Gridline --all -g
```

### Native provider installs

**Codex**
```bash
codex plugin marketplace add MakeItEzzz555/Gridline
codex plugin add gridline@gridline
```

**Claude Code**
```bash
claude plugin marketplace add MakeItEzzz555/Gridline
claude plugin install gridline@gridline
```

**Gemini CLI**
```bash
gemini extensions install https://github.com/MakeItEzzz555/Gridline
```

Or clone once and let the repository detect installed runtimes:

```bash
git clone https://github.com/MakeItEzzz555/Gridline.git
cd Gridline
bash scripts/install-global.sh auto
```

Windows users can run `powershell -ExecutionPolicy Bypass -File .\scripts\install-global.ps1 auto`.

## Measured skill activation

Record actual Codex, Claude Code or Gemini CLI activations and use the dependency-free [behavioral evaluation scorer](docs/EVALS.md) to measure per-skill recall, negative controls and regressions against a baseline. CI tests the scorer without making model calls or claiming measured routing accuracy.

## The 30 superpowers

### Brief, research and site
| Skill | Use it for |
|---|---|
| `architecture-orchestrator` | End-to-end routing and multidisciplinary synthesis |
| `architecture-programming` | Briefs, rooms, areas, adjacencies and requirements |
| `site-analysis-feasibility` | Survey/context/climate constraints, opportunities and capacity |
| `site-regulation-research` | Planning, zoning and building-control source research |
| `precedent-research` | Evidence-backed architectural case studies and transferable lessons |

### Design and drawing
| Skill | Use it for |
|---|---|
| `concept-schematic-design` | Parti, massing, blocking, plans, sections, elevations and options |
| `concept-design-review` | Critique and compare existing schemes |
| `interior-fitout-design` | Fit-out, furniture/equipment, RCP, finishes and joinery briefs |
| `architectural-drawing-generation` | Site/floor/roof/RCP plans, elevations, sections, details, SVG/DXF |
| `visualization-rendering` | Cameras, lighting, materials, render/animation workflows |
| `presentation-review` | Boards, narratives, jury/client presentation quality |
### CAD, BIM and interoperability
| Skill | Use it for |
|---|---|
| `revit-workflow` | Revit, pyRevit, Dynamo and Revit API |
| `rhino-grasshopper-workflow` | Rhino, Grasshopper, RhinoCommon and parametric geometry |
| `autocad-dwg-workflow` | AutoCAD, DWG, xrefs, layers, blocks, plotting, AutoLISP/.NET |
| `openbim-ifc-coordination` | IFC, BCF, IDS, bSDD, IfcOpenShell/Bonsai and federation |
| `cad-bim-automation` | Generic DXF/SVG/Blender/FreeCAD and cross-platform automation |

### Engineering and performance coordination
| Skill | Use it for |
|---|---|
| `civil-site-design` | Survey, grading, drainage, utilities, roads/parking and Civil 3D |
| `structural-coordination` | Grids, spans, cores, transfers, openings and engineer interfaces |
| `mep-coordination` | Plant, shafts, risers, ceilings, services, penetrations and clashes |
| `life-safety-accessibility` | Sourced egress, fire/life-safety and accessible-route coordination |
| `building-envelope-performance` | Water/air/vapor/thermal layers, facades, roofs and interfaces |
| `sustainability-daylight-energy` | Passive design, daylight, energy, carbon, water and resilience |

### Technical delivery, cost and operation
| Skill | Use it for |
|---|---|
| `construction-documentation` | Drawing sets, schedules, details, revisions and issue packages |
| `drawing-qa` | Cross-sheet drawing QA |
| `materials-specifications` | Materials, finishes, performance requirements and specifications |
| `area-quantity-audit` | Areas, counts, schedules and takeoff reconciliation |
| `cost-planning-value-engineering` | Early cost plans, option deltas and VE registers |
| `construction-administration` | RFIs, submittals, site observations, changes and punch lists |
| `handover-fm-postoccupancy` | O&M, asset data, closeout, FM and POE |
| `architecture-red-team` | Independent final challenge before consequential issue/submission |

[Full lifecycle map](docs/AEC_LIFECYCLE.md).
## Revision impact and cross-sheet QA (read-only pilot)

When an opening, wall, room, level, grid, project unit, drafting standard or drawing revision changes, Gridline identifies **affected indexed sheets and schedules** for review. It follows declared wall→opening and level→wall/room dependencies in both revisions, including detail-only references. Grid edits and document-setting changes conservatively flag **all indexed sheets**, since no per-sheet grid/style dependency index exists; unit changes also flag dimensional schedules. The additive `changed_document_fields` report field identifies unit, standard and schema-version changes. This is read-only source-spec impact analysis; it **does not inspect unrelated PDFs, prove complete room-wall adjacency, or certify 40 unknown external drawings**.

```bash
python3 skills/architectural-drawing-generation/scripts/revision_impact.py before.building.json after.building.json --out impact.json
```

There is also an opt-in local, read-only Gridline MCP server exposing this comparison to MCP-compatible agents (requires the official Python MCP SDK v2 and an explicitly permitted project directory). **It is not a connection to AutoCAD or Revit.**

[Next phases: IFC/IDS validation, official Autodesk MCP, Rhino, Blender, Archicad, editable 3D and scanned drawing research](docs/NEXT_AEC_PHASES.md).

## Coordinated CAD drawings

When a trusted native CAD/BIM host is available, the skills provide guidance for working with the native editable model; **Gridline does not currently provide an installed native-host connection**. Without one, the drawing skill can build a **specification-derived plan-sheet set**: standard-layered DXF files (ISO 13567, US NCS or an office profile), required vector PDFs, room/door/window schedules and a sheet register. The current checker inspects a defined subset of properties and schedule consistency; it **does not** certify geometry completeness, PDF fidelity, cross-sheet views or AutoCAD editability. Native AutoCAD open/AUDIT/edit/plot/round-trip testing is an outstanding acceptance gate ([#16](https://github.com/MakeItEzzz555/Gridline/issues/16)).

```bash
pip install ezdxf==1.4.5 matplotlib==3.11.2 pypdf==6.21.2
D=skills/architectural-drawing-generation
python3 $D/scripts/aec_cad.py build $D/references/example-house.building.json /tmp/example-house
python3 $D/scripts/aec_cad.py check $D/references/example-house.building.json /tmp/example-house
```

![Example sheet A-101: ground floor plan at 1:100 on A3, built and checked from the example spec](examples/example-house-A-101.png)

It draws plans today (walls, doors, windows, rooms, grids, dimensions, sheets); sections, elevations and details are next. For quick diagrams there is also a small dependency-free engine that turns an explicit JSON spec into SVG or DXF. It draws six primitives (lines, rectangles, circles, polylines, text and dimensions), enough for **conceptual** plan and section diagrams. It does not model walls, doors, hatching, title blocks or scale bars:

```bash
python3 skills/architectural-drawing-generation/scripts/aec_draw.py skills/architectural-drawing-generation/references/concept-plan.drawing.json /tmp/plan.svg
python3 skills/architectural-drawing-generation/scripts/aec_draw.py skills/architectural-drawing-generation/references/concept-plan.drawing.json /tmp/plan.dxf
```

The JSON format is documented by [aec-drawing.schema.json](skills/architectural-drawing-generation/references/aec-drawing.schema.json). The fallback never invents dimensions and stamps conceptual output **CONCEPT / NOT FOR CONSTRUCTION** by default. [Drawing-output details](docs/DRAWING_OUTPUTS.md).

A bounded [AutoCAD Mac inspection adapter](docs/AUTOCAD_NATIVE_INSPECTION.md) prepares a disposable DXF copy and a manually activated read-only AutoLISP inspector. Installed status, operator-captured metadata and native AUDIT/plot/DWG roundtrip remain distinct evidence gates; this is not an MCP connection.

## CAD / BIM / AEC tools

The pack knows how to route work for **Revit, pyRevit, Dynamo, Rhino, Grasshopper, AutoCAD, Civil 3D, IFC/IfcOpenShell/Bonsai, DXF/SVG, Blender and FreeCAD**. Public MCP projects also exist for Revit, Rhino/Grasshopper, AutoCAD, Archicad, Vectorworks and SketchUp.

Those integrations are **optional and not installed automatically**. A model-writing bridge can change professional project files; review its source, permissions, network surface and write commands before connecting it.

[Tool-integration policy](docs/TOOL_INTEGRATIONS.md).

A dependency-free [source-detail intake gate](docs/PROJECT_BRIEF_GATE.md) records unknown dimensions and approvals before exact 3D work. The incomplete villa example blocks plot boundary, floor-to-floor heights and roof; concept remains provisional. This is an intake check, not model completeness or native-write permission.

## A real project context

Copy [templates/ARCHITECTURE_PROJECT.md](templates/ARCHITECTURE_PROJECT.md) into a project root and fill only what is known. Additional reusable templates cover:

- design brief and room/program inputs;
- site analysis;
- drawing briefs and sheet registers;
- BIM coordination;
- RFIs and site observations;
- punch/defects tracking;
- handover/closeout.

Then ask naturally:

> Develop three schematic options from this brief and site evidence, draw the preferred plan and section, reconcile its area schedule, and identify the structural/MEP/life-safety questions that must be resolved next.

The orchestrator should load only the relevant specialists.

## How the system works

```text
request
  │
  ▼
architecture-orchestrator
  ├── establishes stage / jurisdiction / units / source truth
  ├── routes only relevant skills
  ├── prefers native CAD/BIM tools when safely available
  ├── uses bounded specialist agents for independent review
  └── verifies and red-teams consequential outputs
```

The design principle is **progressive disclosure**: short skill names/descriptions support discovery; full workflows load on activation; scripts, templates and reference docs are opened only when needed.
## Professional and safety boundary

Architecture, structural engineering, civil engineering, MEP, fire engineering, accessibility, cost consultancy and construction administration overlap—but they are not interchangeable professional responsibilities.

This project can research, calculate, draft, automate, coordinate, generate conceptual drawings and review evidence. It does **not** by itself provide licensure, statutory approval, signed/stamped engineering, permit approval or issue-for-construction certification.

The core rules are deliberately conservative:

- never invent survey coordinates, dimensions, regulations, loads/capacities, product certifications or current costs;
- cite jurisdiction, authority, source and edition for regulatory claims;
- preserve source models and issued files;
- use read-only inventory and dry runs before bulk writes;
- make units, origin/datum, IDs and revisions explicit;
- distinguish observed fact from assumption and design option;
- require competent human review for regulated and construction-critical conclusions.

## Research-driven, not prompt folklore

The capability map is grounded in professional lifecycle frameworks, buildingSMART/openBIM standards, current vendor documentation and public AEC agent/tool projects. The research specifically informed:

- lifecycle coverage from briefing through post-occupancy;
- version-aware Revit/Rhino/AutoCAD workflows;
- IFC + BCF + IDS information coordination;
- Civil 3D/site workflow concepts;
- guarded live-tool/MCP write patterns;
- progressive skill disclosure instead of a huge permanent prompt.

[Research basis](docs/RESEARCH.md).

## Maintainer validation

```bash
python3 scripts/sync-provider-skills.py --check
python3 tests/check_repo.py
python3 -m unittest discover -s tests -v
bash scripts/validate-native.sh
```

The repository tests structural skill coverage and provider synchronization. Native provider validation runs only for installed CLIs. Behavioral model activation still requires provider/model evals; installation alone is not proof that every model will select every skill perfectly.

## Project status

This is an open-source professional-assistance toolkit, not a substitute for appointed professionals. Coverage is broad, but every real office has its own BIM standards, detail libraries, codes, contracts and QA procedures. Those should be layered into project/organization-specific skills rather than hard-coded as universal rules here.

[Research](docs/RESEARCH.md) · [Lifecycle](docs/AEC_LIFECYCLE.md) · [Drawings](docs/DRAWING_OUTPUTS.md) · [Providers](docs/PROVIDERS.md) · [Roadmap](ROADMAP.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

---

<div align="center">

**Gridline — AEC agent skills, specification-derived drawings and auditable reviews. Native quality gates are still in development.**

*Community project. Not affiliated with Autodesk, McNeel, Graphisoft, Nemetschek, buildingSMART, OpenAI, Anthropic or Google.*

</div>
