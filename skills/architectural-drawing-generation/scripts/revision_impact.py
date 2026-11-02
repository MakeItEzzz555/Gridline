#!/usr/bin/env python3
"""Read-only change-impact analysis for Gridline building specifications.

Answers: if an opening/wall/room/level changes, which indexed sheets and
schedules must be reviewed? Unindexed or unannotated external drawings remain
explicitly UNKNOWN. This is not a live BIM model checker or a code-compliance test.

Usage:
  python3 scripts/revision_impact.py before.json after.json --out impact.json
  python3 scripts/revision_impact.py before.json after.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path

GROUPS = ("levels", "walls", "openings", "rooms", "grids")
REFERENCABLE = {"levels", "walls", "openings", "rooms"}
SCHEDULES = {
    "openings": {"window": "window-schedule.csv", "door": "door-schedule.csv"},
    "rooms": "room-schedule.csv",
    "sheets": "sheet-register.csv",
}


class InvalidSpecification(ValueError):
    pass


def indexed(items: list, label: str) -> dict:
    output = {}
    if not isinstance(items, list):
        raise InvalidSpecification(f"{label} must be an array")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id" if label != "sheets" else "number"), str):
            raise InvalidSpecification(f"{label} entries require string IDs")
        key = item["id" if label != "sheets" else "number"]
        if not key or key in output:
            raise InvalidSpecification(f"{label} contains empty or duplicate identifier {key!r}")
        output[key] = item
    return output


def _unique_json_pairs(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate object keys at every nesting level before data is lost."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidSpecification(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    """The Python JSON decoder otherwise accepts non-standard NaN/Infinity."""
    raise InvalidSpecification(f"non-finite JSON constant {value!r}")


def _finite_json_float(value: str) -> float:
    """Reject exponent overflow that decodes as infinity despite valid syntax."""
    number = float(value)
    if not math.isfinite(number):
        raise InvalidSpecification("non-finite JSON number")
    return number


def parse_spec_json(contents: str | bytes) -> dict:
    """Decode unambiguous finite JSON for both CLI and read-only MCP inputs."""
    document = json.loads(contents, object_pairs_hook=_unique_json_pairs,
                          parse_constant=_reject_json_constant,
                          parse_float=_finite_json_float)
    if not isinstance(document, dict):
        raise InvalidSpecification("building specification must be a JSON object")
    return document


def read_spec(path: Path) -> dict:
    doc = parse_spec_json(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise InvalidSpecification(f"{path}: expected JSON object")
    for group in (*GROUPS, "sheets"):
        indexed(doc.get(group, []), group)
    return doc


def sheet_refs(sheet: dict) -> dict[str, set[str]]:
    refs = sheet.get("references", {})
    if not isinstance(refs, dict) or set(refs) - REFERENCABLE:
        raise InvalidSpecification(f"sheet {sheet['number']}: invalid references; use {sorted(REFERENCABLE)}")
    output = {}
    for group, ids in refs.items():
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            raise InvalidSpecification(f"sheet {sheet['number']}: references.{group} must be IDs")
        output[group] = set(ids)
    return output


def stale_model_links(spec: dict, revision: str) -> list[dict]:
    """Find unresolved model relationships without treating a review as CAD validation.

    Report both revisions: an unchanged broken host/level/receiving-room link
    must not produce NO_INDEXED_CHANGES. Do not guess replacement identities.
    """
    levels = indexed(spec.get("levels", []), "levels")
    walls = indexed(spec.get("walls", []), "walls")
    rooms = indexed(spec.get("rooms", []), "rooms")
    openings = indexed(spec.get("openings", []), "openings")
    issues = []
    for group, items, field, targets in (
        ("walls", walls, "level", levels),
        ("rooms", rooms, "level", levels),
        ("openings", openings, "wall", walls),
    ):
        for item_id, item in sorted(items.items()):
            target = item.get(field)
            if not isinstance(target, str) or target not in targets:
                issues.append({"revision": revision, "group": group, "id": item_id,
                               "field": field, "target": target, "reason": "missing_target"})
    for item_id, item in sorted(openings.items()):
        if "receiving_room" not in item:
            continue
        target = item["receiving_room"]
        if not isinstance(target, str) or target not in rooms:
            issues.append({"revision": revision, "group": "openings", "id": item_id,
                           "field": "receiving_room", "target": target,
                           "reason": "missing_target"})
        elif item.get("wall") in walls and rooms[target].get("level") != walls[item["wall"]].get("level"):
            issues.append({"revision": revision, "group": "openings", "id": item_id,
                           "field": "receiving_room", "target": target,
                           "reason": "level_mismatch"})
    return issues


def affected_sheets(group: str, item_id: str, before: dict | None, after: dict | None,
                    old: dict, new: dict) -> list[str]:
    """Conservatively follow declared host/level links in both revisions.

    A wall edit can invalidate an opening-only detail; a level edit can
    invalidate a room-only section. Unindexed external drawings remain unknown.
    """
    matched = set()
    if group == "grids":
        # Grids are drawn across plans but have no per-sheet dependency index.
        # Treat additions, removals and edits as affecting every indexed sheet.
        return sorted({sheet["number"] for spec in (old, new)
                       for sheet in spec.get("sheets", [])})
    for spec, item in ((old, before), (new, after)):
        walls = indexed(spec.get("walls", []), "walls")
        openings = indexed(spec.get("openings", []), "openings")
        rooms = indexed(spec.get("rooms", []), "rooms")
        related = {group: {item_id}}
        level = (item or {}).get("level")
        if group == "levels":
            level = item_id
            related["walls"] = {w["id"] for w in walls.values() if w.get("level") == level}
        elif group == "openings":
            host = (item or {}).get("wall")
            if host in walls:
                related["walls"] = {host}
                level = walls[host].get("level")
        if group == "walls":
            related["walls"] = {item_id}
        if group == "rooms":
            # A room change can affect a door-only detail whose opening
            # declares that room as its receiving/served room.
            related["openings"] = {o["id"] for o in openings.values()
                                   if o.get("receiving_room") == item_id}
        if group in ("walls", "levels"):
            # Host edits affect hosted opening details even if the sheet
            # references only the opening ID, not the wall or its level.
            hosts = related.get("walls", set())
            related["openings"] = {o["id"] for o in openings.values()
                                   if o.get("wall") in hosts}
            # Room-wall adjacency is not indexed. Flag same-level room
            # details conservatively rather than claiming exhaustive coverage.
            related["rooms"] = {r["id"] for r in rooms.values()
                                if r.get("level") == level}
        if level is not None:
            related.setdefault("levels", set()).add(level)
        for sheet in spec.get("sheets", []):
            refs = sheet_refs(sheet)
            explicit = any(refs.get(kind, set()) & ids for kind, ids in related.items())
            if explicit or (level is not None and sheet.get("level") == level):
                matched.add(sheet["number"])
    return sorted(matched)


def analyze(old: dict, new: dict) -> dict:
    for spec in (old, new):
        if not isinstance(spec, dict) or not isinstance(spec.get("project", {}), dict):
            raise InvalidSpecification("revision and project must be JSON objects")
        for group in (*GROUPS, "sheets"):
            indexed(spec.get(group, []), group)
        for sheet in spec.get("sheets", []):
            sheet_refs(sheet)

    stale_refs = []
    for label, spec in (("before", old), ("after", new)):
        for sheet in spec.get("sheets", []):
            for group, ids in sheet_refs(sheet).items():
                known = indexed(spec.get(group, []), group)
                for key in sorted(ids - set(known)):
                    stale_refs.append({"revision": label, "sheet": sheet["number"],
                                       "group": group, "id": key})

    stale_model_refs = [
        issue for label, spec in (("before", old), ("after", new))
        for issue in stale_model_links(spec, label)
    ]

    changes = []
    schedules = set()
    if stale_model_refs:
        # Broken source relationships may affect any sheet and any derived
        # dimensional schedule; never silently issue an unchanged verdict.
        schedules.update(("door-schedule.csv", "window-schedule.csv",
                          "room-schedule.csv"))
    for group in GROUPS:
        before_items = indexed(old.get(group, []), group)
        after_items = indexed(new.get(group, []), group)
        for key in sorted(set(before_items) | set(after_items)):
            before, after = before_items.get(key), after_items.get(key)
            if before == after:
                continue
            fields = sorted(set(before or {}) | set(after or {}))
            fields = [f for f in fields if f not in (before or {}) or f not in (after or {})
                      or before[f] != after[f]]
            if group == "openings":
                for item in (before, after):
                    if item:
                        schedules.add(SCHEDULES["openings"].get(item.get("kind"), "opening-schedule-UNKNOWN"))
            if group == "rooms":
                schedules.add(SCHEDULES["rooms"])
                if any(o.get("kind") == "door" and o.get("receiving_room") == key
                       for spec in (old, new) for o in spec.get("openings", [])):
                    schedules.add(SCHEDULES["openings"]["door"])
            if group in ("levels", "walls"):
                # Without full room-wall topology, changing a wall or level
                # can alter hosted openings, room quantities and schedules.
                schedules.update(("door-schedule.csv", "window-schedule.csv",
                                  "room-schedule.csv"))
            changes.append({
                "group": group,
                "id": key,
                "operation": "added" if before is None else "removed" if after is None else "modified",
                "changed_fields": fields,
                "affected_indexed_sheets": affected_sheets(group, key, before, after, old, new),
                "references_exhaustive": False,
            })

    old_sheets = indexed(old.get("sheets", []), "sheets")
    new_sheets = indexed(new.get("sheets", []), "sheets")
    sheet_changes = sorted(k for k in set(old_sheets) | set(new_sheets)
                           if old_sheets.get(k) != new_sheets.get(k))
    changed_project_fields = sorted(
        key for key in set(old.get("project", {})) | set(new.get("project", {}))
        if key not in old.get("project", {}) or key not in new.get("project", {})
        or old["project"][key] != new["project"][key]
    )
    if sheet_changes or changed_project_fields:
        schedules.add(SCHEDULES["sheets"])
    # Treat future/extension top-level fields conservatively. Otherwise a
    # site, datum, material or custom document edit can return NO_INDEXED_CHANGES
    # even though generated sheets may depend on it. Presence matters: adding
    # an explicit null is still a document change.
    modeled_fields = set(GROUPS) | {"project", "sheets"}
    changed_document_fields = sorted(
        key for key in (old.keys() | new.keys()) - modeled_fields
        if key not in old or key not in new or old[key] != new[key]
    )
    if "units" in changed_document_fields:
        # A changed length unit can invalidate every dimensional schedule.
        schedules.update(("door-schedule.csv", "window-schedule.csv", "room-schedule.csv"))
    if "standard" in changed_document_fields:
        schedules.add(SCHEDULES["sheets"])

    return {
        "schema_version": 1,
        "status": "REVIEW_REQUIRED" if changes or sheet_changes or changed_project_fields or changed_document_fields or stale_refs or stale_model_refs else "NO_INDEXED_CHANGES",
        "changes": changes,
        "changed_sheets": sheet_changes,
        "changed_project_fields": changed_project_fields,
        "changed_document_fields": changed_document_fields,
        "stale_sheet_references": stale_refs,
        "stale_model_references": stale_model_refs,
        "schedules_to_recheck": sorted(schedules),
        "affected_indexed_sheets": sorted(set(sheet for c in changes for sheet in c["affected_indexed_sheets"]) | set(sheet_changes)
                                         | ({s["number"] for s in old.get("sheets", []) + new.get("sheets", [])} if changed_project_fields or changed_document_fields else set())
                                         | {r["sheet"] for r in stale_refs}
                                         | ({s["number"] for s in old.get("sheets", []) + new.get("sheets", [])} if stale_model_refs else set())),
        "coverage": "PARTIAL: broken host/level/receiving-room links flag all indexed sheets and dimensional schedules; room edits trace declared receiving-room doors; grid and top-level document edits flag indexed sheets; unclassified fields may affect schedules requiring manual review; external elevations, sections, details, linked references and PDF markups require separate inspection",
        "verified_live_host": False,
        "verified_exported_geometry": False,
    }


def _guard_report_destination(output: Path, inputs: tuple[Path, Path]) -> None:
    """Refuse input aliases and output symlinks before writing a review report.

    This guards ordinary path/symlink/hardlink mistakes, not concurrent
    adversarial filesystem replacement. The source JSON files remain read-only.
    """
    if output.is_symlink():
        raise InvalidSpecification("report output must not be a symbolic link")
    for source in inputs:
        if output.resolve() == source.resolve() or (
            output.exists() and source.exists() and output.samefile(source)
        ):
            raise InvalidSpecification("report output aliases an input specification")


def _write_report(output: Path, contents: str, inputs: tuple[Path, Path]) -> None:
    """Atomically replace a report without truncating an existing report on error.

    Creates a temporary file in the destination directory and removes it on
    failure. A successful rename replaces an existing regular report file.
    """
    _guard_report_destination(output, inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=output.parent, prefix=f".{output.name}.", suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck to catch ordinary path changes during report generation.
        _guard_report_destination(output, inputs)
        os.replace(temp_path, output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.add_argument("--out", type=Path, help="optional JSON report path")
    args = p.parse_args(argv)
    try:
        report = analyze(read_spec(args.before), read_spec(args.after))
    except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot assess revision impact: {exc}", file=sys.stderr)
        return 2
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        try:
            _write_report(args.out, output, (args.before, args.after))
        except (ValueError, OSError) as exc:
            print(f"ERROR: cannot write revision-impact report: {exc}", file=sys.stderr)
            return 2
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
