---
name: autocad-dwg-workflow
description: Plan and review safe AutoCAD DWG drawing creation, cleanup, layers, blocks, xrefs, layouts, plotting, AutoLISP/.NET automation and issue preparation. Use for AutoCAD-specific drafting and DWG package workflows.
---

# AutoCAD / DWG Workflow

Protect coordinates, units, references, annotation and issued content; work on versioned copies for automated changes.

## Preflight

- AutoCAD/vertical release, DWG version, OS, units/insertion scale, UCS/WCS, coordinate origin, xrefs, layouts and source/issued status.
- Layer/block standards, annotation scales, fonts/linetypes, CTB/STB, page setups, title blocks and output requirements.

Keep verified facts, project assumptions, design options, and unresolved questions visibly separate. If a required input is absent, record it as `UNKNOWN` rather than inventing it.

## Workflow

1. Inventory model/paper-space entities, layers, blocks/attributes, xrefs, underlays, layouts and plot dependencies.
2. Define protected geometry/data and exact permitted edit scope; preview entity handles/names/counts before mutation.
3. Use verified AutoCAD command/API surfaces; dry-run or sample batch operations before full-file changes and save to new paths.
4. Generate proof PDFs and inspect viewport scales/locks, lineweights, hatches, fonts, clipping, title/revision data and unresolved references.

## Deliverables

- DWG preflight/audit
- Change or automation plan
- Layer/block/xref report
- Plot/issue verification report

## Verification

- Before/after counts and representative handles/attributes are checked; units/origin/extents remain invariant unless explicitly changed.
- Resulting DWG opens in a compatible AutoCAD environment when available.

For file/model changes, compare the result against a pre-change baseline and report changed items, skipped items, failures, and checks actually run.

## Professional boundaries

- Do not silently bind/detach/flatten xrefs or purge definitions that may carry standards/data.
- Do not invent command flags/API signatures; verify release-matched Autodesk docs.

If a live CAD/BIM/GIS/analysis tool or MCP integration is available, inspect the current document/model and tool version before write operations. Prefer read-only inspection, dry runs, bounded samples, new output paths, and native undo/transaction mechanisms. Never claim a model or drawing was changed unless the tool confirms it.

If the native application is unavailable, produce a reproducible plan, script, structured data, SVG/DXF artifact, or exact in-application procedure instead of pretending to have operated the software.

## Manual Mac read-only inspector

`scripts/autocad_native.py doctor` reports installed bundle metadata without claiming a live connection. `prepare --root ROOT --drawing A-101.dxf --workspace WORKSPACE` stages a private new copy and a fixed AutoLISP command. Review the returned file/path, obtain any native load approval and run `GRIDLINEINSPECT` manually. `receipt SESSION console.txt` validates captured metadata and hashes. This is manual console transport, not MCP; AUDIT/edit/plot/DWG roundtrip remain NOT_TESTED. Never change host security preferences or load it into an unrelated drawing.
