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
import sys
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


def read_spec(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
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

    changes = []
    schedules = set()
    for group in GROUPS:
        before_items = indexed(old.get(group, []), group)
        after_items = indexed(new.get(group, []), group)
        for key in sorted(set(before_items) | set(after_items)):
            before, after = before_items.get(key), after_items.get(key)
            if before == after:
                continue
            fields = sorted(set(before or {}) | set(after or {}))
            fields = [f for f in fields if (before or {}).get(f) != (after or {}).get(f)]
            if group == "openings":
                for item in (before, after):
                    if item:
                        schedules.add(SCHEDULES["openings"].get(item.get("kind"), "opening-schedule-UNKNOWN"))
            if group == "rooms":
                schedules.add(SCHEDULES["rooms"])
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
        if old.get("project", {}).get(key) != new.get("project", {}).get(key)
    )
    if sheet_changes or changed_project_fields:
        schedules.add(SCHEDULES["sheets"])
    changed_document_fields = sorted(
        key for key in ("units", "standard", "schema_version")
        if old.get(key) != new.get(key)
    )
    if "units" in changed_document_fields:
        # A changed length unit can invalidate every dimensional schedule.
        schedules.update(("door-schedule.csv", "window-schedule.csv", "room-schedule.csv"))
    if "standard" in changed_document_fields:
        schedules.add(SCHEDULES["sheets"])

    return {
        "schema_version": 1,
        "status": "REVIEW_REQUIRED" if changes or sheet_changes or changed_project_fields or changed_document_fields or stale_refs else "NO_INDEXED_CHANGES",
        "changes": changes,
        "changed_sheets": sheet_changes,
        "changed_project_fields": changed_project_fields,
        "changed_document_fields": changed_document_fields,
        "stale_sheet_references": stale_refs,
        "schedules_to_recheck": sorted(schedules),
        "affected_indexed_sheets": sorted(set(sheet for c in changes for sheet in c["affected_indexed_sheets"]) | set(sheet_changes)
                                         | ({s["number"] for s in old.get("sheets", []) + new.get("sheets", [])} if changed_project_fields or changed_document_fields else set())
                                         | {r["sheet"] for r in stale_refs}),
        "coverage": "PARTIAL: grid and document-setting edits conservatively flag all indexed sheets; external elevations, sections, details, linked references and PDF markups require separate inspection",
        "verified_live_host": False,
        "verified_exported_geometry": False,
    }


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
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
