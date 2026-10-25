# Optional ARCHIMESH components (unreleased)

Based on Gridline 0.8.1. This work adds bounded component recipes, disposable
Blender generation, a local signed proposal ledger and an opt-in texture cache.
The IFC adapter is under implementation and has **not passed engine acceptance**.
No stable release/version or completion of issues #13, #15 or #45 is claimed.
See the [historical source review](ARCHIMESH_SOURCE_REVIEW.md) for upstream pins,
operator inventory, reproduced panel defects and package A evidence.

## Supported boundary

The generator accepts reviewed data, copies the exact official ARCHIMESH 1.2.5
source into private temporary storage, starts an independent Blender 5.2.3
factory/background process, freezes evaluated meshes and independently reopens
native `.blend` and embedded GLB artifacts. It never installs an extension,
patches upstream source, changes Preferences or controls an existing window.
Blender offline mode is not an OS security sandbox; the executable and pinned
external code must be trusted. No unofficial compatibility patch is used.

The bounded recipes cover door frames/leaves, rail windows, panel windows,
cabinets, shelves, faceted columns, stairs, roof tile patches, books, lamps,
roller blinds, Venetian blinds and Japanese curtains. See `catalog` for exact
required parameters/ranges. Examples are synthetic test inputs, not construction
designs or safe defaults. Missing dimensions block validation.

Results are editable frozen meshes with source IDs and parent assemblies; they
are not working ARCHIMESH parametric panels or approved BIM families. Upstream
Blender 5.2 panel defects remain. Column subdivision is disabled to preserve the
requested radius, yielding a 12-sided faceted surface. Zero-area upstream
triangles are explicitly removed/counts recorded; nonzero surfaces are retained.
Stair tread thickness and frame/body thicknesses are explicit recipe inputs.
Each component uses one explicit material across its members: windows do not
retain an independently qualified transparent glazing shader. Columns preserve
the upstream open-ended display surface; they are not watertight structural solids.
Roof patches are decorative tiles, not a structural/weatherproof roof. Prop
recipes do not establish manufacturing dimensions, clearances, egress, glazing,
photometric or structural performance. Rooms, upstream auto-hole booleans,
animations, external GLB resources and live-host edits are unsupported.

## Choose and generate

From an installed `architectural-drawing-generation` skill directory (repository
paths have the prefix `skills/architectural-drawing-generation/`):

```sh
python3 scripts/archimesh_components.py catalog
python3 scripts/archimesh_components.py validate references/example-components.json
python3 scripts/archimesh_components.py build REQUEST.json NEW_OUT \
  --addon-source /absolute/reviewed/archimesh \
  --approve-addon-sha256 44745a86dd472e296e06cd45c511e002a1105512a73009cb0018c87611d18d87
python3 scripts/archimesh_components.py verify NEW_OUT \
  --expected-receipt-sha256 TRUSTED_PIN_FROM_BUILD_RESULT
```

Use the catalog as a data picker: select a kind, obtain every required size and
material value from the user/project source, and validate the complete request
before generation. Do not translate prose into executable Blender Python.
Explicit `schema: gridline-components.v1`, metre units, project/component/source
IDs, position, rotation, material ID/color/roughness/metallic and parameters are
required. A scene is bounded to 100,000 triangles and 64 MiB per published
artifact; exceeding a budget blocks publication. The panel-window fields explicitly name centimetres. Material IDs may
be reused only for identical properties. Requests contain 1–32 components.

Standalone requests use an empty `host_id`. Requests embedding `building-spec.v1`
use its existing millimetre schema and Gridline topology validation; component
placements remain metres. Hosted doors/windows must reference the actual opening
and wall and match exact dimensions, level, position and rotation. Unhosted props
in a building require `level_id`. The authoritative Gridline wall-union and
opening oracle remain in use; generated components replace only corresponding
closed preview slabs. No wall is cut by ARCHIMESH. See
`example-house.components.json` and `example-two-level.components.json`.

The new output directory contains `request.json`, `components.blend`,
`components.glb`, `meshes.json`, `verification.json` and the receipt published last.
Publication refuses existing paths. Build snapshots the exact consumed worker,
helpers, request, add-on and local textures. Source/state changes during generation
block publication. Verification pins the retained receipt, snapshots validated
bytes before native readback and does not rewrite published artifacts. Retain the
build-result receipt SHA256 separately: recomputing it after an untrusted change
is not an integrity check.

Readback checks inventory, source/host IDs, parents, root transforms, actual world
triangles/winding/corner normals, UVs, known PBR surface graphs, visibility,
modifiers, constraints, animation and source dimensions for supported anchors.
Position/UV tolerance is 1e-5; normal-component tolerance is 5e-5, separately
qualified against observed Blender import quantization. Canonical shell surfaces
are checked independently against occupied/void boxes. A passing readback does
not independently establish every upstream algorithm or arbitrary parameter
combination. `.blend` bytes may vary with Blender metadata; use geometry/source
checks, not an assertion of byte-identical native serialization.

## Signed local source state

`component_state.py DATABASE COMMAND` persists immutable revisions/proposals and
append-only events in SQLite. An owner key signs exact initialization/proposal
payloads with Ed25519; OpenSSL 3 is required. The product accepts public keys and
detached signatures only, never a private key or a signing command. Owner labels
alone cannot approve. Keep the signing key outside agent-controlled storage and
retain the trusted public-key fingerprint separately. This is key-holder proof,
not proof of a person's presence, professional approval or a hostile-OS sandbox.
SQLite database and executable storage must remain trusted.

1. `prepare-init REQUEST --owner OWNER --public-key PUBLIC.pem --payload-out PAYLOAD`
   produces the exact bytes for independent owner review/signing.
2. `init REQUEST --owner OWNER --public-key PUBLIC.pem --signature SIGNATURE`
   verifies the proof and exclusively publishes a new database.
3. `propose BASE_HASH PATCH.json --actor ACTOR --rationale TEXT --evidence TEXT
   --payload-out PAYLOAD` accepts whole-component replacements with unchanged
   identity/kind/host. It cannot add/delete elements or mutate the embedded building.
4. Independently review/sign the payload, then `approve PROPOSAL_HASH --owner OWNER
   --signature SIGNATURE`; `commit PROPOSAL_HASH` rechecks the signature and merges
   only nonconflicting changes under one immediate SQLite transaction.
5. `restore REVISION --actor ACTOR --rationale TEXT --evidence TEXT` creates another
   proposal requiring exact approval. `prepare-rejection PROPOSAL_HASH --payload-out
   PAYLOAD` supplies distinct rejection bytes; `reject ... --signature SIGNATURE`
   refuses subsequent commit. `inspect` reports the document and a bounded audit.

Same-target stale edits conflict; disjoint edits revalidate before merging;
commits are idempotent. `build --state-db DATABASE --owner-key-sha256 TRUSTED_KEY_PIN`
binds preview generation to the committed signed source and checks the head again
before publication. Preview geometry is never the canonical source.

This component ledger does **not** complete the general #15 building transaction
manager: arbitrary structural/wall edits, full drawing dependency impact and
Revit/AutoCAD live transaction/rollback acceptance remain gated. It does not grant
native-host write permissions. No agent is authorized to self-sign as the owner.

## Opt-in CC0 textures

`cc0_assets.py` supports Poly Haven **textures** only: exactly 1K JPG diffuse,
roughness and OpenGL-normal channels. It downloads no archive, model, HDRI, sprite
or add-on. No ambientCG backend is implemented. Pillow is required for image
validation/readback. Catalog requests use a Gridline User-Agent and preserve
Poly Haven attribution. Live service terms and individual asset provenance remain
part of source review; see [Poly Haven API](https://polyhaven.com/our-api).

```sh
python3 scripts/cc0_assets.py --help
```

The default is network-off. Catalog fetch is explicitly enabled and saved to a
new snapshot; query can use that offline snapshot. Plan creation records URLs,
CC0 license, provider, upstream lengths and MD5s. The download command itself requests network use and requires the exact approved
plan SHA256; limits are 8 MiB per
three-channel plan and four plans per generated scene. Only allowlisted HTTPS
hosts are accepted, including redirects. Verified JPEG dimensions/bytes, MD5 and
local SHA256 are rechecked on cache use. Downloads publish a new content-addressed
cache entry and never silently replace a damaged entry.

A textured component material supplies `asset_plan_sha256`, explicit
`uv_tile_size_m: [WIDTH, HEIGHT]`, white base color, roughness 1 and metallic 0.
Do not infer physical texture scale from an undocumented provider metadata unit.
Build uses `--asset-cache CACHE` offline, snapshots verified files, packs all images
in `.blend`/GLB, and checks native/imported graph connections and image pixels.
Provider/license/source/hash provenance survives in roots and receipts. Synthetic
fixtures test mechanics and must remain labelled synthetic; they do not prove
real public-source download acceptance. Real-asset acceptance is still pending.

## IFC and release gates

`component_ifc.py` is an unqualified implementation under test. IfcOpenShell is
optional and never automatically installed. Do not present its files as accepted
IFC until actual schema/EXPRESS, independent geometry, unit, stable GUID,
spatial/host/opening/filling, property/quantity and before/after checks pass with
explicit project requirements. Real client/IDS interoperability and human model
inspection are separate gates. PBR textures remain native/GLB; the IFC path maps
material identities and discloses that limit. Issues #13 and #15 remain open.

Portable consumed-source receipts and limits are recorded in
[evidence/archimesh-components](evidence/archimesh-components/development-status.json).
Current actual native evidence includes all 13 synthetic recipes, a hosted house,
a two-level fixture and synthetic embedded PBR readback. Adverse tests operate
only on private corrupted copies: 26 seeded faults were rejected after the
unchanged baseline passed. Tests are in `tests/components_native_acceptance.py`.
Final-head evidence, real CC0 acceptance, IFC engine acceptance, packaging,
provider mirror checks and CI must be completed before stable shipment.

## Distribution license

The external official GPL source/images/ZIP are not bundled. The original new
Blender API worker is explicitly GPL-2.0-or-later with corresponding source and
full license text. Existing MIT grants/notices are retained. The distribution is
mixed-license; see [portable licensing boundary](../skills/architectural-drawing-generation/references/BLENDER-LICENSING.md).
This is a documented redistribution choice based on primary Blender/FSF guidance,
not legal certification of every downstream combination. No user profile add-on
installation or professional/construction approval is implied.
