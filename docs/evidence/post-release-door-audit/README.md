# Door patch evidence

Generated DXF/SVG files are marked binary for Git review to preserve their original bytes and avoid treating drawing syntax as a source diff; use the rendered views and hash inventory.

Synthetic geometry only; not a construction drawing or release qualification.

- `rotated-legacy.building.json`: one wall at 105°, explicit legacy right swing, 900 mm door. The baseline generator makes a 270° arc; the patch produces 90°.
- `room-entry.building.json`: bedroom/hall and explicit receiving room, rotated 15°. Dimensions are declared fixture data, not statutory clearances.
- `before-*`: generated with baseline f521969934758ac5625239ea65229190a5a6114e.
- `after-*` / `room-entry-*`: generated with patch sources, before commit. `validation.json` binds the final tested logic/test hashes. The final commit identity is in the PR/handoff.
- `*-plan.pdf` / `*.dxf`: complete A-101 sheet/model. `*-door.svg` / `*.png`: actual DXF render crops; after crops honor nonplot layer visibility as the patched PDF does. Cropped annotation is intentional; full sheets were inspected separately.
- `artifact-hashes.json`: generated drawing/spec file hashes. It is not a publisher signature or independent approval. Validation/README records were added subsequently and are not in that output inventory.

Reproduce in a fresh directory with the pinned CAD environment:

```sh
python3 skills/architectural-drawing-generation/scripts/aec_cad.py build docs/evidence/post-release-door-audit/rotated-legacy.building.json NEW_OUTPUT
python3 skills/architectural-drawing-generation/scripts/aec_cad.py check docs/evidence/post-release-door-audit/rotated-legacy.building.json NEW_OUTPUT
python3 -m unittest discover -s tests -p test_door_intent.py -v
```

Repeat build/check with `room-entry.building.json` and a different fresh output directory. Build the legacy fixture from a separate baseline checkout to reproduce the old failure; never reset existing worktrees. There is no native AutoCAD/Blender roundtrip receipt for this patch. Closed conceptual 3D door slabs do not verify open-door behavior. Do not reuse the v0.8.0 release receipt for this source.
