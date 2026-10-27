# Optional ARCHIMESH components and source-bound IFC4

Gridline 0.9.0 builds on released 0.8.1. Component generation is optional,
new-output-only and qualified on the observed macOS Blender 5.2.3 LTS host with the
exact official ARCHIMESH 1.2.5 source. It never installs/enables an extension in a
user profile, patches source or controls an existing window. See the
[historical source review](ARCHIMESH_SOURCE_REVIEW.md) for upstream provenance,
operator inventory and reproduced Blender 5.2 panel defects. The doctor remains
read-only inventory; exit 0 is not generation or licensing approval.

## Select a bounded recipe

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
material value from reviewed source, then validate. Never translate prose into
executable Blender Python or copy synthetic fixture dimensions into a real design.
Choose a persistent globally unique `project_id` for a real project (a UUID is suitable);
keep the human project number in `building.project.number`. GUID stability is scoped
to that project namespace. Synthetic example IDs are not federation identities.
All 13 recipes are exercised in actual native/GLB and IFC acceptance:

| Kind | Meaning and independent measurement scope |
|---|---|
| Door, rail window, cabinet | Source frame/body anchors checked against explicit width/depth/height. Cabinet fronts and window hardware may extend outside the nominal body/frame. |
| Shelves | Explicit body/board sizes and shelf count; frozen evaluated surface readback. No storage-load claim. |
| Column | Radius and height measured; 12-sided, open-ended display surface with size-changing subdivision disabled. No watertight structural-solid claim. |
| Stairs | Width, total run and rise measured against count/tread/riser inputs; tread thickness explicit. No headroom, egress or code clearance claim. |
| Roof | Bounded decorative tile array/angle/scale/thickness controls; evaluated surface readback. No structural/weatherproof roof. |
| Books, lamp | Bounded source controls and evaluated surfaces. No furniture schedule, photometry or electrical acceptance. |
| Roller, Venetian, Japanese curtain | Nominal source controls; fabric/slat/rail/hardware assemblies may exceed nominal opening dimensions. No clearance/fabric-performance claim. |
| Panel window | Explicit centimetre pane controls; assembly includes upstream frame sizes. No glazing-performance claim. |

`schema: gridline-components.v1`, metre coordinates, project/component/source IDs,
position, rotation, material ID/color/roughness/metallic and every catalog parameter
are required. Counts/scales are dimensionless; `_deg` and `_cm` fields name their
units. These are bounded recipes, not support for every upstream option or proof
of every parameter combination. Validation rejects unknown fields and invalid
ranges/types/relationships. Scenes are limited to 32 components, 100,000 triangles
and 64 MiB per published artifact; excess blocks publication.

Results are editable frozen meshes with source IDs and parent assemblies, not
working ARCHIMESH parametric panels or approved BIM families. One explicit material
is used per component, including opaque windows. Zero-area upstream triangles are
explicitly removed/counts recorded; nonzero source surfaces are retained.
Rooms, auto-hole booleans, animations, external GLB resources, original-project
writes and interactive panel repair are not exposed by the component generator.
Blender offline mode is not an OS sandbox: executable and pinned source are trusted.

## Building and artifact bindings

Standalone requests use empty `host_id`. An embedded `building-spec.v1` retains its
millimetre schema; component coordinates remain metres. Hosted doors/windows must
reference an actual opening/wall and match its dimensions, level, position and
rotation. Unhosted building props require `level_id`. Canonical wall unions and
opening occupied/void checks remain authoritative; components replace only matching
closed preview slabs. ARCHIMESH never cuts a source wall. Simple room polygons,
global source identities and nonoverlapping stacked level ranges are checked;
complex overlapping storey models are outside this bounded adapter.

See `example-house.components.json` and `example-two-level.components.json`.
A new output contains `request.json`, `components.blend`, `components.glb`,
`meshes.json`, `verification.json` and a receipt published last. Existing paths
are never overwritten. Interrupted/incomplete publication cannot be accepted as
valid. Builds snapshot consumed add-on/runtime/request/texture bytes. Source or
canonical-head changes during generation prevent publication.

Readback checks complete object/mesh inventory, source/host IDs, parents, root
transforms, world triangles/winding/corner normals, UVs, known active PBR graphs,
visibility, modifiers, constraints, animation, supported anchors and shell geometry.
Position/UV tolerance is 1e-5; normal-component tolerance is 5e-5 from measured Blender
import quantization. Public verification uses pinned private byte snapshots and
preserves published artifacts. Retain receipt hashes separately from the output;
recomputing a pin after an untrusted change is not an integrity check. Source
approvals and receipt pins do not provide an OS sandbox or remote publisher identity.

## Signed canonical source revisions

`component_state.py DATABASE COMMAND` stores version 3 immutable revisions/proposals
and append-only events in SQLite. Ed25519 owner signatures bind exact initialization
and proposals, action, project and public-key fingerprint. OpenSSL 3 is required;
production accepts public keys/detached signatures only. Never sign for a real owner
or treat an actor label as approval. Keep the private key outside agent-controlled
storage and retain the trusted public-key fingerprint separately.

1. `prepare-init REQUEST --owner OWNER --public-key PUBLIC.pem --payload-out PAYLOAD`
   supplies exact bytes for independent owner review/signing.
2. `init REQUEST --owner OWNER --public-key PUBLIC.pem --signature SIGNATURE`
   verifies proof and exclusively publishes a new database.
3. `propose BASE_HASH PATCH.json --actor ACTOR --rationale TEXT --evidence TEXT
   --payload-out PAYLOAD` supplies before/after diffs, indexed sheet/schedule impact
   and signable approval bytes.
4. After independent owner review/signing, `approve PROPOSAL_HASH --owner OWNER
   --signature SIGNATURE`, then `commit PROPOSAL_HASH`.
5. `restore REVISION --actor ACTOR --rationale TEXT --evidence TEXT` creates a new
   proposal requiring approval. `prepare-rejection PROPOSAL_HASH --payload-out PAYLOAD`
   and `reject ... --signature SIGNATURE` use distinct rejection bytes. `inspect`
   reports the source and bounded audit.

A legacy list patch replaces whole components. A typed patch contains any of
`components`, `levels`, `walls`, `openings`, `rooms`, each a list of whole-element
replacements; at most 32 targets total. Additions/deletions, identity/host/type/level
reassignment, missing attributes and arbitrary unit/datum changes are rejected.
Coordinated opening/component edits must be one geometrically consistent proposal.
Unrelated stale edits merge only after full revalidation; same-target edits conflict.
Root initialization and every stored transition proof are checked before a revision
is trusted. The current head must also agree with the latest committed audit event:
its owner-approved proposal, previous document, conflict preconditions and resulting
content are verified even when a legitimate restore reuses an earlier content hash.
Repointing the head to a previously signed revision without an approved restore now
fails closed, including historical-revision reads and new proposals. A fabricated
commit event cannot substitute for a valid owner signature. This does not provide
external anti-rollback protection against an attacker who can replace the entire
trusted database with an older snapshot. Old unreleased database schemas fail
closed; no silent migration occurs.

Changes flag indexed plans and explicit references, including dependent openings
and schedules. Unindexed drawings, external families/types and professional
constraints remain UNKNOWN. This does not claim a complete live BIM dependency
graph. Database/executable storage must remain trusted; signatures do not establish
human presence, professional credentials, external anti-rollback storage or an OS
security boundary. `build --state-db DB --owner-key-sha256 TRUSTED_PIN` binds the
preview to the current approved head and rechecks it under the publication lock.
No Revit/AutoCAD live edit/transaction/rollback adapter is implemented by this ledger.

## Opt-in CC0 textures

`cc0_assets.py` supports Poly Haven textures: exactly 1K JPG diffuse, roughness and
OpenGL-normal channels. No archive, model, HDRI, sprite or ambientCG backend is
exposed. Pillow is required. Catalog access defaults to network-off; explicit
catalog/plan network options preserve attribution/User-Agent and source metadata.
See [Poly Haven API](https://polyhaven.com/our-api) and `cc0_assets.py --help`.

Download requests require the exact approved plan SHA256. The plan binds source,
CC0 license, provider, URLs, lengths and upstream MD5s. HTTPS hosts/redirects are
allowlisted; aggregate budget 8 MiB per plan and at most 4 plans per scene. JPEG
format/dimensions, MD5 and local SHA256 are rechecked. Failed downloads preserve
previous cache entries; corrupted content is rejected rather than silently replaced.
MD5 metadata is not a publisher signature. Live service terms/asset rights remain
part of source review; no legal certification is implied.

Materials supply `asset_plan_sha256`, explicit `uv_tile_size_m: [WIDTH, HEIGHT]`,
white base color, roughness 1 and metallic 0. Do not infer physical texture size from
undocumented provider units. Builds consume `--asset-cache CACHE` offline and pack
images into `.blend`/GLB. Native/imported shader links, UV mapping, image pixels and
provider/license/source/hash provenance are checked. The actual approved Aerial
Wood Snips three-channel download passed; it is a technical texture test, not a
recommendation of wood chips as furniture finish. Synthetic fixtures stay labelled.

## Source-bound IFC4

Explicitly install optional dependencies only in a selected environment, using
`references/requirements-ifc.txt` (IfcOpenShell 0.9.0.post1; pytest 9.1.1 is required
by EXPRESS validation). Gridline never automatically installs them. Publication
requires POSIX secure directory operations and the selected signed state database:

```sh
python3 scripts/component_ifc.py NATIVE_OUT NEW_IFC_OUT \
  --state-db PROJECT.sqlite --requirements REQUIREMENTS.json \
  --expected-bundle-receipt-sha256 TRUSTED_NATIVE_RECEIPT_PIN \
  --expected-owner-key-sha256 TRUSTED_OWNER_KEY_PIN
python3 scripts/component_ifc.py NATIVE_OUT IFC_OUT \
  --state-db PROJECT.sqlite --requirements REQUIREMENTS.json \
  --expected-bundle-receipt-sha256 TRUSTED_NATIVE_RECEIPT_PIN \
  --expected-owner-key-sha256 TRUSTED_OWNER_KEY_PIN \
  --verify --expected-ifc-receipt-sha256 TRUSTED_IFC_RECEIPT_PIN
```

Requirements are data: `schema: gridline-ifc-requirements.v1`, matching `project_id`,
explicit `required_properties` chosen from SourceElementId/RequestSHA256/Kind/MaterialId,
and boolean `allow_unknown_materials`. Unsupported requirements fail closed. The
synthetic acceptance requirements are not a client's IDS or regulatory requirements.

IFC4 contains project/site/building/storeys, source room spaces, physical joined
walls with stable source-segment parts, opening voids/fillings and typed components.
Decorative tiles become coverings, books become proxies and lamps become fixtures;
no generic display mesh is presented as certified structural BIM. Room source area
and explicit-level-height prism volume are labelled accordingly; mesh surface sums
are custom visual quantities, not net usable area or construction quantities.
Unknown source wall materials stay UNKNOWN and fail if the requirements disallow it.
No materials are attached to voids. PBR textures remain native/GLB; IFC maps identities.

Checks include schema/EXPRESS, SI units, local coordinate declaration, spatial
membership/placement, complete products, source properties/material links/quantities,
GUID uniqueness, opening hosts/fillings, raw indices/winding before engine repair,
independent evaluated triangles and occupied/void/room geometry. Fixed IFC4 source
exchange is not a certified MVD or generic client/IDS interoperability claim.
Publication rechecks the signed current head under a transaction. Historical readback
requires an authenticated approved revision; it does not make that revision current.
`model.ifc`, `mapping.json`, `verification.json`, `requirements.json` and the final
receipt bind source, runtime and consumed bytes. Native/IFC headers may contain
legitimate serialization timestamps; source/geometry/GUID checks establish stability.

## Acceptance and distribution

The offline `tests/components_pipeline_acceptance.py` exercises signed source→three
plan sheets/DXF/PDF/schedules→Blender/GLB→IFC, a coordinated 100 mm before/after door
change, actual DXF/IFC widths, host-wall volume and source/relationship GUID stability,
then all 13 component kinds. `components_native_acceptance.py` and
`components_ifc_acceptance.py` seed real private corrupted copies after baseline PASS.
They never operate on a client/live scene. See [0.9.0 qualification](RELEASE_0_9_0_QUALIFICATION.md)
for final source-bound receipts, exact checked scope and outstanding publication gates.

The first-party Blender API worker/harness are GPL-2.0-or-later with corresponding
source and full text. Existing MIT grants are retained; metadata is mixed-license.
External ARCHIMESH source/images/ZIP and optional IFC binaries are not bundled.
Read the portable [licensing boundary](../skills/architectural-drawing-generation/references/BLENDER-LICENSING.md).
Professional project approval, actual client IDS/exchange acceptance, interactive
upstream panels and Revit/AutoCAD live transactions remain outside this release's
qualified scope; full roadmap issues #13/#15/#45 must not be falsely closed.
