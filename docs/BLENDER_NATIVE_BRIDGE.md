# Local Blender native model bridge (first proof)

**Status:** Bounded local 3D modeling proof. The `scripts/blender_native.py` tool can generate a new native Blender scene and glTF binary from Gridline's existing `building-spec.v1` wall/opening/level subset. This is **not** image-to-3D, photoreal rendering, complete architectural detailing, safe authoring of existing projects, IFC delivery, a Blender MCP server, or CAD/BIM certification.

## Current host and usage

On the maintainer's Mac, Blender **5.2.3 LTS** was detected at `/Applications/Blender.app/Contents/MacOS/Blender`. A model and a GLB were built and separately reopened/read back on this installed host using `skills/architectural-drawing-generation/references/example-house.building.json`. This is a sample proof, not an independently reviewed production deliverable.

```sh
python3 scripts/blender_native.py doctor
python3 scripts/blender_native.py build \
  skills/architectural-drawing-generation/references/example-house.building.json \
  /path/to/NEW-output-directory
```

The destination **must not exist**. For installed portable Gridline skills, run `python3 scripts/blender_native.py doctor` and `build` **from the installed architectural-drawing-generation skill directory**; it includes the worker and building-spec validator. The repository-level launcher above is only a convenience.

Only an explicitly provided NEW output directory is used; Blender is started in background factory mode. No Blender preferences or existing model are changed. The script does not install a plugin or modify Codex's global MCP configuration. Optional `--blender /path/to/Blender` selects a trusted executable (verify its publisher and version first). A failed build returns nonzero and does not advertise a successful model.

Result:
- `model.blend`: Blender source scene with named mesh objects and retained `gridline_id`, levels and opening-host metadata.
- `model.glb`: glTF scene for viewers or import into supported downstream 3D applications.
- `scene.json`: exact typed geometry inputs, transformed from millimetres to metres.
- `verification.json`: independent native Blender and GLB readbacks with IDs, host/source-unit metadata, materials, world-space mesh bounds, measured per-object world-corner error and documented tolerance.
- `receipt.json`: source-spec hash, checksums for model.blend, model.glb and verification.json, separate scene_sha256 (for scene.json), adapter and worker source hashes, host version, format statuses and known unverified scope.

The renderer does not infer roofs, slabs, foundations, stairs, furniture, detailed door/window construction, structure, MEP or materials from the existing 2D source. Source wall occupancy boxes are combined into continuous orthogonal boundary meshes, subtracting declared opening envelopes through the host thickness. Compatible walls share a mesh per level/material/explicit joint group; `gridline_source_ids` maps every original wall ID, and opening members keep their original host IDs. `scene.json` retains the source boxes; `receipt.json` distinguishes their count from the exported mesh count. Mixed oblique joins fail explicitly. No gap is snapped shut. Door leaves and glazing are illustrative boxes. The output is a **conceptual 3D source model** with editable Blender mesh geometry, not a fully parametric native BIM object system.

Native readback checks both formats for object counts/names, Gridline IDs/kind/host/source units, material assignment and world-space mesh corners, including rotation and parent transforms. Native scene units must be metric at scale 1. Tolerances are 0.25 mm (.blend) and 1 mm (GLB); these are fixture comparison limits, not construction tolerances. Union-boundary checks additionally validate face winding, closed edges, vertex fans, orphan vertices and signed volume against an independent analytic sweep of source occupancy minus apertures (0.01 mm readback weld; volume threshold max(0.001 m³, expected volume × 1e-5)). Raw GLB triangles are checked before Blender import can sanitize them. Coordinate construction rounds to 0.0001 mm in a common rotated orthogonal basis; this is not a gap-closing tolerance. This does not establish construction intent, material parity, complete UV/texture delivery or compatibility beyond the exercised Blender 5.2.3 paths. See [measured villa repair](VILLA_TOPOLOGY_REPAIR_2026-10-24.md) for coverage and exclusions.

## Image reference fidelity is a future, evidence-gated task

For high-detail reconstruction, Gridline must capture an image inventory and compare each modeled element to the original reference: source image and consent; camera/projection estimate; visible facade volumes; storeys; roof/profile; fenestration positions and proportions; materials; landscape/context; ambiguous or occluded sides; and source-backed measured dimensions. A single perspective photo generally cannot determine hidden rooms, precise measurements or actual materials. Require floor plans, additional views, survey/site geometry or user confirmation when needed; never silently invent detail and mark it verified. Track every observable feature with a source region, confidence, target Gridline element and verification outcome. Render matching camera views and ask human reviewers to confirm discrepancies; never substitute visual similarity for dimensional or BIM validation.

## AutoCAD on macOS is a separate bridge

Autodesk's AutoCAD for Mac exposes **AutoLISP** and **ObjectARX** interfaces, with different capabilities from Windows .NET/ActiveX and from AutoCAD LT for Mac. Follow official version-matched Autodesk API documentation and validate actual host installation before developing a bounded LISP/DXF/DWG roundtrip on a disposable drawing. See [AutoCAD programming interfaces](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Customization/files/GUID-E6429154-36DF-4D84-8ABC-9FCA15B66158.htm).

On 2026-10-24, AutoCAD 2027 for Mac was installed/running (bundle 26.0.60.171). A disposable sample DXF was visibly opened with font substitutions. Independent license entitlement, metadata inspector execution, AUDIT, edit/plot and DWG↔DXF roundtrip remain unverified. A security dialog awaiting operator approval is not a successful native query. No AutoCAD MCP connection is claimed.

## Next gates

1. Approval-bound semantic project revision state and constraints [#15](https://github.com/MakeItEzzz555/Gridline/issues/15).
2. Authenticated, restricted native adapters [#12](https://github.com/MakeItEzzz555/Gridline/issues/12); this prototype is callable through the local CLI, **not MCP**.
3. More accurate architectural topology, level/slab/roof intent, material recipes, reference-image comparison and real exports [#13](https://github.com/MakeItEzzz555/Gridline/issues/13).
4. True IFC semantic checks [#11](https://github.com/MakeItEzzz555/Gridline/issues/11), DXF/DWG native AutoCAD acceptance [#16](https://github.com/MakeItEzzz555/Gridline/issues/16), and independent professional checks.

Never claim a universal, bugless or construction-ready model. A real loaded 3D scene is useful evidence, but not professional design approval.


## Readback hardening work package (2026-10-24)

Dependent on **unmerged PR #23**, reviewed head `72f3d3a1ef4e9b1cce5eeafa05b3d32c0fc7e645`. Independent read-only review found orientation/parenting false PASS, omitted GLB identity validation, unbounded source allocation and path-based publication races. Scope is those defects, not higher-detail modeling. Reserved identity metadata can no longer be overwritten by an opening's semantic kind; the real native test exposed that collision.

Source reads pin directory components, reject symlinks/special files, and consume at most 1 MiB + 1 bytes. The CLI uses the explicitly selected local source; it is not an untrusted MCP endpoint. Child processes disable embedded autoexecution, use a fixed worker and propagate Python exceptions as nonzero exits. Publication pins directory descriptors and uses exclusive no-follow file creation; a swapped path cannot redirect artifact writes. `receipt.json` is written last. Partial new directories can remain on failure and must be quarantined; this is not atomic directory publication or a last-good revision manager. No existing output directory is replaced.

Historical PR #25 acceptance on Blender 5.2.3 LTS generated and reopened 42 meshes / 17 wall-opening elements; the topology repair now exports 11 meshes from those same 42 source boxes. Four real disposable corruption cases (90-degree rotation, parent displacement, GLB identity deletion and missing material) were rejected. The exact local command is:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --disable-autoexec --python-exit-code 1 --python tests/blender_native_acceptance.py \
  -- /absolute/generated-package
```

The dedicated acceptance script only loads the generated fixture and creates owned temporary corrupted copies. Original native files remain unchanged. Eleven deterministic bridge tests run without Blender; this native script runs separately and is not a fake CI host test. See `docs/BLENDER_HARDENING_EVIDENCE.json` for measured errors, hashes and declared coverage. This historical receipt predates the topology repair. Material shader appearance, textures, source-photo fidelity and general architectural correctness remain unverified; current bounded topology evidence is linked above. No new roof, floor, stair or other design dimensions are invented in this package.
