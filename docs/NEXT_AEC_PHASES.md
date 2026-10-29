# Gridline: coordination, openBIM validation and native tool integrations

Research checkpoint: **2026-10-22**. This is an implementation plan grounded in current vendor documentation, not a claim that all host adapters are installed or tested.

## Why the priorities changed

Two real architectural problems should drive the next work:
1. **A window schedule revision** can invalidate numerous plans, elevations, sections, details and schedules. Catching that must start with stable element IDs, explicit sheet references and detectable revision impact, not an LLM reading 40 PDFs and guessing.
2. **A model that exports as IFC is not necessarily valid or fit for a client's information requirements.** Use separate schema/normative validation and project-specific IDS checks. IDS generally checks specified data requirements, **not geometric correctness**.

A third research objective is **scanned / hand-marked plan reconstruction**. This is inherently uncertain; unscaled scans, handwriting, erasures and non-orthogonal photographs require confidence flags, calibration, user confirmation and geometry review before generating any BIM element.

## Additional community feedback: state safety and native DXF readback

Two further community comments raised separate release-quality concerns: (a) when agents hallucinate or compete during design edits, **who controls authoritative project state?**, and (b) **do generated DXF files really open and behave cleanly in AutoCAD?**

### P0 — Authoritative state and deterministic transaction gate

**Research-backed design requirements** (tracked in [#15](https://github.com/MakeItEzzz555/Gridline/issues/15)):

1. Keep a canonical model/spec revision with units, datum/CRS, topology, constraints, unresolved assumptions, element IDs and provenance **outside model chat/session context**. An AI response is not a committed design state.
2. Every agent proposes a typed, reviewable patch against an **expected revision hash**: old/new element attributes, exact targets, dependency impact and evidence. A deterministic validator enforces constraints before any write. Unknown site/structural dimensions or conflicting levels must block the operation, not be filled by a guess.
3. Use optimistic concurrency to prevent two agents from silently overwriting one another. Before committing any patch, compare the current authoritative revision with the proposal base; on conflicts, return a structured rejection/rebase request. Append-only event history (accepted/rejected/approved/rolled back) makes rollback and audit possible.
4. Map stable internal identities to host-native identifiers (e.g., Revit UniqueId, IFC GlobalId, CAD handles) using explicit, separately validated mapping tables. Neither exported DXF handles nor IFC metadata constitute a cross-application revision system.
5. Use local host-native transactions for approved mutations, not a sequence of uncontrolled MCP calls. **Revit API `Transaction`, `SubTransaction` and `TransactionGroup` support commit/rollback**, but Autodesk also documents failure processing at commit time; success must be confirmed after host-side processing and readback. Equivalent AutoCAD operations need their own verified transaction/undo pathway.
6. Make read/dry-run the default tool scope. Approve an exact diff and limit write operations by file/model, revision, target and duration; prohibit arbitrary evaluation/credential access. Reject stale snapshots and require independent post-change checks.

**Adversarial acceptance cases:** two agents modifying the same wall from stale snapshots; nonexistent wall/window IDs; a window wider than its host wall; unresolved mm-versus-metres; duplicate identifiers; phantom levels; disconnected geometry; failed partial native transaction; simulated client interruption. All should preserve the last approved state, with evidence of rejection. These checks are required before expanding the write-capable MCP set.

Sources: [Autodesk Revit `Transaction`](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/308ebf8d-d96d-4643-cd1d-34fffcea53fd.htm), [`TransactionGroup`](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/f1113d30-4c36-7844-1537-aad7f095cea0.htm), [Revit Automation failure handling](https://aps.autodesk.com/en/docs/design-automation/v3/developers_guide/revit_specific/), [AWS agent deterministic state guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/best-practices-system-design.html), [OpenAI agent guardrails and structured outputs](https://developers.openai.com/tracks/building-agents).

### P1 — AutoCAD compatibility is an independent evidence gate

Existing code produces R2018 DXF files with model-space geometry, paper-space sheets, dimensions, layers and schedule/readback checks. It has **not** been proven production-ready by a native AutoCAD round trip. Even `ezdxf` documents that it is neither an architectural CAD kernel nor a DWG converter; some XREF cases require DWG conversion for AutoCAD use. **Do not claim that library audit success means native AutoCAD compatibility.**

Implement [#16](https://github.com/MakeItEzzz555/Gridline/issues/16) as a compatibility matrix with captured app/version/OS/license and these verifications on *copies*:

- Open in actual AutoCAD with errors and warnings logged; run native `AUDIT` and inspect whether anything was repaired or lost.
- Confirm standard layers, ByLayer properties, dimensions, text fonts and heights, snapping, units and insertion scale, blocks/attributes and roundtrip editability.
- Verify named paper-space layouts, locked viewport scale, proper plot area, PDF plot and measurements at known 1:50 and 1:100 scales. Autodesk reports model objects missing from layout/plot when viewports are misconfigured.
- Save as DWG, reopen, modify a sample opening, then (when supported) resave/re-import DXF; measure differences in geometry, schedules, annotation, xrefs, block attributes, quantities, and entity identity. A working file in another viewer is not evidence AutoCAD passed.
- For licensed host automation, explore Autodesk's supported AutoCAD Core Console without presuming it is installed on developer machines or available via generic cloud MCP.
- Use outcome labels: `DXF_GENERATED`, `EZDXF_AUDITED`, `AUTOCAD_OPENED`, `AUTOCAD_AUDITED`, `AUTOCAD_EDITED_AND_PLOTTED`, `DWG_DXF_ROUNDTRIP_VERIFIED`, with `NOT_TESTED` where evidence is unavailable. Fail CI only for gates the run actually attempted; never label unavailable checks `PASS`.

Vendor/library sources: [Autodesk DXF import/export](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-LT/files/GUID-11AEFE3C-D05A-45C3-8604-7B6A594440F3.htm), [Autodesk AUDIT/RECOVER](https://help.autodesk.com/view/ACADWEB/ENU/?caas=caas%2Fsfdcarticles%2Fsfdcarticles%2FOptimizing-the-AutoCAD-drawing-file-Purge-Audit-Recover.html), [Autodesk viewport failures](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Objects-drawn-in-model-space-are-not-visible-or-are-only-partially-visible-in-layout-in-AutoCAD-products.html), [Autodesk Core Console](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-use-the-AutoCAD-Core-Console.html), [ezdxf limitations](https://ezdxf.readthedocs.io/en/stable/introduction.html), [ezdxf XREF interoperability](https://ezdxf.readthedocs.io/en/stable/xref.html).

**Status:** Both items are researched/spec'd but remain unimplemented; no native AutoCAD session or write-capable agent transaction test has been performed in this research update.

## Execution phases and acceptance gates

### Phase 1 — Read-only revision dependency/coordination index (started)

- Baseline and proposed building specifications; compare stable opening, wall, room and level IDs.
- Emit machine-readable changed fields, impacted indexed sheets and affected schedules.
- Let authored sheet records declare `references` e.g. `{"openings":["W01"],"walls":["E1"]}` for cross-level sections or details.
- Compare **all** window schedule fields, not width alone; flag duplicate IDs and stale revision/title blocks.
- Never claim comprehensive 40-sheet coverage: unindexed PDFs, sections/elevations or hand markups remain UNKNOWN.
- Gate: positive and negative tests for changes to window width, height, sill, type, wall, and sheet revisions.

Command (stdlib-only, **does not edit** the input project):
```bash
python3 skills/architectural-drawing-generation/scripts/revision_impact.py before.building.json after.building.json --out impact.json
```

Output is a **review queue, not certification**. Downstream hosts or drawing-specific readers must verify that geometry and annotation really match.


Optional **Gridline Read-Only MCP** integration (MCP SDK **v2**, Python 3.11+):

```bash
python3 -m pip install 'mcp>=2,<3'
export GRIDLINE_MCP_PROJECT_ROOT=/absolute/path/to/your/architectural-project
python3 skills/architectural-drawing-generation/scripts/gridline_mcp.py
```

On POSIX hosts with `O_NOFOLLOW` and descriptor-relative opens, MCP JSON inputs are read from pinned regular-file descriptors with a 5 MB read limit, preventing a concurrent symlink replacement from redirecting reads outside the authorized root. The Windows/unsupported-host fallback validates and bounds paths but is **not race-proof**; keep its project directory trusted and non-writable by untrusted processes. A pair of independently opened JSON files is not a transactional snapshot.

Configure the MCP client to launch that script by its **absolute path** with a Python environment containing the v2 SDK, using local **stdio** transport. For example, a client's generic `mcpServers` format, if supported:

```json
{
  "mcpServers": {
    "gridline-review": {
      "command": "/absolute/path/to/python-with-mcp",
      "args": ["/absolute/path/to/Gridline/skills/architectural-drawing-generation/scripts/gridline_mcp.py"],
      "env": {
        "GRIDLINE_MCP_PROJECT_ROOT": "/absolute/path/to/your/architectural-project"
      }
    }
  }
}
```

This is a **Gridline-owned local review server**, not the Autodesk AutoCAD or Revit MCP server. It exposes only `compare_gridline_revisions` and `get_gridline_capabilities`; it cannot write model files or use arbitrary shell commands. It refuses to start without an explicit project root; input file paths must resolve under that root, preventing symlink escapes. It does not connect to any native CAD/BIM application. The client configuration keys vary by provider; verify their official documentation.

Official MCP Python SDK v2: https://py.sdk.modelcontextprotocol.io/

### Phase 2 — IFC/IDS local validation gate

- For an IFC export: validate syntax and IFC schema (and where supported the EXPRESS rules) using the `ifcopenshell` validation tools or a self-hosted buildingSMART validator.
- Separately run IfcTester against supplied, version-controlled project IDS requirements, and report pass/fail per requirement.
- Preserve schema version (IFC2X3, IFC4, IFC4.3 as supported), GUIDs, model revision, coordinate reference, units, source hashes, software/validator version and structured issues.
- Block release on parser/schema errors, failed mandatory IDS checks, and missing required validators. Report geometry / clashes / code compliance as **NOT CHECKED** until separately validated.
- Test against known-valid and deliberately defective IFC fixtures, including invalid schema/entity, missing property, incorrect spatial assignment and GUID changes.
- Gate: deterministic nonzero exit codes, JSON reports and reproduced failures. Never upload production IFC externally without project-owner authorization.

Sources:
- IFC official schema: https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/
- buildingSMART validation: https://dev.validate.buildingsmart.org/
- Local IfcOpenShell: https://docs.ifcopenshell.org/ifcopenshell-python/validation.html
- Project IDS with IfcTester: https://docs.ifcopenshell.org/ifctester.html

### Phase 3 — MCP/native AEC tool adapters (read-only first)

| Host | Verified connection surface | Important constraint / next adapter |
| --- | --- | --- |
| **AutoCAD / Civil 3D** | Official Autodesk AutoCAD/Civil 3D MCP tech preview; native AutoCAD .NET/ObjectARX/AutoLISP; APS cloud Automation | As documented, native preview currently runs **inside Autodesk Assistant on Windows**; AutoCAD exposes read/analysis, Civil 3D includes edit tools. Do not assume arbitrary external MCP clients can connect or that read-only tools can modify AutoCAD. Build a supported local bridge only after confirming the client's transport and user authorizations. |
| **Revit** | Autodesk Revit 2027.2 Public MCP Server via local STDIO, read/write/experimental choices; Revit .NET/APS AEC Data Model | A real Windows Revit host and add-on are required. Default to **read-only** server; writing needs separate explicit approval, transaction boundaries and rollback/undo. |
| **Rhino / Grasshopper** | Rhino.Compute REST geometry; Rhino.Inside.Revit on Windows; RhinoCommon/Grasshopper native scripting | Rhino.Compute is a geometry service, **not necessarily a native MCP server**. A Gridline MCP wrapper must authenticate the underlying service and limit calls; licensed host and deployment requirements apply. |
| **Archicad** | Graphisoft JSON Automation API over loopback HTTP and official Python connection | Uses local ports and requires running host. Verify which commands can read/write; do not expose loopback to untrusted clients. |
| **Blender** | Official `bpy` Python API (local add-on or headless Blender script) | A bounded MCP wrapper can expose allowlisted actions (inspect, build sample scene, render, export); **never** offer unrestricted Python evaluation by default. |
| **FreeCAD** | Native Python/document APIs and file exchange | Build a local sandboxed adapter, verify version, and use copied documents/transaction boundaries. |
| **IFC / openBIM** | IfcOpenShell / IfcTester local Python, BCF issue interchange | Prefer pure local deterministic validators before any hosted API. |

Additional authoritative references:
- Autodesk MCP index: https://help.autodesk.com/view/ADSKMCP/ENU/
- Autodesk AutoCAD/Civil3D: https://help.autodesk.com/view/ADSKMCP/ENU/?guid=ADSKMCP_AutoCADCivil3DMcp_autodesk_autocad_civil_3d_mcp_html
- Autodesk Revit: https://help.autodesk.com/view/ADSKMCP/ENU/?guid=ADSKMCP_RevitMcp_revit_mcp_server_html
- Rhino.Compute: https://developer.rhino3d.com/guides/compute/compute-faq/
- Archicad JSON: https://archicadapi.graphisoft.com/JSONInterfaceDocumentation/
- Blender API: https://docs.blender.org/api/4.5/

**MCP connector protocol requirements:** capability discovery with supported host/version, `read` vs `write` permission separation, user-scoped resources, model/drawing ID and revision, dry-run change sets, user approval, backups / undo, timeouts and output size limits, audit logs, no credential exfiltration, and post-edit native readback. Tool failures are never silently converted to success.

### Phase 4 — Coherent 2D → editable 3D pipeline

1. Prefer authoritative measured 2D geometry (room boundaries, wall centerlines, opening types and dimensions) from an editable DXF/BIM spec.
2. Validate topology (closed boundaries, wall joins, nonoverlapping openings), units and levels before extruding.
3. Create walls/doors/windows with stable IDs; export a reproducible neutral scene (e.g. glTF) for **visual review**; only export IFC after adding spatial/semantic BIM data and passing Phase 2.
4. Use Rhino.Compute/Grasshopper, Blender, FreeCAD or native Revit/Archicad as backends based on actually detected host capabilities.
5. After a revision, regenerate incrementally and verify geometric quantities / opening positions against the authoritative spec.

**3D appearance ≠ coordinated BIM**. A mesh or Gaussian splat is not a substitute for IFC entities, layers, element properties or editable architectural geometry.

### Phase 5 — Scans and annotations (research/experimental)

- Pipeline: page rectification → calibration from user-supplied dimensions/scale → line/arc detection → candidate walls/openings → OCR/markup separation → confidence scoring → editable 2D review → 3D/BIM conversion.
- Mixed scans and hand annotations are **untrusted input**. Flag overlaps, overwritten notes, missing scale, unknown wall types and uncertain symbols; never invent missing dimensions.
- Benchmark with consented redacted examples: vector PDFs, 300 DPI scans, damaged scans, handwritten revisions, misregistered pages and variant symbol conventions.
- Explicit human sign-off gates precede geometry and IFC export. Evaluate false negatives (missed changed dimensions) more heavily than false positives.

## Near-term evaluation protocol

- **Accuracy:** precision and recall of affected sheet/schedule IDs; report missed references and uncertainty, not just apparent successes.
- **IFC:** schema-valid count, IDS requirement success, GUID stability, unit/coordinate integrity, and client-app import roundtrip on a representative sample.
- **Host adapters:** discovery works, read-only mode cannot write, permissions are respected, unauthorized action rejected, dry-run/undo available and confirmed on a licensed application.
- **3D:** errors in dimensions/opening locations and mesh watertightness / BIM semantic preservation, not attractiveness of renders.
- **Humans:** architectural reviewer signs off, with time-to-review and false negative rates recorded.

**Not yet done:** real application sessions, native Autodesk MCP connections, schema/IDS integration tests, geometry/IFC generation, and scanned image reconstruction. These are separate deliverables, not implied by the Phase 1 tooling.
