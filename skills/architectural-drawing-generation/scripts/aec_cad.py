#!/usr/bin/env python3
"""Coordinated CAD drawing set from one building spec, plus an independent checker.

build: SPEC.json -> per-sheet DXF (model-space plan + paper-space sheet), PDF, and
       room/door/window schedules and a sheet register, all derived from the same spec.
check: reads the outputs back from disk and verifies standards and coordination.

Every dimension comes from the spec; nothing is inferred. Requires ezdxf,
matplotlib for PDF generation and pypdf for mandatory PDF readback.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import sys
from pathlib import Path

# Installed skill bundles also support Python's isolated (-I) invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from building_spec import finite, shape_errors, door_opens
from aec_readback import geometry_check, plan_requirements, pdf_check, TOLERANCE_MM, PDF_TOLERANCE_PT
from aec_receipt import coverage, finish

try:
    import ezdxf
    from ezdxf import bbox
    from ezdxf.enums import TextEntityAlignment
except ImportError:  # the skill must still explain itself without the dependency
    ezdxf = None

REFERENCES = Path(__file__).resolve().parents[1] / "references"
MID = None if ezdxf is None else TextEntityAlignment.MIDDLE_CENTER
LEFT = None if ezdxf is None else TextEntityAlignment.BOTTOM_LEFT
TITLE_FIELDS = ["PROJECT", "CLIENT", "ADDRESS", "TITLE", "NUMBER", "REVISION", "SCALE",
                "SIZE", "STATUS", "DATE", "DRAWN", "CHECKED", "ARCHITECT"]
REQUIRED_TITLE_FIELDS = set(TITLE_FIELDS) - {"CLIENT", "ADDRESS", "CHECKED"}
TB_W, TB_H = 180.0, 64.0  # ISO 7200 title block: at most 180 mm wide


# ---------------------------------------------------------------- inputs

def deep_merge(base, override):
    out = dict(base)
    for key, value in override.items():
        out[key] = deep_merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def load_profile(name: str, sources=None, seen=None) -> dict:
    """A built-in profile name, or a path to an office profile that may say "extends": "<built-in>"."""
    builtin = REFERENCES / "standards" / f"{name}.json"
    path = builtin if builtin.exists() else Path(name)
    seen = set() if seen is None else seen
    if path.resolve() in seen:
        raise ValueError("cyclic standards profile inheritance")
    seen.add(path.resolve())
    data = read_json(path, sources)
    parent = data.pop("extends", None)
    return deep_merge(load_profile(parent, sources, seen), data) if parent else data


def read_json(path, sources=None):
    if sources is not None:
        sources[str(path)] = None
    with path.open("rb") as stream:
        data = stream.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError(f"{path.name}: JSON exceeds 10 MiB limit")
    if sources is not None:
        sources[str(path)] = data
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: root must be an object")
    return value


def load(spec_path: Path, standard: str | None, sources=None):
    spec = read_json(spec_path, sources)
    spec.setdefault("project", {})
    for group in ("levels", "grids", "walls", "openings", "rooms", "sheets"):
        spec.setdefault(group, [])
    return spec, load_profile(standard or spec.get("standard", "iso13567"), sources)


# ---------------------------------------------------------------- geometry (mm)

def area_m2(points) -> float:
    s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))
    return abs(s) / 2 / 1e6


def centroid(points):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    return (cx / (3 * a), cy / (3 * a)) if a else points[0]


def frame(wall):
    (x1, y1), (x2, y2) = wall["start"], wall["end"]
    length = math.hypot(x2 - x1, y2 - y1)
    u = ((x2 - x1) / length, (y2 - y1) / length) if length else (1.0, 0.0)
    return (x1, y1), u, (-u[1], u[0]), length  # start, direction, left normal, length


def at(start, u, n, s, d=0.0):
    return (start[0] + u[0] * s + n[0] * d, start[1] + u[1] * s + n[1] * d)


def distance_to_segment(p, wall):
    start, u, _, length = frame(wall)
    s = max(0.0, min(length, (p[0] - start[0]) * u[0] + (p[1] - start[1]) * u[1]))
    q = at(start, u, (0, 0), s)
    return math.hypot(p[0] - q[0], p[1] - q[1])


def extensions(wall, walls):
    """Extend a wall end that meets another wall by half that wall's thickness, so corners and T-joints close."""
    ext = []
    for end in (wall["start"], wall["end"]):
        hosts = [w["thickness"] / 2 for w in walls if w is not wall and distance_to_segment(end, w) < 1.0]
        ext.append(max(hosts, default=0.0))
    return ext


def readable(angle: float) -> float:
    """Dimension angle in (-90, 90] so text reads from the bottom or the right, never upside down."""
    a = angle % 180
    return a - 180 if a > 90 else a


def outward(wall, middle):
    start, u, n, length = frame(wall)
    mid = at(start, u, n, length / 2)
    return n if (mid[0] - middle[0]) * n[0] + (mid[1] - middle[1]) * n[1] > 0 else (-n[0], -n[1])


# ---------------------------------------------------------------- validation

def validate(spec: dict, profile: dict) -> list[str]:
    errors = shape_errors(spec)
    if errors:
        return errors
    project = spec.get("project", {})
    for key in ("name", "number", "architect", "drawn_by", "status", "revision", "date"):
        if not str(project.get(key, "")).strip():
            errors.append(f"project.{key} is required")
    status = project.get("status")
    if status and status not in profile["statuses"]:
        errors.append(f"project.status {status!r} is not one of {profile['statuses']}")
    if status in profile["issued_statuses"] and not str(project.get("checked_by", "")).strip():
        errors.append(f"status {status!r} needs project.checked_by: issued drawings must be checked")
    if spec.get("units") != "mm":
        errors.append("units must be explicitly supplied as mm")

    ids = {}
    for group in ("levels", "grids", "walls", "openings", "rooms"):
        for item in spec.get(group, []):
            if item.get("id") in ids:
                errors.append(f"duplicate id {item.get('id')!r} in {group} and {ids[item['id']]}")
            ids[item.get("id")] = group
    levels = {lv["id"] for lv in spec.get("levels", [])}
    if not levels:
        errors.append("at least one level is required")
    for lv in spec["levels"]:
        if not finite(lv.get("elevation")) or not finite(lv.get("height")) or lv.get("height", 0) <= 0:
            errors.append(f"level {lv['id']}: finite elevation and positive height are required")
        if not isinstance(lv.get("name"), str) or not lv["name"].strip():
            errors.append(f"level {lv['id']}: name is required")
    walls = {}
    for w in spec.get("walls", []):
        missing = [k for k in ("id", "level", "type", "start", "end", "thickness") if k not in w]
        if missing:
            errors.append(f"wall {w.get('id', '?')}: missing {', '.join(missing)}")
        else:
            walls[w["id"]] = w

    for w in walls.values():
        if w.get("level") not in levels:
            errors.append(f"wall {w['id']}: unknown level {w.get('level')!r}")
        if w.get("type") not in ("external", "internal"):
            errors.append(f"wall {w['id']}: type must be external or internal")
        if not (w.get("thickness", 0) > 0) or not finite(frame(w)[3]) or frame(w)[3] <= 0:
            errors.append(f"wall {w['id']}: needs a positive thickness and length")

    by_wall = {}
    for o in spec.get("openings", []):
        missing = [k for k in ("id", "kind", "wall", "offset", "width", "height") if k not in o]
        if missing:
            errors.append(f"opening {o.get('id', '?')}: missing {', '.join(missing)}")
            continue
        wall = walls.get(o.get("wall"))
        if wall is None:
            errors.append(f"opening {o['id']}: unknown wall {o.get('wall')!r}")
            continue
        if o.get("kind") not in ("door", "window"):
            errors.append(f"opening {o['id']}: kind must be door or window")
        if not (o.get("width", 0) > 0 and o.get("height", 0) > 0):
            errors.append(f"opening {o['id']}: width and height must be positive")
        if not (0 <= o.get("offset", -1) and o.get("offset", 0) + o.get("width", 0) <= frame(wall)[3]):
            errors.append(f"opening {o['id']}: does not fit inside wall {wall['id']} "
                          f"(offset {o.get('offset')} + width {o.get('width')} > length {frame(wall)[3]:.0f})")
        if o.get("kind") == "door":
            try:
                door_opens(o, wall, spec["rooms"])
            except ValueError as exc:
                errors.append(str(exc))
        level = next((lv for lv in spec["levels"] if lv["id"] == wall.get("level")), None)
        sill = o.get("sill") if o["kind"] == "window" else 0
        if not finite(sill) or sill < 0:
            errors.append(f"opening {o['id']}: explicit nonnegative sill is required for windows")
        elif level and finite(level.get("height")) and sill + o["height"] > level["height"]:
            errors.append(f"opening {o['id']}: sill plus height exceeds host level height")
        by_wall.setdefault(wall["id"], []).append(o)
    for wall_id, items in by_wall.items():
        items = sorted(items, key=lambda o: o.get("offset", 0))
        for a, b in zip(items, items[1:]):
            if a.get("offset", 0) + a.get("width", 0) > b.get("offset", 0):
                errors.append(f"openings {a['id']} and {b['id']} overlap in wall {wall_id}")

    for g in spec.get("grids", []):
        if "start" not in g or "end" not in g or not finite(frame(g)[3]) or frame(g)[3] <= 0:
            errors.append(f"grid {g.get('id', '?')}: needs distinct start and end points")
    for r in spec.get("rooms", []):
        if r.get("level") not in levels:
            errors.append(f"room {r['id']}: unknown level {r.get('level')!r}")
        if len(r.get("boundary", [])) < 3 or not finite(area_m2(r.get("boundary", []))) or area_m2(r.get("boundary", [])) <= 0:
            errors.append(f"room {r['id']}: boundary needs at least three points enclosing an area")
        if not str(r.get("name", "")).strip():
            errors.append(f"room {r['id']}: name is required")

    numbers = set()
    for sh in spec.get("sheets", []):
        if not re.fullmatch(profile["sheet_number_pattern"], str(sh.get("number", ""))):
            errors.append(f"sheet {sh.get('number')!r}: number does not match {profile['sheet_number_pattern']}")
        if sh.get("number") in numbers:
            errors.append(f"duplicate sheet number {sh.get('number')!r}")
        numbers.add(sh.get("number"))
        if sh.get("level") not in levels:
            errors.append(f"sheet {sh.get('number')}: unknown level {sh.get('level')!r}")
        elif not any(w.get("level") == sh["level"] for w in walls.values()):
            errors.append(f"sheet {sh.get('number')}: no walls on level {sh['level']}")
        if sh.get("scale") not in profile["scales"]:
            errors.append(f"sheet {sh.get('number')}: scale 1:{sh.get('scale')} is not a standard scale")
        if sh.get("size") not in profile["paper"]:
            errors.append(f"sheet {sh.get('number')}: unknown paper size {sh.get('size')!r}")
        if not str(sh.get("title", "")).strip():
            errors.append(f"sheet {sh.get('number')}: title is required")
    if not spec.get("sheets"):
        errors.append("at least one sheet is required")
    return errors


# ---------------------------------------------------------------- drawing

def new_document(profile: dict, scale: int):
    doc = ezdxf.new("R2018", setup=True, units=ezdxf.units.MM)
    doc.appids.add("GRIDLINE")
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2
    doc.header["$PSLTSCALE"] = 1
    doc.header["$LTSCALE"] = 1
    for spec in profile["layers"].values():
        layer = doc.layers.add(spec["name"], color=spec["color"], linetype=spec["linetype"])
        layer.dxf.lineweight = spec["lineweight"]
        layer.dxf.plot = 1 if spec["plot"] else 0
    style = doc.dimstyles.new(f"AAS-1-{scale}")
    style.dxf.dimtxt = profile["text_mm"]["dimension"]
    style.dxf.dimscale = scale
    style.dxf.dimasz = 1.5
    style.dxf.dimexe = 1.5
    style.dxf.dimexo = 1.0
    style.dxf.dimgap = 0.6
    style.dxf.dimtad = 1
    style.dxf.dimtih = 0
    style.dxf.dimtoh = 0
    style.dxf.dimdec = 0
    style.dxf.dimlunit = 2
    style.set_arrows(blk=ezdxf.ARROWS.architectural_tick)
    return doc


def text(layout, value, point, height, layer, align=None, rotation=0.0):
    entity = layout.add_text(str(value), height=height, rotation=rotation, dxfattribs={"layer": layer})
    entity.set_placement(point, align=align or MID)
    return entity


def draw_plan(msp, spec, profile, level_id, scale):
    L = {k: v["name"] for k, v in profile["layers"].items()}
    tm = {k: v * scale for k, v in profile["text_mm"].items()}  # model-space text heights
    walls = [w for w in spec["walls"] if w["level"] == level_id]
    openings = {}
    for o in spec["openings"]:
        openings.setdefault(o["wall"], []).append(o)
    pts = [p for w in walls for p in (w["start"], w["end"])]
    middle = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (0, 0)

    # Grid lines run past the outer dimension chain (18 mm) so bubbles at both ends never touch it.
    corners = [at(*frame(w)[:3], s, d) for w in walls for s in (0, frame(w)[3]) for d in (-w["thickness"] / 2, w["thickness"] / 2)]
    r = profile["text_mm"]["grid"] * scale
    reach = 26 * scale
    for g in spec.get("grids", []):
        origin, gu, _, _ = frame(g)
        along = [(p[0] - origin[0]) * gu[0] + (p[1] - origin[1]) * gu[1] for p in corners] or [0.0, frame(g)[3]]
        ends = (min(along) - reach, max(along) + reach)
        msp.add_line(at(origin, gu, (0, 0), ends[0]), at(origin, gu, (0, 0), ends[1]), dxfattribs={"layer": L["grid"]})
        for s in (ends[0] - r, ends[1] + r):
            c = at(origin, gu, (0, 0), s)
            msp.add_circle(c, r, dxfattribs={"layer": L["grid_tag"]})
            text(msp, g["id"], c, tm["grid"], L["grid_tag"])

    for w in walls:
        start, u, n, length = frame(w)
        t = w["thickness"]
        e0, e1 = extensions(w, walls)
        cuts = sorted((o["offset"], o["offset"] + o["width"]) for o in openings.get(w["id"], []))
        solid, s = [], -e0
        for a, b in cuts:
            solid.append((s, a))
            s = b
        solid.append((s, length + e1))
        layer = L["wall_external" if w["type"] == "external" else "wall_internal"]
        for a, b in solid:
            if b - a < 1e-6:
                continue
            outline = [at(start, u, n, a, -t / 2), at(start, u, n, b, -t / 2), at(start, u, n, b, t / 2), at(start, u, n, a, t / 2)]
            msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": layer}).set_xdata("GRIDLINE", [(1000, w["id"])])
            hatch = msp.add_hatch(dxfattribs={"layer": L["wall_poche"]})
            hatch.set_solid_fill(color=256)
            hatch.paths.add_polyline_path(outline, is_closed=True)

        out = outward(w, middle)
        for o in openings.get(w["id"], []):
            a, b = o["offset"], o["offset"] + o["width"]
            for s in (a, b):  # jambs
                msp.add_line(at(start, u, n, s, -t / 2), at(start, u, n, s, t / 2), dxfattribs={"layer": L["opening"]}).set_xdata("GRIDLINE", [(1000, o["id"])])
            if o["kind"] == "window":
                for d in (-t / 2, 0.0, t / 2):
                    msp.add_line(at(start, u, n, a, d), at(start, u, n, b, d), dxfattribs={"layer": L["opening"]}).set_xdata("GRIDLINE", [(1000, o["id"])])
                swing = None
            else:
                side = n if door_opens(o, w, spec["rooms"]) == "left" else (-n[0], -n[1])
                hinge_s, free_s = (a, b) if o["hinge"] == "start" else (b, a)
                sign = 1 if side == n else -1
                hinge = at(start, u, n, hinge_s, sign * t / 2)
                tip = (hinge[0] + side[0] * o["width"], hinge[1] + side[1] * o["width"])
                msp.add_line(hinge, tip, dxfattribs={"layer": L["opening"]}).set_xdata("GRIDLINE", [(1000, o["id"])])
                leaf = math.degrees(math.atan2(side[1], side[0]))
                closed_dir = (u[0], u[1]) if free_s > hinge_s else (-u[0], -u[1])
                closed = math.degrees(math.atan2(closed_dir[1], closed_dir[0]))
                a1, a2 = (closed, leaf) if (free_s > hinge_s) == (sign > 0) else (leaf, closed)
                msp.add_arc(hinge, o["width"], a1, a2, dxfattribs={"layer": L["opening"]}).set_xdata("GRIDLINE", [(1000, o["id"])])
                swing = side
            # Tags stay off the outside (dimension chains) and clear of a door's swing.
            tag_side = (-out[0], -out[1]) if w["type"] == "external" else (-swing[0], -swing[1]) if swing else n
            d = t / 2 + 4 * scale + (o["width"] if swing == tag_side else 0)
            mid = at(start, u, n, (a + b) / 2)
            text(msp, o["id"], (mid[0] + tag_side[0] * d, mid[1] + tag_side[1] * d), tm["tag"], L["opening_tag"])

        if w["type"] == "external":
            sign = 1 if out == n else -1
            marks = sorted({-e0, length + e1, *[s for c in cuts for s in c]})
            face = t / 2 * sign
            style = f"AAS-1-{scale}"
            for offset_mm, points in ((10, marks), (18, [marks[0], marks[-1]])):
                if len(points) < 2 or (offset_mm == 18 and len(marks) == 2):
                    continue
                base = at(start, u, n, 0, face + sign * offset_mm * scale)
                msp.add_multi_point_linear_dim(base=base, points=[at(start, u, n, s, face) for s in points],
                                               angle=readable(math.degrees(math.atan2(u[1], u[0]))), dimstyle=style,
                                               dxfattribs={"layer": L["dimension"]})

    for r in spec.get("rooms", []):
        if r["level"] != level_id:
            continue
        msp.add_lwpolyline(r["boundary"], close=True, dxfattribs={"layer": L["room_boundary"]}).set_xdata("GRIDLINE", [(1000, r["id"])])
        cx, cy = centroid(r["boundary"])
        text(msp, r["name"], (cx, cy + 0.8 * tm["room_name"]), tm["room_name"], L["room_tag"])
        text(msp, f"{area_m2(r['boundary']):.2f} m²", (cx, cy - 0.8 * tm["room_area"]), tm["room_area"], L["room_tag"])


def title_block(doc, profile):
    L = {k: v["name"] for k, v in profile["layers"].items()}
    small, value = profile["text_mm"]["note"], 3.5
    block = doc.blocks.new("AAS-TITLE-BLOCK")
    attrs = {"layer": L["titleblock"]}
    block.add_lwpolyline([(0, 0), (TB_W, 0), (TB_W, TB_H), (0, TB_H)], close=True, dxfattribs=attrs)
    # rows from the top: project | client, address | title (tall) | number, rev, scale, size | status, date, drawn, checked | architect
    rows = [(10, [("PROJECT", 1.0)]), (10, [("CLIENT", 0.5), ("ADDRESS", 0.5)]), (14, [("TITLE", 1.0)]),
            (10, [("NUMBER", 0.4), ("REVISION", 0.2), ("SCALE", 0.2), ("SIZE", 0.2)]),
            (10, [("STATUS", 0.4), ("DATE", 0.2), ("DRAWN", 0.2), ("CHECKED", 0.2)]), (10, [("ARCHITECT", 1.0)])]
    y = TB_H
    for height, cells in rows:
        y -= height
        block.add_line((0, y), (TB_W, y), dxfattribs=attrs)
        x = 0.0
        for tag, share in cells:
            w = TB_W * share
            if x > 0:
                block.add_line((x, y), (x, y + height), dxfattribs=attrs)
            label = block.add_text(tag.title(), height=small, dxfattribs=attrs)
            label.set_placement((x + 1.5, y + height - small - 1.0), align=LEFT)
            size = profile["text_mm"]["sheet_title"] if tag == "TITLE" else value
            block.add_attdef(tag, insert=(x + 1.5, y + 1.5), height=size, dxfattribs=attrs)
            x += w


def draw_sheet(doc, spec, profile, sheet, msp):
    L = {k: v["name"] for k, v in profile["layers"].items()}
    project, scale = spec["project"], sheet["scale"]
    pw, ph = profile["paper"][sheet["size"]]
    m = profile["sheet_margins_mm"]
    psp = doc.layouts.new(sheet["number"])
    psp.page_setup(size=(pw, ph), margins=(0, 0, 0, 0), units="mm", scale=(1, 1), name=sheet["size"])
    # AutoCAD AUDIT requires the overall paper-space viewport (ID 1) on layer 0.
    for viewport in psp.query("VIEWPORT"):
        if viewport.dxf.id == 1:
            viewport.dxf.layer = "0"
    doc.layouts.delete("Layout1")
    x0, y0, x1, y1 = m["left"], m["bottom"], pw - m["right"], ph - m["top"]
    psp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": L["sheet_frame"]})

    title_block(doc, profile)
    status = project["status"]
    values = {
        "PROJECT": project["name"], "CLIENT": project.get("client", ""), "ADDRESS": project.get("address", ""),
        "TITLE": sheet["title"], "NUMBER": sheet["number"], "REVISION": project["revision"],
        "SCALE": f"1:{scale}", "SIZE": sheet["size"], "STATUS": status, "DATE": project["date"],
        "DRAWN": project["drawn_by"], "CHECKED": project.get("checked_by", ""), "ARCHITECT": project["architect"],
    }
    ref = psp.add_blockref("AAS-TITLE-BLOCK", (x1 - TB_W, y0), dxfattribs={"layer": L["titleblock"]})
    ref.add_auto_attribs(values)

    stamp = status if status in profile["issued_statuses"] else f"{status} - NOT FOR CONSTRUCTION"
    text(psp, stamp, (x1 - TB_W, y0 + TB_H + 4), profile["text_mm"]["stamp"], L["stamp"], align=LEFT)

    # scale bar: five 1 m segments at the sheet scale, bottom left
    seg = 1000 / scale
    for i in range(5):
        cell = [(x0 + 8 + i * seg, y0 + 8), (x0 + 8 + (i + 1) * seg, y0 + 8),
                (x0 + 8 + (i + 1) * seg, y0 + 11), (x0 + 8 + i * seg, y0 + 11)]
        psp.add_lwpolyline(cell, close=True, dxfattribs={"layer": L["annotation"]})
        if i % 2 == 0:
            fill = psp.add_hatch(dxfattribs={"layer": L["annotation"]})
            fill.set_solid_fill(color=256)
            fill.paths.add_polyline_path(cell, is_closed=True)
    note = profile["text_mm"]["note"]
    text(psp, "0", (x0 + 8, y0 + 14), note, L["annotation"])
    text(psp, "5 m", (x0 + 8 + 5 * seg, y0 + 14), note, L["annotation"])
    text(psp, f"SCALE 1:{scale} @ {sheet['size']}", (x0 + 8, y0 + 18), note, L["annotation"], align=LEFT)

    if project.get("north_deg") is not None:
        cx, cy, r = x1 - 18, y1 - 18, 8.0
        a = math.radians(90 + project["north_deg"])
        psp.add_circle((cx, cy), r, dxfattribs={"layer": L["annotation"]})
        tip = (cx + r * math.cos(a), cy + r * math.sin(a))
        left = (cx + 0.5 * r * math.cos(a + 2.5), cy + 0.5 * r * math.sin(a + 2.5))
        right = (cx + 0.5 * r * math.cos(a - 2.5), cy + 0.5 * r * math.sin(a - 2.5))
        psp.add_lwpolyline([tip, left, (cx, cy), right], close=True, dxfattribs={"layer": L["annotation"]})
        text(psp, "N", (cx + 1.6 * r * math.cos(a), cy + 1.6 * r * math.sin(a)), note, L["annotation"])

    # viewport: the drawing area above the title block, locked at the sheet scale
    ext = bbox.extents(msp)
    area_w, area_h = x1 - x0 - 10, y1 - (y0 + TB_H + 12) - 5
    need_w, need_h = ext.size.x / scale, ext.size.y / scale
    if need_w > area_w or need_h > area_h:
        raise ValueError(f"sheet {sheet['number']}: plan needs {need_w:.0f} x {need_h:.0f} mm at 1:{scale} "
                         f"but {sheet['size']} has {area_w:.0f} x {area_h:.0f} mm; use a smaller scale or a larger sheet")
    centre = ((x0 + x1) / 2, (y0 + TB_H + 12 + y1) / 2)
    vp = psp.add_viewport(centre, (area_w, area_h), (ext.center.x, ext.center.y), area_h * scale,
                          dxfattribs={"layer": L["viewport"]})
    vp.dxf.flags |= ezdxf.const.VSF_LOCK_ZOOM
    return psp


def write_pdf(doc, layout, size, path: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration, LineweightPolicy
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    except ImportError:
        return False
    fig = plt.figure(figsize=(size[0] / 25.4, size[1] / 25.4))
    ax = fig.add_axes((0, 0, 1, 1))
    config = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK,
                           lineweight_policy=LineweightPolicy.ABSOLUTE)
    ctx = RenderContext(doc)
    def plot_layers(layers):
        for layer in layers:
            if not doc.layers.get(layer.layer).dxf.plot:
                layer.is_visible = False
    ctx.set_layer_properties_override(plot_layers)
    ctx.set_current_layout(layout)
    Frontend(ctx, MatplotlibBackend(ax, adjust_figure=False), config=config).draw_layout(layout, finalize=True)
    ax.set_xlim(0, size[0])
    ax.set_ylim(0, size[1])
    ax.set_aspect("equal")
    ax.axis("off")
    title = next(e for e in layout.query("INSERT") if e.dxf.name == "AAS-TITLE-BLOCK")
    values = {a.dxf.tag: a.dxf.text for a in title.attribs}
    # Project number is not a title-block attribute; project name anchors identity.
    identity = f"Gridline {values['PROJECT']} {values['NUMBER']} {values['REVISION']} {values['DATE']}"
    fig.savefig(path, format="pdf", metadata={"Title": identity})
    plt.close(fig)
    return True


def write_csv(path: Path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def build(spec_path: Path, out: Path, standard: str | None) -> int:
    try:
        spec, profile = load(spec_path, standard)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(f"ERROR: invalid input: {exc}", file=sys.stderr)
        return 1
    errors = validate(spec, profile)
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)
    levels = {lv["id"]: lv for lv in spec["levels"]}
    walls = {w["id"]: w for w in spec["walls"]}
    pdfs = 0
    for sheet in spec["sheets"]:
        doc = new_document(profile, sheet["scale"])
        msp = doc.modelspace()
        draw_plan(msp, spec, profile, sheet["level"], sheet["scale"])
        try:
            psp = draw_sheet(doc, spec, profile, sheet, msp)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        doc.saveas(out / f"{sheet['number']}.dxf")
        pdfs += write_pdf(doc, psp, profile["paper"][sheet["size"]], out / f"{sheet['number']}.pdf")

    project = spec["project"]
    write_csv(out / "room-schedule.csv", ["id", "name", "level", "area_m2", "perimeter_m"],
              [[r["id"], r["name"], levels[r["level"]]["name"], f"{area_m2(r['boundary']):.2f}",
                f"{sum(math.dist(a, b) for a, b in zip(r['boundary'], r['boundary'][1:] + r['boundary'][:1])) / 1000:.2f}"]
               for r in spec.get("rooms", [])])
    room_doors = any("receiving_room" in o or o.get("opens") == "into_room" for o in spec["openings"] if o["kind"] == "door")
    for kind in ("door", "window"):
        rows = [[o["id"], o.get("type", ""), walls[o["wall"]]["level"], o["wall"], o["width"], o["height"],
                 o.get("sill", "") if kind == "window" else o.get("hinge", "")]
                for o in spec["openings"] if o["kind"] == kind]
        header = ["id", "type", "level", "wall", "width_mm", "height_mm", "sill_mm" if kind == "window" else "hinge"]
        if kind == "door" and room_doors:
            header += ["opens", "receiving_room", "resolved_opens"]
            for row, o in zip(rows, (o for o in spec["openings"] if o["kind"] == "door")):
                row += [o["opens"], o.get("receiving_room", ""), door_opens(o, walls[o["wall"]], spec["rooms"])]
        write_csv(out / f"{kind}-schedule.csv", header, rows)
    write_csv(out / "sheet-register.csv", ["number", "title", "scale", "size", "revision", "status", "date"],
              [[s["number"], s["title"], f"1:{s['scale']}", s["size"], project["revision"], project["status"], project["date"]]
               for s in spec["sheets"]])
    if pdfs < len(spec["sheets"]):
        print(f"ERROR: build incomplete: produced {pdfs}/{len(spec['sheets'])} required PDFs; "
              "check will fail. Install matplotlib (pip install matplotlib).", file=sys.stderr)
        return 1
    print(f"BUILT {len(spec['sheets'])} sheets ({pdfs} PDF) and 4 schedules in {out}")
    return 0


# ---------------------------------------------------------------- checking

def read_csv(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))


def check(spec_path: Path, out: Path, standard: str | None) -> int:
    sources, outputs, gates = {}, {}, coverage()
    errors, warnings, checked = [], [], []
    profile_name = "UNKNOWN"
    try:
        spec, profile = load(spec_path, standard, sources)
        profile_name = profile["name"]
        errors.extend(validate(spec, profile))
        gates["spec"]["status"] = "FAIL" if errors else "PASS"
        if not errors:
            names = [s["number"] + suffix for s in spec["sheets"] for suffix in (".dxf", ".pdf")]
            names += ["room-schedule.csv", "door-schedule.csv", "window-schedule.csv", "sheet-register.csv"]
            for name in names:
                outputs[name] = None
                try:
                    with (out / name).open("rb") as stream:
                        blob = stream.read(64 * 1024 * 1024 + 1)
                    if len(blob) > 64 * 1024 * 1024:
                        errors.append(f"{name}: exceeds supported 64 MiB input limit (not hashed)")
                    else:
                        outputs[name] = blob
                except FileNotFoundError:
                    pass
            for sheet in spec["sheets"]:
                for gate in ("dxf_standards", "dxf_geometry", "pdf_vectors"):
                    gates[gate]["sheets"][sheet["number"]] = {"status": "NOT_RUN"}
            check_outputs(spec, profile, outputs, gates, errors, warnings, checked)
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError, RecursionError, csv.Error,
            ezdxf.DXFError) as exc:
        errors.append(f"validation could not complete: {type(exc).__name__}: {exc}")
        if gates["spec"]["status"] == "NOT_RUN":
            gates["spec"]["status"] = "FAIL"
    return finish(out, profile_name, sources, outputs, gates, errors, warnings, checked)


def check_outputs(spec, profile, outputs, gates, errors, warnings, checked):
    layers = {v["name"]: v for v in profile["layers"].values()}
    L = {k: v["name"] for k, v in profile["layers"].items()}
    minimum = profile["min_text_mm"] - 1e-6
    project = spec["project"]
    if not str(project.get("checked_by", "")).strip():
        warnings.append("project.checked_by is empty: no one has checked these drawings yet")

    for sheet in spec["sheets"]:
        number, scale = sheet["number"], sheet["scale"]
        data = outputs[f"{number}.dxf"]
        if data is None:
            errors.append(f"{number}: {number}.dxf is missing or unavailable")
            continue
        start_errors = len(errors)
        try:
            doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
        except (ValueError, ezdxf.DXFError) as exc:
            errors.append(f"{number}: invalid DXF: {exc}")
            gates["dxf_standards"]["sheets"][number] = {"status": "FAIL"}
            continue
        audit = doc.audit()
        if audit.has_errors or audit.has_fixes:
            errors.append(f"{number}: DXF audit found {len(audit.errors)} errors and {len(audit.fixes)} repairs")
        if doc.header.get("$INSUNITS") != 4:
            errors.append(f"{number}: DXF units must be millimetres")
        for name, want in layers.items():
            layer = doc.layers.get(name) if doc.layers.has_entry(name) else None
            if layer is None:
                errors.append(f"{number}: required layer {name} is missing")
                continue
            got = (layer.dxf.color, layer.dxf.lineweight, layer.dxf.linetype.upper(), bool(layer.dxf.plot))
            if got != (want["color"], want["lineweight"], want["linetype"].upper(), want["plot"]):
                errors.append(f"{number}: layer {name} properties {got} differ from the standard")
        try:
            psp = doc.layouts.get(number)
        except KeyError:
            errors.append(f"{number}: no paper-space layout named {number}")
            gates["dxf_standards"]["sheets"][number] = {"status": "FAIL"}
            continue
        settings = psp.dxf_layout.dxf
        if (settings.plot_paper_units != 1 or settings.plot_type != 5
                or not finite(settings.scale_numerator) or not finite(settings.scale_denominator)
                or settings.scale_denominator <= 0
                or abs(settings.scale_numerator / settings.scale_denominator - 1) > 1e-9):
            errors.append(f"{number}: paper-space plot must use millimetres at 1:1")
        msp = doc.modelspace()
        for space, layout in (("model", msp), ("paper", psp)):
            for e in layout:
                is_main_viewport = e.dxftype() == "VIEWPORT" and e.dxf.get("id", 0) == 1
                if is_main_viewport and e.dxf.layer != "0":
                    errors.append(f"{number}: overall paper-space viewport must be on layer 0")
                if e.dxf.layer not in layers and not is_main_viewport:
                    errors.append(f"{number}: {e.dxftype()} on non-standard layer {e.dxf.layer!r} in {space} space")
                if e.dxf.get("color", 256) != 256 or e.dxf.get("lineweight", -1) != -1:
                    errors.append(f"{number}: {e.dxftype()} on {e.dxf.layer} overrides colour/lineweight; use ByLayer")
                if e.dxftype() == "TEXT":
                    plotted = e.dxf.height / (scale if space == "model" else 1)
                    if plotted < minimum:
                        errors.append(f"{number}: text {e.dxf.text!r} plots at {plotted:.2f} mm, below {profile['min_text_mm']} mm")
        style = doc.dimstyles.get(f"AAS-1-{scale}") if doc.dimstyles.has_entry(f"AAS-1-{scale}") else None
        if style is None or style.dxf.dimtxt < minimum or style.dxf.dimscale != scale:
            errors.append(f"{number}: dimension style AAS-1-{scale} missing or not scaled for 1:{scale}")

        blocks = [e for e in psp.query("INSERT") if e.dxf.name == "AAS-TITLE-BLOCK"]
        if not blocks:
            errors.append(f"{number}: title block missing")
        else:
            values = {a.dxf.tag: a.dxf.text.strip() for a in blocks[0].attribs}
            for tag in REQUIRED_TITLE_FIELDS:
                if not values.get(tag) or values.get(tag).upper() == "UNKNOWN":
                    errors.append(f"{number}: title block field {tag} is empty")
            for a in blocks[0].attribs:
                if a.dxf.height < minimum:
                    errors.append(f"{number}: title block {a.dxf.tag} text below {profile['min_text_mm']} mm")
            expected_title = {
                "PROJECT": project["name"], "CLIENT": project.get("client", ""),
                "ADDRESS": project.get("address", ""), "TITLE": sheet["title"],
                "NUMBER": number, "REVISION": project["revision"],
                "SCALE": f"1:{scale}", "SIZE": sheet["size"],
                "STATUS": project["status"], "DATE": project["date"],
                "DRAWN": project["drawn_by"],
                "CHECKED": project.get("checked_by", ""),
                "ARCHITECT": project["architect"],
            }
            for field, expected in expected_title.items():
                if values.get(field) != str(expected):
                    errors.append(f"{number}: title block {field} differs from authoritative spec")
        stamps = [e.dxf.text for e in psp.query("TEXT") if e.dxf.layer == L["stamp"]]
        if not any(project["status"] in s for s in stamps):
            errors.append(f"{number}: status stamp missing")
        viewports = [v for v in psp.query("VIEWPORT") if v.dxf.get("id", 0) != 1]
        valid_viewports = [v for v in viewports if v.dxf.height > 0 and
                           abs(v.dxf.view_height / v.dxf.height - scale) < 1e-6 and
                           v.dxf.flags & ezdxf.const.VSF_LOCK_ZOOM and not v.dxf.view_twist_angle and
                           tuple(v.dxf.view_direction_vector) == (0, 0, 1)]
        if len(viewports) != 1 or len(valid_viewports) != 1:
            errors.append(f"{number}: no locked viewport at 1:{scale}")

        level_walls = {w["id"] for w in spec["walls"] if w["level"] == sheet["level"]}
        want_tags = {o["id"] for o in spec["openings"] if o["wall"] in level_walls}
        tag_list = [e.dxf.text for e in msp.query("TEXT") if e.dxf.layer == L["opening_tag"]]
        got_tags = set(tag_list)
        if len(tag_list) != len(got_tags):
            errors.append(f"{number}: duplicate opening tags")
        if want_tags != got_tags:
            errors.append(f"{number}: opening tags {sorted(got_tags)} do not match the spec {sorted(want_tags)}")
        room_text = {e.dxf.text for e in msp.query("TEXT") if e.dxf.layer == L["room_tag"]}
        for r in spec.get("rooms", []):
            if r["level"] == sheet["level"]:
                label = f"{area_m2(r['boundary']):.2f} m²"
                if r["name"] not in room_text or label not in room_text:
                    errors.append(f"{number}: room {r['id']} tag missing or area label is not {label}")
        gates["dxf_standards"]["sheets"][number] = {"status": "FAIL" if len(errors) > start_errors else "PASS"}
        requirements = plan_requirements(spec, profile, sheet["level"])
        geometric_errors, evidence = geometry_check(doc, requirements, number, profile)
        errors.extend(geometric_errors)
        gates["dxf_geometry"]["sheets"][number] = {
            "status": "FAIL" if geometric_errors else "PASS", "tolerance_mm": TOLERANCE_MM,
            "expected_primitives": len(requirements), "measured": evidence}
        pdf_data = outputs[number + ".pdf"]
        try:
            if pdf_data is None:
                raise ValueError("required PDF is missing or unavailable")
            pdf_errors, pdf_evidence = pdf_check(pdf_data, spec, profile, sheet, requirements,
                                                valid_viewports[0] if len(valid_viewports) == 1 else None)
            errors.extend(pdf_errors)
            gates["pdf_vectors"]["sheets"][number] = {
                "status": "FAIL" if pdf_errors else "PASS", "tolerance_pt": PDF_TOLERANCE_PT, **pdf_evidence}
        except ImportError:
            errors.append(f"{number}.pdf: mandatory validator unavailable: pip install pypdf==6.21.2")
        except Exception as exc:
            # PDF parsers expose several exception types; every parser failure blocks PASS.
            errors.append(f"{number}.pdf: validation failed: {type(exc).__name__}: {exc}")
            gates["pdf_vectors"]["sheets"][number] = {"status": "FAIL"}
        checked.append(number)
    # Independent, field-complete schedule readback catches stale type, height,
    # sill, wall or level after a client-driven opening change. Width alone is
    # not enough for cross-sheet coordination.
    levels_by_id = {lv["id"]: lv for lv in spec["levels"]}
    walls_by_id = {wall["id"]: wall for wall in spec["walls"]}
    expected_schedules = {
        "room-schedule.csv": {
            room["id"]: {
                "id": room["id"], "name": room["name"],
                "level": levels_by_id[room["level"]]["name"],
                "area_m2": f"{area_m2(room['boundary']):.2f}",
                "perimeter_m": f"{sum(math.dist(a, b) for a, b in zip(room['boundary'], room['boundary'][1:] + room['boundary'][:1])) / 1000:.2f}",
            }
            for room in spec.get("rooms", [])
        }
    }
    room_doors = any("receiving_room" in o or o.get("opens") == "into_room" for o in spec["openings"] if o["kind"] == "door")
    for kind in ("door", "window"):
        expected = {}
        for opening in spec["openings"]:
            if opening["kind"] != kind:
                continue
            row = {
                "id": opening["id"], "type": opening.get("type", ""),
                "level": str(walls_by_id[opening["wall"]]["level"]),
                "wall": opening["wall"], "width_mm": str(opening["width"]),
                "height_mm": str(opening["height"]),
            }
            row["sill_mm" if kind == "window" else "hinge"] = str(
                opening.get("sill", "") if kind == "window" else opening.get("hinge", "")
            )
            if kind == "door" and room_doors:
                row.update(opens=opening["opens"], receiving_room=opening.get("receiving_room", ""),
                           resolved_opens=door_opens(opening, walls_by_id[opening["wall"]], spec["rooms"]))
            expected[opening["id"]] = row
        expected_schedules[f"{kind}-schedule.csv"] = expected

    for name, want in expected_schedules.items():
        if outputs[name] is None:
            errors.append(f"{name} is missing")
            gates["schedules"]["sheets"][name] = {"status": "FAIL"}
            continue
        schedule_start = len(errors)
        rows = read_csv(outputs[name])
        got = {row.get("id"): row for row in rows}
        if len(got) != len(rows) or any(not row.get("id") for row in rows):
            errors.append(f"{name} contains duplicate or missing IDs")
        diff = sorted(
            key for key in set(want) | set(got)
            if got.get(key) != want.get(key)
        )
        if diff:
            errors.append(f"{name} does not match spec fields for {diff}")
        gates["schedules"]["sheets"][name] = {"status": "FAIL" if len(errors) > schedule_start else "PASS"}
        checked.append(name)
    register = outputs["sheet-register.csv"]
    if register is not None:
        got = [(r["number"], r["title"], r["scale"], r["size"], r["revision"], r["status"], r["date"]) for r in read_csv(register)]
        want = [(s["number"], s["title"], f"1:{s['scale']}", s["size"], project["revision"], project["status"], project["date"]) for s in spec["sheets"]]
        if got != want:
            errors.append("sheet-register.csv does not match the sheets in the spec")
        gates["schedules"]["sheets"]["sheet-register.csv"] = {"status": "PASS" if got == want else "FAIL"}
        checked.append("sheet-register.csv")
    else:
        errors.append("sheet-register.csv is missing")
        gates["schedules"]["sheets"]["sheet-register.csv"] = {"status": "FAIL"}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("spec", type=Path, help="building spec JSON")
    parser.add_argument("out", type=Path, help="output folder")
    parser.add_argument("--standard", help="iso13567, ncs, or a path to an office profile JSON")
    args = parser.parse_args()
    if ezdxf is None:
        print("aec_cad.py needs ezdxf: pip install ezdxf matplotlib pypdf", file=sys.stderr)
        sys.exit(2)
    sys.exit((build if args.command == "build" else check)(args.spec, args.out, args.standard))


if __name__ == "__main__":
    main()
