# Research Basis

These are the sources the skills were shaped from and that agents should check for current behavior. Vendor APIs and standards change between releases: treat the live documentation for the user's exact version as the truth, not this list. Links were last checked on 2026-10-21.

## Professional workflow coverage

- [RIBA Plan of Work](https://www.architecture.com/knowledge-and-resources/resources-landing-page/riba-plan-of-work): lifecycle stages from strategic definition through use.
- AIA B101 Owner–Architect Agreement ([AIA Contract Documents](https://www.aiacontracts.com/)): basic services from schematic design through construction-phase services.
- buildingSMART openBIM standards, from their official repositories:
  - [IFC 4.3](https://github.com/buildingSMART/IFC4.3.x-development): model exchange schema.
  - [BCF](https://github.com/buildingSMART/BCF-XML): issue/coordination exchange.
  - [IDS](https://github.com/buildingSMART/IDS): machine-checkable information requirements.
  - [bSDD](https://github.com/buildingSMART/bSDD): shared classification and property terminology.

These sources inform capability coverage. They do not replace the actual project contract, jurisdiction or appointed consultants.

## Authoring and automation documentation

- Revit: [Autodesk Revit help](https://help.autodesk.com/view/RVT/2026/ENU/), [Revit API index](https://www.revitapidocs.com/), [pyRevit](https://pyrevitlabs.io/), [Dynamo](https://github.com/DynamoDS/Dynamo).
- Rhino / Grasshopper: [RhinoCommon API](https://developer.rhino3d.com/api/rhinocommon/), [Grasshopper developer guides](https://developer.rhino3d.com/guides/grasshopper/).
- AutoCAD / Civil 3D: [AutoCAD developer help](https://help.autodesk.com/view/OARX/2026/ENU/), [Civil 3D help](https://help.autodesk.com/view/CIV3D/2026/ENU/).
- openBIM tooling: [IfcOpenShell](https://docs.ifcopenshell.org/), [IfcTester for IDS checks](https://docs.ifcopenshell.org/ifctester.html), [Bonsai](https://docs.bonsaibim.org/).

## Agent / automation projects reviewed

- Live model control through MCP: [revit-mcp](https://github.com/mcp-servers-for-revit/revit-mcp), [autocad-mcp](https://github.com/puran-water/autocad-mcp), [cordyceps (Grasshopper)](https://github.com/brookstalley/cordyceps), [rhinoMcpServer](https://github.com/always-tinkering/rhinoMcpServer). Lesson: live model operations need explicit write boundaries, tool discovery, readback and undo/transaction safety.
- Deterministic IFC skills: [IFC-Claude-Skill-Package](https://github.com/Impertio-Studio/IFC-Claude-Skill-Package). Lesson: version-sensitive knowledge belongs in focused skills backed by scripts.
- Skill packaging: [Agent Skills specification](https://agentskills.io/), [Claude Code plugins](https://docs.claude.com/en/docs/claude-code/plugins). Lesson: progressive disclosure beats a giant system prompt, and a skill's scripts must ship inside the skill folder.

## Repository-design lesson

TuckBit, Claude Widget Kit and Codex Widget Kit informed the onboarding style: a clear hero/value proposition, copyable agent-install prompt, exact verification, honest capability boundaries, native-provider paths and evidence-driven validation.

## Source-edition and jurisdiction triage (2026-10-25)

The [portable source registry and offline selector](../skills/site-regulation-research/references/source-selection.md) records exact source/edition/access metadata and unresolved national/local adoption. It does not evaluate building requirements or establish compliance. All rule activation remains disabled; the existing drawing profiles are separate output conventions.
