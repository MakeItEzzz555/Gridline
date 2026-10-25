---
name: civil-site-design
description: "Coordinate architectural projects with civil/site engineering: survey and terrain, grading, earthworks, access roads, parking, pedestrian routes, stormwater/drainage, utilities, retaining conditions and Civil 3D workflows. Use for site grading concepts, surface/corridor coordination, utility interfaces and civil-architectural handoff."
---

# Civil / Site Design Coordination

Develop and review site/civil concepts while keeping hydrology, road, geotechnical and utility engineering with qualified civil specialists.

## Preflight

- Topographic/cadastral survey, coordinate/datum system, existing/proposed surfaces, drainage catchments/outfalls, road/access requirements, utilities and geotechnical information.
- Civil 3D version/workflow when applicable: surfaces, feature lines, alignments, profiles, corridors, pipe/pressure networks and data shortcuts.

Keep verified facts, project assumptions, design options, and unresolved questions visibly separate. If a required input is absent, record it as `UNKNOWN` rather than inventing it.

## Workflow

1. Preserve survey control and build an existing-conditions/site-constraints model before proposed grading.
2. Coordinate finished-floor levels, accessible entries, roads/parking, slopes, walls/steps and landscape interfaces against proposed surfaces.
3. Map stormwater flow paths, utility corridors and service connections; expose conflicts with foundations, trees, public realm and structures.
4. For Civil 3D work, inventory dynamic dependencies and data shortcuts before edits; validate surfaces, profiles, corridors and quantities after changes.

## Deliverables

- Site/civil coordination plan
- Level/grading interface matrix
- Drainage/utility corridor diagram
- Civil 3D change/verification plan when relevant

## Verification

- Coordinates, datum, units, surface versions and level references are explicit.
- Cut/fill, hydraulic capacity, pavement and retaining design are not treated as verified without engineering calculations.

For file/model changes, compare the result against a pre-change baseline and report changed items, skipped items, failures, and checks actually run.

## Professional boundaries

- Do not replace licensed civil, drainage, road or geotechnical design.
- Never move survey control or authoritative utility data without explicit verified instruction.

If a live CAD/BIM/GIS/analysis tool or MCP integration is available, inspect the current document/model and tool version before write operations. Prefer read-only inspection, dry runs, bounded samples, new output paths, and native undo/transaction mechanisms. Never claim a model or drawing was changed unless the tool confirms it.

If the native application is unavailable, produce a reproducible plan, script, structured data, SVG/DXF artifact, or exact in-application procedure instead of pretending to have operated the software.

## On-demand evidence and practice references

Load only the relevant reference. These are original review prompts, not binding code or full-book extraction.

- [B12: site and landscape](references/b12-practice.md)
- [B15: landscape junction review](references/b15-practice.md)
