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
- `verification.json`: independent Blender reopen of .blend and import of .glb, recording IDs and sorted dimensions; positions are checked but not recorded in this baseline evidence (PR #25 improves readback).
- `receipt.json`: source/spec hash, artifact hashes for model.blend, model.glb and verification.json (not scene.json in this baseline), host version, supported element count and explicit unverified list.

The renderer does not infer roofs, slabs, foundations, stairs, furniture, wall intersection topology, detailed door/window construction, structure, MEP or materials from the existing 2D source. The walls are split into solid segments to leave hosted opening gaps. Door leaves and glazing are illustrative boxes. The output is a **conceptual 3D source model** with editable Blender mesh geometry, not a fully parametric native BIM object system.

Native readback checks object counts, IDs, positions and box dimensions. It does not guarantee joined/manifold solid geometry, material parity, complete UV/texture delivery, correct architectural corner junctions or application compatibility beyond the actually exercised Blender 5.2.3 import/export paths.

## Image reference fidelity is a future, evidence-gated task

For high-detail reconstruction, Gridline must capture an image inventory and compare each modeled element to the original reference: source image and consent; camera/projection estimate; visible facade volumes; storeys; roof/profile; fenestration positions and proportions; materials; landscape/context; ambiguous or occluded sides; and source-backed measured dimensions. A single perspective photo generally cannot determine hidden rooms, precise measurements or actual materials. Require floor plans, additional views, survey/site geometry or user confirmation when needed; never silently invent detail and mark it verified. Track every observable feature with a source region, confidence, target Gridline element and verification outcome. Render matching camera views and ask human reviewers to confirm discrepancies; never substitute visual similarity for dimensional or BIM validation.

## AutoCAD on macOS is a separate bridge

Autodesk's AutoCAD for Mac exposes **AutoLISP** and **ObjectARX** interfaces, with different capabilities from Windows .NET/ActiveX and from AutoCAD LT for Mac. Follow official version-matched Autodesk API documentation and validate actual host installation before developing a bounded LISP/DXF/DWG roundtrip on a disposable drawing. See [AutoCAD programming interfaces](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Customization/files/GUID-E6429154-36DF-4D84-8ABC-9FCA15B66158.htm).

The maintainer's Mac currently has `~/Downloads/Autodesk_AutoCAD_2027.0.1_macOS.dmg` but AutoCAD itself was **not detected as installed** during this discovery. Downloaded installer is not an available host. The user must complete official installation and licensing (and grant any OS permissions necessary) first. Do not use unofficial unrestricted CAD MCP servers to bypass that gate.

## Next gates

1. Approval-bound semantic project revision state and constraints [#15](https://github.com/MakeItEzzz555/Gridline/issues/15).
2. Authenticated, restricted native adapters [#12](https://github.com/MakeItEzzz555/Gridline/issues/12); this prototype is callable through the local CLI, **not MCP**.
3. More accurate architectural topology, level/slab/roof intent, material recipes, reference-image comparison and real exports [#13](https://github.com/MakeItEzzz555/Gridline/issues/13).
4. True IFC semantic checks [#11](https://github.com/MakeItEzzz555/Gridline/issues/11), DXF/DWG native AutoCAD acceptance [#16](https://github.com/MakeItEzzz555/Gridline/issues/16), and independent professional checks.

Never claim a universal, bugless or construction-ready model. A real loaded 3D scene is useful evidence, but not professional design approval.
