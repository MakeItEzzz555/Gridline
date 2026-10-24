#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

def load_json(path):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return {}

registry = load_json(ROOT / "skills" / "manifest.json")
expected = {x["name"] for x in registry.get("skills", []) if x.get("status") == "stable"}
if not expected:
    errors.append("skills/manifest.json: no stable skills declared")

paths = [
    ROOT / "plugin.json",
    ROOT / "distribution.json",
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / "gemini-extension.json",
    ROOT / "providers" / "claude" / ".claude-plugin" / "plugin.json",
]
manifests = {x: load_json(x) for x in paths}
versions = {m.get("version") for m in manifests.values() if m.get("version")}
if len(versions) != 1:
    errors.append(f"provider manifest version drift: {sorted(versions)}")
if registry.get("version") not in versions:
    errors.append("skills/manifest.json version does not match provider manifests")

marketplace = load_json(ROOT / ".claude-plugin" / "marketplace.json")
mp_plugins = marketplace.get("plugins", [])
if not mp_plugins or mp_plugins[0].get("version") not in versions:
    errors.append("Claude marketplace version does not match provider manifests")


market = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
entries = market.get("plugins", [])
if market.get("name") != "gridline" or len(entries) != 1:
    errors.append("Codex marketplace: expected one gridline entry")
elif entries[0].get("source") != {"source": "local", "path": "./"}:
    errors.append("Codex marketplace: root local source mapping is invalid")

portable = manifests[ROOT / "plugin.json"]
allowed_portable = {"$schema", "name", "version", "description", "author", "homepage", "repository", "license", "keywords", "extensions"}
extra_portable = set(portable) - allowed_portable
if extra_portable:
    errors.append(f"plugin.json: unsupported portable fields {sorted(extra_portable)}")
if portable.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
    errors.append("plugin.json: current portable Agent Plugins schema missing")
if portable.get("skills") is not None:
    errors.append("plugin.json: portable root should rely on the fixed root skills/ directory, not a compatibility-only skills field")
if not (ROOT / "skills").is_dir():
    errors.append("portable plugin: root skills/ directory missing")

found = set()
for skill in (ROOT / "skills").glob("*/SKILL.md"):
    text = skill.read_text()
    fm = re.match(r"---\s*\n(.*?)\n---", text, re.S)
    if not fm:
        errors.append(f"{skill.relative_to(ROOT)}: missing frontmatter")
        continue
    name = re.search(r"^name:\s*(.+)$", fm.group(1), re.M)
    desc = re.search(r"^description:\s*(.+)$", fm.group(1), re.M)
    if desc:
        raw_desc = desc.group(1).strip()
        if ": " in raw_desc and not (raw_desc.startswith('"') and raw_desc.endswith('"')):
            errors.append(f"{skill.relative_to(ROOT)}: description containing colon-space must be YAML-quoted")
    if not name or not desc:
        errors.append(f"{skill.relative_to(ROOT)}: name/description required")
    else:
        found.add(name.group(1).strip())
if found != expected:
    errors.append(f"canonical skill set mismatch: registry={sorted(expected)} files={sorted(found)}")

sys.path.insert(0, str(ROOT / "scripts"))
sync = __import__("sync-provider-skills")
for name in sync.drift():
    errors.append(f"Claude skill drift (whole folder): {name}")

claude = manifests[ROOT / "providers" / "claude" / ".claude-plugin" / "plugin.json"]
if claude.get("skills") != "./skills/":
    errors.append("Claude plugin: explicit ./skills/ path missing")
declared = set(claude.get("agents", []))
actual = {f"./agents/{x.name}" for x in (ROOT / "providers" / "claude" / "agents").glob("*.md")}
if declared != actual:
    errors.append("Claude plugin: explicit agent list does not match files")

def frontmatter(path):
    match = re.match(r"---\s*\n(.*?)\n---", path.read_text(), re.S)
    return match.group(1) if match else ""

for path in (ROOT / "agents").glob("*.md"):
    fm = frontmatter(path)
    for field in ("name:", "description:", "kind:", "max_turns:", "timeout_mins:"):
        if field not in fm:
            errors.append(f"{path.relative_to(ROOT)}: missing Gemini field {field[:-1]}")

for path in (ROOT / "providers" / "claude" / "agents").glob("*.md"):
    fm = frontmatter(path)
    for field in ("name:", "description:", "maxTurns:"):
        if field not in fm:
            errors.append(f"{path.relative_to(ROOT)}: missing Claude field {field[:-1]}")

evals = load_json(ROOT / "evals" / "activation-cases.json")
ids = set()
coverage = {name: 0 for name in expected}
negative = 0
for case in evals.get("cases", []):
    cid = case.get("id")
    prompt = case.get("prompt", "").strip()
    target = case.get("expected_skill")
    if not cid or cid in ids:
        errors.append(f"evals: missing/duplicate id {cid!r}")
    ids.add(cid)
    if not prompt:
        errors.append(f"eval {cid}: empty prompt")
    if target is None:
        negative += 1
    elif target not in expected:
        errors.append(f"eval {cid}: unknown target skill {target}")
    else:
        coverage[target] += 1

for name, count in coverage.items():
    if count < 2:
        errors.append(f"eval coverage: {name} has {count} positive cases; need >=2")
if negative < 2:
    errors.append("eval coverage: need at least two negative controls")

for required in (
    ROOT / "skills" / "architectural-drawing-generation" / "scripts" / "aec_draw.py",
    ROOT / "skills" / "architectural-drawing-generation" / "references" / "aec-drawing.schema.json",
    ROOT / "skills" / "architectural-drawing-generation" / "references" / "concept-plan.drawing.json",
    ROOT / "skills" / "architectural-drawing-generation" / "scripts" / "aec_cad.py",
    ROOT / "skills" / "architectural-drawing-generation" / "references" / "example-house.building.json",
    ROOT / "skills" / "architectural-drawing-generation" / "references" / "standards" / "iso13567.json",
    ROOT / "skills" / "architectural-drawing-generation" / "references" / "standards" / "ncs.json",
    ROOT / "INSTALL_PROMPT.md",
    ROOT / "docs" / "AEC_LIFECYCLE.md",
    ROOT / "docs" / "TOOL_INTEGRATIONS.md",
    ROOT / "docs" / "DRAWING_OUTPUTS.md",
    ROOT / "docs" / "RESEARCH.md",
):
    if not required.exists():
        errors.append(f"required AEC asset missing: {required.relative_to(ROOT)}")

if "architectural-drawing-generation" in expected:
    drawing_skill = (ROOT / "skills" / "architectural-drawing-generation" / "SKILL.md").read_text()
    if "scripts/aec_draw.py" not in drawing_skill:
        errors.append("architectural-drawing-generation must reference scripts/aec_draw.py")

if errors:
    print("\n".join("ERROR: " + e for e in errors))
    sys.exit(1)

version = next(iter(versions))
print(f"PASS: v{version}; {len(expected)} canonical skills; provider sync; manifests; bounded agents; {len(ids)} activation cases.")
