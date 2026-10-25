# Draft implementation review

What this change does: Generates bounded, explicitly approved ARCHIMESH visual
components in disposable Blender processes, validates native and GLB readback,
and adds signed local component proposals and an opt-in texture cache. The IFC
adapter remains unqualified and the stable release is blocked.

One coding agent performed a bounded Ponytail/security/architecture self-review
of the driver, worker, model, mesh matching, cache, approval/state and IFC input
flow, shared publication/file/GLB helpers, callers, tests, fixtures, manifests and
documentation. Expected workload is a local CLI, at most32 components,100,000
triangles and64 MiB per published artifact; this is not a hosted multiuser service.
No independent agent review, legal certification or professional approval is implied.

Fixed during implementation/review:
- Owner labels could impersonate approval: detached Ed25519 proofs now bind exact
  initialization/proposal/action/project/key data and are rechecked at commit.
- An unused valid shader and animated/constrained roots could escape readback:
  known active surface graphs and complete object state/inventory are now checked.
- Public verification could race artifact reads and rewrite a published report:
  it now reopens only pinned snapshots and preserves the published directory.
- Unbounded artifact serialization could exceed the public verifier's limits:
  matching byte/triangle budgets now block generation/publication.
- IFC intake could accept an unsigned preview and reread changed inputs:
  it now requires a signed source binding, trusted owner key/receipt pins and
  consumes only the bytes already validated in memory.

Validation: repository checker passed; all218 CAD-environment tests passed with
zero skips in77.556s. Current-source native builds passed for13 recipes, a signed
two-level building fixture and synthetic packed PBR; the unchanged baseline passed
before26 actual corrupted native/GLB fixtures were rejected. Public verification
reopened the retained-pinned current source bundle without changing published
bytes. Native detail renders were inspected; opaque windows and open-ended
faceted column display surfaces are disclosed. Portable receipts/hash coverage
are in this directory; full local logs remain at the path in development-status.json.

Must fix before stable shipment: execute the optional IFC adapter against actual
IfcOpenShell and fix any schema/EXPRESS, spatial, quantity, GUID, geometry or
requirements failures; test a real approved CC0 download/packed PBR path; complete
final release/package/CI qualification. The current IFC input tests do not cover
engine execution. General #15 building/live-host transactions, full #13 P2/IDS
acceptance and professional model inspection are not completed by this component
ledger or preview adapter. Keep those capabilities gated; do not close those issues.

Verdict: draft checkpoint only. No stable release/version bump or merge.
Not checked: real IFC engine/client/IDS behavior, real public-asset acceptance,
interactive ARCHIMESH panels, arbitrary parameter combinations and live-host edits.
