---
name: openbim-ifc-coordination
description: Plan and review openBIM interoperability using IFC, BCF, IDS, bSDD and IfcOpenShell/Bonsai workflows. Use for IFC export/import, model audit, spatial structure, property sets, quantities, model federation, issue exchange, information requirements and cross-platform BIM coordination.
---

# openBIM / IFC Coordination

Treat IFC as structured building data, not just geometry. Preserve GUIDs, schema/version, units, spatial containment, classifications, properties and issue traceability.

## Preflight

- IFC schema/MVD or exchange target, authoring tool/version, coordinate strategy, model purpose, information requirements and receiving software.
- Federation disciplines, file/revision IDs, BCF/issue workflow, classification/property requirements and IDS when available.

Keep verified facts, project assumptions, design options, and unresolved questions visibly separate. If a required input is absent, record it as `UNKNOWN` rather than inventing it.

## Workflow

1. Inventory project/site/building/storey/space structure, element counts, GUID stability, units, coordinates and schema.
2. Validate required classes/properties/classifications/materials/quantities against project requirements or IDS; remember IDS checks alphanumeric information, not geometry.
3. Federate and clash/issue-coordinate with BCF-style identifiers rather than screenshots alone; preserve issue status and viewpoints.
4. Round-trip sample exchanges before full delivery; compare element counts, GUIDs, property sets, geometry extents and quantities.

## Deliverables

- IFC exchange/validation plan
- Information requirement or IDS mapping
- Federation/BCF issue register
- Round-trip verification report

## Verification

- Schema, units, coordinates, GUIDs and spatial hierarchy are explicit and checked.
- Export success is not treated as interoperability success until the receiving workflow is tested.

For file/model changes, compare the result against a pre-change baseline and report changed items, skipped items, failures, and checks actually run.

## Professional boundaries

- Do not invent IFC property requirements or claim IDS validates geometry.
- Third-party BIM/MCP tools are optional and must be reviewed before granting write access.

If a live CAD/BIM/GIS/analysis tool or MCP integration is available, inspect the current document/model and tool version before write operations. Prefer read-only inspection, dry runs, bounded samples, new output paths, and native undo/transaction mechanisms. Never claim a model or drawing was changed unless the tool confirms it.

If the native application is unavailable, produce a reproducible plan, script, structured data, SVG/DXF artifact, or exact in-application procedure instead of pretending to have operated the software.


## Optional Gridline source-bound IFC4 exchange

Discover the installed `architectural-drawing-generation` skill before invoking
its own `scripts/component_ifc.py`; report a missing dependency rather than
inventing a path. The bounded exporter requires IfcOpenShell 0.9.0.post1 plus pytest
for actual EXPRESS validation, a selected signed state database, explicit matching
project requirements and separately trusted native receipt/owner-key pins. It
checks typed source/units/spatial/room/material/quantity/host/void/filling data,
raw and independently evaluated geometry, and stable source mappings. Public
`--verify` additionally requires the retained IFC receipt pin and preserves
published bytes. Read its command help, optional requirements and source/licensing
boundaries first; no dependency is automatically installed.

Use an owner-selected persistent globally unique project identity. The accepted
synthetic fixture and its minimal provenance requirements are not a client's IDS,
certified MVD or regulatory brief. Unsupported requirements, unknown mandatory
materials or missing source approvals block export. Report the actual checked
scope and all receiving-client/IDS/professional gaps. IFC maps material identities;
packed photographic PBR remains in Blender/GLB. This file-only pipeline grants no
live-host edit permissions and does not close every #13/#15 interoperability or
transaction criterion.
