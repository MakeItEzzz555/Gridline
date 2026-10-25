---
name: visualization-rendering
description: Plan and review architectural visualization workflows for diagrams, clay/massing views, material studies, photoreal rendering, animation and presentation images across Enscape, Twinmotion, V-Ray, Blender and similar tools. Use for camera, lighting, materials, entourage, render briefs and visual QA.
---

# Architectural Visualization & Rendering

Make visualizations communicate the design accurately; distinguish design truth from illustrative atmosphere.

## Preflight

- Source model/revision, intended audience, required views, image/video format, renderer/version, material/lighting data and presentation deadline.
- What geometry/material/site context is verified versus illustrative.

Keep verified facts, project assumptions, design options, and unresolved questions visibly separate. If a required input is absent, record it as `UNKNOWN` rather than inventing it.

## Workflow

1. Define the communication goal and select cameras that explain spatial relationships, scale and context.
2. Clean model hierarchy/material assignments and establish physically plausible lighting/exposure before decorative effects.
3. Use staged previews to verify geometry, openings, levels, materials and context; then add entourage/atmosphere without obscuring design facts.
4. Record post-processing and any illustrative substitutions so rendered imagery cannot be mistaken for guaranteed final conditions.

## Deliverables

- Render/view list
- Camera-light-material brief
- Renderer-specific workflow plan
- Visual QA and disclosure notes

## Verification

- Views match the current model revision and do not hide known conflicts.
- Material/product representation is identified as exact, approximate or illustrative.

For file/model changes, compare the result against a pre-change baseline and report changed items, skipped items, failures, and checks actually run.

## Professional boundaries

- Do not fabricate approvals, surrounding developments or guaranteed finishes.
- Do not use visualization to conceal unresolved safety, accessibility or constructability issues.

If a live CAD/BIM/GIS/analysis tool or MCP integration is available, inspect the current document/model and tool version before write operations. Prefer read-only inspection, dry runs, bounded samples, new output paths, and native undo/transaction mechanisms. Never claim a model or drawing was changed unless the tool confirms it.

If the native application is unavailable, produce a reproducible plan, script, structured data, SVG/DXF artifact, or exact in-application procedure instead of pretending to have operated the software.


## Optional bounded component picker

For explicit procedural door/window/cabinet/shelf/stair/column/tile/prop requests,
discover the installed `architectural-drawing-generation` skill. If missing, report
the dependency. Its `scripts/archimesh_components.py catalog` lists supported kinds
and every required parameter; use that as the picker and collect reviewed dimensions,
position/orientation and materials before `validate`/`build`. Do not invent missing
sizes, treat sample fixtures as a real design, or generate executable Python from
prose. Read that skill's limits and licensing boundary first. The optional backend
uses a separately obtained, exact-hash-approved official source in disposable
Blender 5.2.3 processes, with native/GLB readback and new outputs only. It does not
install an extension or fix interactive upstream panels. For textures, use its
separate consented CC0 plan/cache; builds are offline and require explicit UV scale.
Frozen mesh/PBR readback does not establish manufacturing or architectural approval.
