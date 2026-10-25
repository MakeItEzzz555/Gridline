# Versioned source selection — research only

Use this when identifying which source editions need review for a real project. It does not check model geometry or evaluate any building requirement. The bundled [registry](source-registry.json) contains citations and original access/scope notes; no paid standards text, tables, numeric construction limits or drawings.

From this installed skill directory:

```bash
python3 scripts/select_sources.py references/example-source-context.json
```

The bundled Cyprus example intentionally exits **2**: IFC/IDS references are pinned, but Cyprus permit and Eurocode adoption evidence is unresolved. To use project data, provide a JSON context with these fields:

- `country`: uppercase two-letter country code, e.g. `CY`. No country is assumed.
- `municipality`: exact locality name from project evidence; `null` if unknown. This tool does not geocode or confirm the responsible authority.
- `project_type`: explicit project use, e.g. `residential` or `hotel`.
- `stage`: `briefing`, `concept`, `spatial-coordination`, `technical-design`, `construction`, `handover` or `operation`. These are Gridline workflow labels; they do not establish a statutory or RIBA stage.
- `as_of`: exact `YYYY-MM-DD` assessment date. Supply the date on which this research will be used. A user-supplied historical date does not establish freshness today.
- `requested_sources`: 1–100 unique `{ "id": "ids", "edition": "1.0.0" }` requests. No universal pack, latest edition or US-code default is selected. Omit/null an unknown edition rather than guessing it.

Missing/null context stays unresolved. Invalid types, dates, duplicate JSON keys, nonfinite values, excessive file size and malformed registry/context fail closed. Input files are read-only, capped at 1 MiB, and no network or host application is called. Use only files you intend the command to read. Other project metadata may be present but cannot authorize rule activation; this is not the #15 proposal/approval gateway.

## Classifications and exit codes

| Status | Meaning |
| --- | --- |
| `UNKNOWN` | Context, source identity or explicitly requested edition is missing, or the assessment predates the recorded source check. |
| `UNVERIFIED` | Publication is draft/unverified, edition mismatches/is unresolved, review is overdue, source is withdrawn, or technical/regulatory adoption, clauses and professional review remain necessary. |
| `NOT_APPLICABLE` | Explicit source scope excludes a known project country/locality/type/stage, or its declared effective period has not begun. This rules out only that source record; it never exempts the project from regulation. |
| `REFERENCE_ONLY` | An explicitly requested methodology/documentation/exchange reference edition matches the registry and falls inside its research recheck window. This is not an applicable-law, model-validity or compliance result. |

Exit **0** means all requested records are reference-only or explicitly outside scope; **2** means unresolved or invalid evidence. Neither exit code means compliance PASS. Missing fields take precedence over date/edition classifications; known territorial exclusions can still be reported independently. Comparisons use exact strings; no fuzzy country, office, municipality or edition equivalence is inferred.

The receipt includes original-byte SHA256 hashes for context and registry. These identify the inputs, not their truth, ownership, signature or professional approval. `rule_activation_allowed` is always false at both report and record level. Even claimed professional approval or populated clause lists cannot enable a rule through this command.

## Registry contract and professional boundary

Each record carries issuer, source URL, edition (or null), access level/pointer, publication status, scope, checked/recheck dates, national adoption status/edition, effective/withdrawal dates, obligation source, license scope, verified clause pointers, exception status, reviewer, risk and next evidence. `null` adoption/dates/reviewer and empty clause/exception lists mean **not established**, not no requirements/exceptions exist. Null scope lists mean no source restriction has been encoded for research triage; they do not assert universal legal applicability. Local rule applicability must be established separately.

The 90-day recheck window is an original Gridline research policy, not a statutory validity period or proof that a source cannot change sooner. ISO references are issuer metadata only. CYS's located concrete National Annex is explicitly public enquiry, not verified adopted text. JRC's national publication deadline (2027-09-30) and withdrawal deadline (2028-03-30) are transition guidance, not proof of which Cyprus edition is currently binding. Gov.cy process descriptions are guidance with possible exemptions, not consolidated law.

Before any future rule activation, obtain the exact adopted edition/amendments and source clauses, national/local authority and obligation, occupancy/project/stage scope, exceptions, licensed access and a competent named professional's approval. That future activation requires its own tested trust/approval boundary; editing this registry cannot grant it. Preserve #15 scoped proposals and #33 independent geometry QA.

## Current source coverage and gaps

Covered identifiers: RIBA 2020; ISO 19650-1:2018; ISO 13567-1:2017; IFC 4.3 ADD2 / 4.3.2.0; ISO 16739-1:2024; IDS 1.0.0; ISO 21542:2021; Cyprus Eurocode/adoption intake; the CYS EC2 public-enquiry candidate; Cyprus planning, building permit and fire/accessibility/energy authority intake. References were checked 2026-10-25. Some Gov.cy/CYS metadata was available only via official indexed results; access limitations are recorded, not promoted to full-text reading.

Not yet individually registered: other ISO 19650 parts; EN 17210, EN 13501, EN 17037; moisture/thermal and LCA standards; local planning-zone/decree versions; actual Cyprus National Annex adoptions; contractual MasterFormat/Uniclass profiles. Do not infer their editions or encode thresholds from family names. Unknown IDs remain UNKNOWN.

This package's tests establish classification, input handling and standalone installation behavior only. They do not establish national adoption, professional approval, native CAD/BIM acceptance or lawful compliance.
