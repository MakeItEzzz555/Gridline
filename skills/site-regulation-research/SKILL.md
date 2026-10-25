---
name: site-regulation-research
description: Research and structure site, zoning, planning, building-code, accessibility, fire, and local-authority constraints with source/date traceability. Use whenever architecture work depends on jurisdictional requirements.
---

# Site & Regulation Research

Establish exact jurisdiction, project type, stage, and source version/date before treating a rule as applicable. Prefer official authorities, legislation, regulations, adopted plans, and published guidance.

For each material control record topic, requirement, applicability, numeric value if any, source title, clause/page/link/file, date/version, and confidence/status.

Separate confirmed requirement, interpretation, project assumption, and items requiring authority/professional confirmation.

Do not claim permit approval or definitive compliance. Flag planning/legal, accessibility, fire/life-safety, structural, and construction-critical conclusions for competent human review.

## Offline source-edition triage

For explicit jurisdiction/source-edition requests, read [source selection and limits](references/source-selection.md), then use this skill's own `scripts/select_sources.py` with a project context. Its bundled `references/source-registry.json` is citation metadata, not an approved rule pack. The command reports missing/stale/draft/wrong-jurisdiction evidence and never activates a rule or issues compliance PASS. Do not substitute drawing-profile defaults for adopted building regulations.
