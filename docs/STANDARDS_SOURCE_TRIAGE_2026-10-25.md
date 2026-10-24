# Source registry and jurisdiction triage — bounded delivery

Base: `fdc678a78a48832535efc4d56977d0aafb45bca9` (fresh origin/main). This package is independent of unmerged book PR #37 and update-checker PR #38. Existing source/state/geometry and install paths stay intact; no provider manifest version or format changes.

## Working result

The portable `site-regulation-research` skill now includes a versioned 12-record source registry, offline project-context selector, example, usage/status contract and self-contained script. Claude mirrors are synchronized. The selector explicitly requests source editions and records wrong-jurisdiction, unknown, draft, mismatched and stale evidence without applying rules or generating regulatory PASS. Reports contain context/registry SHA256 identifiers, not authentication claims.

The change reaches the canonical skill/script/references, complete Claude mirror, tests, Windows CI test invocation, changelog and research index. No new dependency, network request, model/native host call, installation setting, root relocation or project write is added. Existing CAD drawing profiles are not changed or reclassified as adopted regulations.

## Evidence and counterexamples

- [JRC transition guidance](https://eurocodes.jrc.ec.europa.eu/second-generation-eurocodes) separates availability, national publication and withdrawal dates. A second-generation availability announcement does not identify an applicable Cyprus edition or national choice.
- The located [CYS concrete National Annex document](https://www.cys.org.cy/images/%CE%A0%CE%B1%CF%81%CE%AC%CF%81%CF%84%CE%B7%CE%BC%CE%B1_%CE%91_Cyprus_National_Annex_1992-1-1_EC2_Public_Enquiry_11-2024.pdf) is indexed as Public Enquiry, dated 2024-11-28. It cannot be silently promoted to adopted requirements. No technical clauses/tables copied.
- [JRC national-standard guidance](https://eurocodes.jrc.ec.europa.eu/en-eurocodes-implementation/national-standards) explains that not every case requires a National Annex; verify the applicable national choice rather than blanket-requiring a nonexistent annex.
- [Gov.cy building permission](https://www.gov.cy/bsc/en/licensing-procedures/building-permission/) and [planning permission](https://www.gov.cy/bsc/en/licensing-procedures/planning-permission/) describe process/authority and exceptions. They do not establish a universal permit predicate for every project. Indexed official metadata was available; direct building-page retrieval returned 403.
- [ISO 13567-1:2017 metadata](https://www.iso.org/standard/70181.html) identifies CAD layer principles, not every office layer code, text height or building requirement. Only identifiers and original scope notes included.
- [ISO 19650-1:2018 metadata](https://www.iso.org/standard/68078.html?browse=tc) distinguishes a published edition from a draft replacement. It does not certify structural adequacy.
- [buildingSMART specification table](https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/) identifies IFC 4.3 ADD2 / 4.3.2.0; IFC 4.4/5 development is not an interchangeable stable target. [ISO 16739-1:2024](https://www.iso.org/standard/84123.html) is separately recorded. Schema, IDS, geometry and native interoperability remain independent dimensions.
- [IDS 1.0.0](https://github.com/buildingSMART/IDS/releases/tag/v1.0.0), published 2024-06-03, was confirmed through the official GitHub API. An IDS information result does not prove geometry or legal compliance.
- [RIBA 2020](https://www.riba.org/work/insights-and-resources/riba-plan-of-work/) is a project-stage method; [ISO 21542:2021](https://committee.iso.org/standard/71860.html) still needs project/national applicability and licensed clauses before technical enforcement.

## Validation and review boundary

Tests cover missing/blank context, exact edition requests, local/country/type/stage exclusions, research recheck deadlines, withdrawal/effective windows, unregistered IDs, draft publications, wrong editions, false/claimed approvals, invalid dates/types, oversized/nonfinite/duplicate-key JSON, malformed registry and standalone skill execution with original-byte hash receipts. Windows CI explicitly runs these tests in addition to existing topology/GLB and installer checks.

One bounded same-agent Ponytail/security/AEC review traced input parsing, classification order, metadata, source claims, copies and tests. Review found whitespace-only locality/project-type could be mistaken for known context; fixed with regression coverage. No independent architectural/security approval is claimed. Expected workload is one local research command with at most 100 explicit source requests, not an agent daemon or legal engine.

## Status and remaining dependency

DONE: working source-edition research selector and portable citation registry, with adversarial tests. PARTIAL: master-plan R2; national/local adopted editions, legal effective dates, verified clauses, exception scope and competent professional approvals are deliberately unresolved. Other standard parts/families are listed as gaps in the skill documentation rather than invented records.

No rules can be activated through this command, even if registry approval fields are populated. Actual rule activation requires a separate authenticated approval/validation design and the #15 proposal safeguards. #33 geometry QA remains independent. No issue is closed, release tagged/published or other repository changed. Native CAD/BIM, Gemini/runtime activation and live regulatory acceptance are NOT_TESTED because this package does not add those capabilities.

Executed checks: `python3 tests/check_repo.py` and provider parity pass. `GRIDLINE_REQUIRE_CAD_TESTS=1 uv run --offline --with ezdxf==1.4.5 --with matplotlib==3.11.2 --with pypdf==6.21.2 python -m unittest discover -s tests -v` passed **134 tests, no skips**, 61.969 seconds after the review fix. Eleven tests are specific to this package. Cached dependencies only. The source example correctly returns exit 2 for unresolved Cyprus adoption while exposing its pinned IFC/IDS references. Headroom retained the earlier regression log under `b86265cd364783a4a5eceb4e` and retrieved the exact original; no provider-billed savings are claimed and its configured proxy was unreachable.
