# AutoCAD Mac inspection v1

Related issues: #12, #16. This is a **manual AutoLISP console transport**, not an MCP connection. No plugin installation, security preference change, automatic script load, native edit, AUDIT, save, plot or DWG conversion occurs through this adapter.

## Work package and permission boundary

Start from main `0a2e9aefa204b90b685556d1fb0c714f719d371b`; preserve existing worktrees. Scope: standalone doctor, bounded copy preparation, fixed inspector, console receipt validation, native-evidenced paper-space viewport layer correction and tests. Done means real read metadata when authorized, otherwise explicit NOT_TESTED. Transactions, write approval, full native compatibility and BIM remain separate gates. A second read-only agent reviewed safety independently; no additional model or benchmark calls are part of this package.

```sh
A=skills/autocad-dwg-workflow/scripts/autocad_native.py
python3 "$A" doctor
python3 "$A" prepare --root /absolute/selected/samples --drawing A-101.dxf --workspace /private/tmp
```

`prepare` reads only the selected relative DXF under the explicit root. It traverses with pinned directory descriptors and no-follow opens; rejects traversal, symlinks, special files and inputs above 16 MiB. Each run creates a private 0700 directory with exclusive 0600 files: a new `drawing.dxf`, `inspect.lsp`, and `session.json` with exact consumed-byte hashes. Preparation does not parse or certify arbitrary DXF safety. Use trusted disposable samples in a local workspace controlled by the operator. Filesystem confinement is macOS/POSIX only; no Windows native transport is advertised.

1. Confirm AutoCAD's license/startup prompts are complete. Do not share credentials. An education/noncommercial title is a session observation, not independent license entitlement verification.
2. Open the returned **copy** in AutoCAD. Confirm its full path and capture opening warnings. Leave client drawings untouched.
3. Review the generated inspector and its manifest hash. Paste the returned `(load "...")` expression into the native command line. If AutoCAD shows a security dialog, the operator must approve that single load; never change SECURELOAD or trusted paths.
4. Run `GRIDLINEINSPECT`. Loading only defines the command. The command refuses any drawing other than the expected exact path, caps table/entity reads and prints one JSON block between `GRIDLINE_READ_BEGIN` / `GRIDLINE_READ_END`. It uses supported AutoLISP reads only, does not issue CAD commands or write files. Close the copy without saving to end the test.
5. Save the exact observed block as `console.txt` in the session directory, then run:

```sh
python3 "$A" receipt /absolute/session-directory console.txt
```

Receipt output goes to stdout, so the operator chooses a **new** destination if preserving it. It verifies probe/document identity, unchanged source and inspector bytes, DBMOD invariance, counts and basic metadata. `READ_PROBED` means an operator-captured, unauthenticated console read. It is not an authenticated automated host query; a fabricated console file cannot be distinguished cryptographically. Recheck hashes before use. No untrusted MCP invocation is exposed.

## Coverage and truth states

Doctor reports installed bundle/version, with license UNKNOWN and all native test states NOT_TESTED. Actual console receipts record ACADVER/PLATFORM, INSUNITS, top-level model entity types/counts, layer names/flags/colors, paper layouts, viewport height ratios/flags and cached EXTMIN/EXTMAX. No nested block enumeration, geometry completeness, recomputed extents, layout plot validation or automatic warning collection is claimed. Numeric extents/viewport heights are strings to avoid locale/AutoLISP number-format ambiguity; validate/convert explicitly when comparing them. Compare viewport paper_height/view_height only as a declared scale hint, not proof of plotted output.

Native open warnings must accompany the receipt. AUDIT can modify a drawing and must be separately exercised on another disposable copy. AUDIT, native edit/plot, DWG export, and DWG↔DXF semantic roundtrip remain **NOT_TESTED** until their own host evidence exists. No AutoCAD 3D capability follows from 2D openability.

## Primary API references checked 2026-10-24

- [2027 supported interfaces](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Customization/files/GUID-E6429154-36DF-4D84-8ABC-9FCA15B66158.htm): AutoLISP/ObjectARX on Mac; no Windows .NET/ActiveX assumptions.
- [ssget](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-AutoLISP-Reference/files/GUID-0F37CC5E-1559-4011-B8CF-A3BA0973B2C3.htm): database selection, top-level entities only.
- [tblnext](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-AutoLISP-Reference/files/GUID-1720D8DC-5559-4AC1-8A75-3C932834D77C.htm) and [layoutlist](https://help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-AutoLISP-Reference/files/GUID-AE3F338F-0B11-45B0-AB12-2C119203A977.htm): native tables/layout names.

Validation: eight dependency-free adapter tests; the initial pinned CAD-required full suite passed 80 tests with zero skips, followed by the syntax regression test and final-head CI. Provider parity and repository checks are required before delivery. OS/UI permission or manual load refusal never becomes PASS.


## Actual native result, 2026-10-24

The operator permitted the inspector load. AutoCAD returned release `26.0s (LMS Tech)`, `macOS Version 15.7 (Arm64)`, INSUNITS=4, 149 top-level model-space entities, 18 layers and layout A-101. Entity counts matched an independent ezdxf read of the exact source DXF. DBMOD was already 17 before the probe and remained 17; the receipt does not claim the earlier in-memory state was pristine. The source and copied DXF bytes remained unchanged. Host automatic autosave of its disposable in-memory drawing was observed; no global preferences were changed or original drawing saved.

Native interpreter testing exposed and corrected inspector syntax, nonce JSON quoting and the viewport height DXF group code (41, not width code40). Regression checks cover these observed defects. [Autodesk viewport DXF reference](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-2602B0FB-02E4-4B9A-B03C-B1D904753D34.htm) and [2027 viewport API](https://help.autodesk.com/cloudhelp/2027/ENU/OARX-RefGuide/files/OARX-RefGuide-__MEMBERTYPE_Methods_AcDbViewport.html) establish the height mapping. The corrected native height ratio was 196/19600 = 1:100; this is not a PDF plot check.

AUDIT with repairs disabled (`_.AUDIT`, `_N`) reported two errors for the same overall paper-space viewport handle23E on VIEWPORTS. Independent DXF inspection confirmed viewport ID1 on VIEWPORTS. The generator now puts only that overall viewport on layer0, and the checker rejects the old assignment. Fresh A-101/A-102 files both opened in AutoCAD and returned **0 errors, 0 fixed, 0 erased** on native no-repair AUDIT. The model-view viewport remains on the profile's nonplot layer and keeps its scale/lock. No prior sample was overwritten.

See `AUTOCAD_INSPECTION_EVIDENCE.json` for per-file hashes and captured audit evidence. The local A-102 native screenshot confirms visible geometry after zoom extents. Font substitutions remain known losses (including room-area glyph appearance); no native plot, edit/DWG export, geometry-completeness, layer-semantic roundtrip or professional approval is inferred. Issue #16 remains open.
