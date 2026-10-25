# Historical package A source review

This records the source-only package A checkpoint. Its blocked/not-tested statements describe that earlier checkpoint. See [current integration](ARCHIMESH_INTEGRATION.md) for subsequent implementation and acceptance.

# Optional ARCHIMESH: source review and read-only doctor

Issue [#45](https://github.com/MakeItEzzz555/Gridline/issues/45), first separate package A. Based on released **0.8.1**, source `0e87aa52922b164235ccf277edead851b9acc000`. This adds discovery and source evidence; component adapters, installation, native/GLB acceptance and asset downloads remain blocked or not tested. Stable provider versions remain 0.8.1; this is an unreleased feature branch.

## Run the doctor

From the repository:

```sh
python3 scripts/archimesh_doctor.py
python3 scripts/archimesh_doctor.py --addon-source /absolute/path/to/archimesh
python3 scripts/archimesh_doctor.py --blender /absolute/path/to/blender
```

From an installed drawing skill, use `python3 scripts/archimesh_doctor.py` in its own directory. No third-party Python dependency is needed. The explicit source option inventories an extracted or installed directory; it does **not** assert that the source is installed. Default discovery checks standard versioned user profiles (legacy `scripts/addons/archimesh` and `extensions/<repository>/archimesh`) on macOS, Linux and Windows. Custom/system installs need an explicit source path. `NOT_FOUND_IN_DEFAULT_PATHS` is a scoped finding, not a whole-disk absence claim. Permission errors and unsafe paths return structured `BLOCKED` and exit 1.

The tool never imports an add-on, enables it, writes Preferences, opens a user model, or connects to an existing Blender window. With a trusted Blender executable it starts a separate factory/background process, disables automatic execution, selects offline mode and private temporary resources, and verifies startup only. Offline mode is Blender's setting, **not** an operating-system sandbox. The caller must trust the executable. No arbitrary Python expression/script option is exposed. Exit 0 means the inventory completed, including a missing dependency; inspect `generation: BLOCKED`, `registration: NOT_TESTED`, and `geometry_acceptance: NOT_TESTED` rather than interpreting it as integration success.

Source reads reject symlinks, special files, files over 1 MiB and trees over 128 entries. An exact match to all 19 pinned files, with no extra files except ignored `__pycache__` directories, yields `SOURCE_VERIFIED`. Any missing/modified/extra file yields `UNVERIFIED` and version `UNKNOWN`. Matching source bytes neither authorizes execution nor clears licensing. The reference JSON is a factual hash/operator inventory, not upstream Python source. No GPL add-on code, ZIP, image or bytecode is shipped.

## Pinned source and compatibility

The [official extension](https://extensions.blender.org/add-ons/archimesh/) advertises **1.2.5**, Community maintenance, limited support, Blender **4.2.0+**, and **GPL-2.0-or-later**. Its manifest agrees; legacy `bl_info` still says Blender 3.0.0. Use the extension manifest as the advertised floor, not as proof of Blender 5 compatibility. The downloaded 323,488-byte ZIP SHA256 is `44745a86dd472e296e06cd45c511e002a1105512a73009cb0018c87611d18d87`, matching the official content-addressed link. See the portable [pin inventory](../skills/architectural-drawing-generation/references/archimesh-1.2.5.json).

The archived [Blender add-ons mirror](https://github.com/blender/blender-addons/tree/b42d68627734cb18af0e6f41537063984313a284/archimesh) is a distinct historical source; this implementation pins the extension ZIP, not an assumed identical mirror tree. A secondary 1.2.6/GPL3 listing is **not accepted as the official edition**: no authoritative matching release was verified. The reported marcoo releases URL returned a challenge page, so that channel remains **UNVERIFIED**.

The [Odhexe patcher](https://github.com/Odhexe/archimesh-1.2.5-blender5-fix/blob/35e6495802bcef6d5465bbff36e0148fac4c40ca/patch_archimesh.py), pinned at `35e6495802bcef6d5465bbff36e0148fac4c40ca`, uses regex substitutions for generator-membership/panel tests. It recursively rewrites Python files and creates `.bak` files; it is not a complete tested replacement release. Static inspection does not establish callback, geometry, material, export or Blender-version compatibility. It was **not executed**, installed, or adopted, and modified source would fail the official pin. Its exact file hash is recorded in [source.json](evidence/archimesh-doctor/source.json).

## Actual Blender 5.2.3 evidence

**TESTED_BLENDER_5_2_3, PARTIALLY_SUPPORTED:** in a new factory/background/offline process with private temporary resource directories, the hash-verified official source imported and registered. All 14 mesh generator names were present. Default door, rail window and kitchen operators returned `FINISHED`, producing 6, 7 and 5 mesh objects respectively. These counts are diagnostic observations, **not** evaluated geometry acceptance.

Both door and rail-window panel polls returned **false** while their RNA generator collections were populated. This reproduces a panel gating defect in this narrow context; it does not prove every interactive viewport state. No patch was applied. Dimension callbacks, panels in a live viewport, evaluated meshes, units/transforms, normals, UVs, material fidelity, saved `.blend` and GLB reimport remain **NOT_TESTED** for ARCHIMESH. The existing Gridline geometry validators are unchanged and cannot be assumed to accept these foreign meshes.

The native research harness stayed outside the repository, explicitly GPL-labelled, and ran only the reviewed official source in a disposable process. No extension was installed/enabled in a user profile; no existing native session or `.blend` was controlled. The shipped doctor does **not** execute this research harness or claim its observations as a fresh per-install compatibility result. See [native probe](evidence/archimesh-doctor/native-probe.json), [default discovery](evidence/archimesh-doctor/doctor-default.json), [source inspection](evidence/archimesh-doctor/doctor-source.json), and [external receipt paths/hashes](evidence/archimesh-doctor/source.json). The harness/log remain in the external research directory for reproduction; they are not portable installed-skill payloads.

## Typed capability and side-effect inventory

These are **SOURCE_VERIFIED interfaces**, not Gridline request schemas or supported adapters. Names below are under `bpy.ops.mesh.`; floats follow upstream units/context and need independently measured conversion. Object property collections are edited after creation, often triggering destructive child-mesh rebuilding. Direct function calls into internal helpers are not stable public APIs.

| Component / operator | Typed source controls (representative) | State / side effects and unsupported cases |
|---|---|---|
| Room `archimesh_room` | `RoomGenerator`: `room_height`, `wall_width`: float; `wall_num`: int; `walls`: collection with `w`, `r`: float, `curved`: bool | NOT_TESTED. Wall/baseboard/floor/ceiling/shell meshes; no Gridline wall replacement or topology guarantee. |
| Door `archimesh_door` | `DoorObjectGenerator`: `frame_width`, `frame_height`: float 0.25–10; `frame_thick`: float 0.05–0.50; `openside`, `model`, `handle`: enum | PARTIALLY_SUPPORTED: default smoke only; panel poll false. Parent empty, frame/leaf/handle and hole-control children; dimensions are frame dimensions, not certified clear opening. |
| Rail window `archimesh_window` | `WindowObjectGenerator`: `width`, `height`, `depth`: float; `opentype`: enum; `sill`, `blind`, `blind_box`: bool | PARTIALLY_SUPPORTED: default smoke only; panel poll false. Parent/leaf/glass/sill/blind/control meshes; callbacks recreate children; no host-aperture or glazing-performance guarantee. |
| Panel window `archimesh_winpanel` | `WindowPanelGenerator`: `gen`, `yuk`: int pane/row counts; `gnx0…7`, `gny0…4`: int sizes; `UST`, `DT2`, `DT3`: enum | NOT_TESTED. Uses upstream pane/frame sizing conventions; curved/sloped options are not bounded Gridline windows. |
| Cabinet `archimesh_kitchen` | Operator `depth`, `height`, `thickness`: float; `cabinet_num`: int; `cabinets`: collection; each `sX`: float, `dType`: enum, `sNum`, `dNum`: int | PARTIALLY_SUPPORTED: default smoke only. Multiple carcass/door/handle/baseboard/counter meshes and SKU metadata; not BIM furniture semantics. |
| Shelves `archimesh_shelves` | `depth`, `height`, `thickness`, `sthickness`: float; `shelves_num`: int; `shelves`: collection, `sNum`: int | NOT_TESTED. Repeated assemblies; no structural/storage capacity checks. |
| Column `archimesh_column` | `rad_top`, `rad_mid`, `rad_bottom`, `col_height`: float; `crt_array`: bool; `array_num_x`, `array_num_y`: int | NOT_TESTED. Bases/tops/arcs/arrays and modifiers; no structural verification. |
| Stairs `archimesh_stairs` | `step_num`: int; `max_width`, `depth`, `height`, `thickness`: float; `model`: enum; `curve`: bool | NOT_TESTED. Step/curve construction; no egress, headroom, riser or tread compliance. |
| Roof `archimesh_roof` | `roof_width`, `roof_height`: int tile counts 1–100; `roof_angle`: float 0–70; `roof_scale`: float; `model`: enum | NOT_TESTED. Tile patches/arrays/solidify, not a complete authoritative roof or structural system. |
| Books `archimesh_books` | `width`, `depth`, `height`: float; `num`: int; `rX`, `rY`, `rZ`, `rC`: float | NOT_TESTED. Randomized props; no deterministic source IDs or dimensions assumed. |
| Lamp `archimesh_light` | `base_height`: float; `base_segments`, `base_rings`: int; `preset`: enum; `energy`, `opacity`: float | NOT_TESTED. Generated bases/shades and optional subdivision/materials; no photometric/electrical acceptance. |
| Japanese curtain `archimesh_japan` | `width`, `height`: float; `num`, `palnum`: int; `open01…05`: float | NOT_TESTED. Rails/panels/curves/fabric; no material/UV export guarantee. |
| Roller `archimesh_roller` | `width`, `height`: float; `crt_mat`: bool | NOT_TESTED. Rail/sides/fabric/curve; display prop only. |
| Venetian `archimesh_venetian` | Object collection `width`, `height`, `depth`, `angle`: float; `ratio`: int | NOT_TESTED. Slats/cords and update callbacks; no clearance acceptance. |

Import-time registration already creates several `bpy.types.Object` collections; importing is therefore **not** read-only. Add-on `register()` adds operators, panels, menu hooks, Scene/WindowManager properties. Generators change selection, active object, cursor-relative object placement, object mode, mesh data, parenting and materials. Many use context-dependent `bpy.ops`, edit mode, UV unwrap, merge/recalculate operations, modifiers and renderer-name gates. Background default smoke cannot validate every parameter path. `draw()` paths use `space_data.local_view`; they require a viewport context.

`object.archimesh_cut_holes` creates boolean cuts and `object.archimesh_pencil_room` derives rooms from drawing context. Both are **BLOCKED** for Gridline host editing. Room import/export and kitchen inventory operators perform file I/O and are not exposed. Gridline retains authority over wall joins, openings, element IDs, dimensions and source state; no shell modifier or existing-project write is authorized by this doctor. Issues #15 and #33 remain in force.

## Licensing and separate assets

**NEEDS_LICENSE_REVIEW:** the [Blender FAQ](https://www.blender.org/support/faq/#using-blender-8) says distributed Python scripts using Blender's API must be GPL-licensed; its external-software exception requires no Blender API calls. MIT's compatibility with GPL is not a blanket permission to redistribute a combined add-on solely as MIT. This package adds no `bpy` calls and copies no GPL implementation. The existing MIT-repository `blender_native_worker.py` uses `bpy`; its distribution/combined-work boundary needs explicit qualified license review before new API adapters or repackaging. No whole-repository license change is made or implied.

The FAQ describes ordinary `.blend` output as user-owned, with caveats for embedded scripts. That is not universal clearance for third-party images, models, textures, marks or imported assets. ARCHIMESH has procedural shader helpers (diffuse/glass/glossy/brick/fabric) and **one** bundled `images/fabric_diffuse.png`; it is not a PBR/8K asset catalog. This package redistributes neither those helpers nor the image, and does not establish a separate image license.

A future **separate opt-in** backend may use the [Poly Haven API](https://polyhaven.com/our-api). Its assets are CC0, while the live service requires visible Poly Haven attribution and a unique User-Agent. Recheck full service terms before implementation. The [Poly Haven Lite asset extension](https://extensions.blender.org/asset-libraries/poly-haven/) advertises Blender 5.3+, so it is not accepted on this 5.2.3 host. API content would need independent import tests, explicit download consent, per-asset URL/license/hash, bounded cache/archive handling, UV/PBR texture packing and GLB reimport validation. No Poly Haven assets were downloaded. ambientCG and sprites are outside this package.

## Next gate and review

Package B requires a reviewed licensing/distribution decision and an explicitly approved external add-on source/version before any adapter executes it. Then implement bounded door/window/cabinet request data, new-scene-only generation, and independent evaluated `.blend`/GLB acceptance with corruption tests. The current smoke results do not satisfy that gate or close #45. Installation from Blender Preferences/Get Extensions or an official verified ZIP requires the user's approval in the chosen profile; this PR performs neither step.

One coding agent performed the bounded source/security/architecture/Ponytail self-review. No independent reviewer, counsel, or professional acceptance is implied. Apple Design's relevant nonvisual guidance is clear feedback and honest failure states; no UI, visual redesign or animation work applies. Provider mirrors and pinned manifests remain coordinated. Test commands/results are recorded in the evidence directory; external provider token/cache/cost receipts are unavailable, and no savings or benchmarks are claimed.
