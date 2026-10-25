"""Independent measurements for Gridline's supported 2D plan primitives.

No generator imports: expected geometry is derived in wall-local coordinates.
Room-intent resolution is shared input validation, not an independent oracle;
tests/test_door_intent.py checks swings against a separate rectangular-room oracle.
XDATA is an association hint, never the geometric oracle or a native identity.
"""
from __future__ import annotations

import io
import math

from building_spec import door_opens

TOLERANCE_MM = 0.01
PDF_TOLERANCE_PT = 0.05


def plan_requirements(spec, profile, level):
    """(element ID, layer, primitive, coordinates) for independently checked items."""
    layers = {key: value["name"] for key, value in profile["layers"].items()}
    walls = [w for w in spec["walls"] if w["level"] == level]
    result = []
    for wall in walls:
        x, y = wall["start"]
        dx, dy = wall["end"][0] - x, wall["end"][1] - y
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        half = wall["thickness"] / 2

        def point(along, across):
            return (x + along * ux - across * uy, y + along * uy + across * ux, 0.0)

        openings = sorted((o for o in spec["openings"] if o["wall"] == wall["id"]),
                          key=lambda o: o["offset"])
        # Joined wall outlines include half the intersecting host thickness.
        extra = []
        for end in (wall["start"], wall["end"]):
            joins = [0.0]
            for other in walls:
                if other is wall:
                    continue
                ax, ay = other["start"]
                vx, vy = other["end"][0] - ax, other["end"][1] - ay
                t = max(0, min(1, ((end[0] - ax) * vx + (end[1] - ay) * vy) / (vx * vx + vy * vy)))
                if math.hypot(end[0] - ax - t * vx, end[1] - ay - t * vy) < 1.0:
                    joins.append(other["thickness"] / 2)
            extra.append(max(joins))
        starts = [-extra[0]] + [o["offset"] + o["width"] for o in openings]
        ends = [o["offset"] for o in openings] + [length + extra[1]]
        layer = layers["wall_" + wall["type"]]
        for a, b in zip(starts, ends):
            if b - a > 1e-6:
                result.append((wall["id"], layer, "LWPOLYLINE",
                               [point(a, -half), point(b, -half), point(b, half), point(a, half)]))
        for opening in openings:
            oid, a, width = opening["id"], opening["offset"], opening["width"]
            layer = layers["opening"]
            for s in (a, a + width):
                result.append((oid, layer, "LINE", [point(s, -half), point(s, half)]))
            if opening["kind"] == "window":
                for across in (-half, 0, half):
                    result.append((oid, layer, "LINE", [point(a, across), point(a + width, across)]))
            else:
                direction = 1 if door_opens(opening, wall, spec["rooms"]) == "left" else -1
                hinge_s = a if opening["hinge"] == "start" else a + width
                hinge = point(hinge_s, direction * half)
                tip = point(hinge_s, direction * (half + width))
                result.append((oid, layer, "LINE", [hinge, tip]))
                closed_sign = 1 if opening["hinge"] == "start" else -1
                closed_angle = math.degrees(math.atan2(uy * closed_sign, ux * closed_sign)) % 360
                open_angle = math.degrees(math.atan2(ux * direction, -uy * direction)) % 360
                first, last = ((closed_angle, open_angle) if closed_sign * direction > 0
                               else (open_angle, closed_angle))
                result.append((oid, layer, "ARC", [hinge, width, first, last]))
    for room in spec["rooms"]:
        if room["level"] == level:
            result.append((room["id"], layers["room_boundary"], "LWPOLYLINE",
                           [(x, y, 0.0) for x, y in room["boundary"]]))
    return result


def near(a, b, tolerance=TOLERANCE_MM):
    return len(a) == len(b) and all(math.isfinite(float(x)) and abs(x - y) <= tolerance for x, y in zip(a, b))


def matches(entity, kind, want):
    if entity.dxftype() != kind or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1):
        return False
    if entity.dxf.get("invisible", 0) or abs(entity.dxf.get("thickness", 0)) > TOLERANCE_MM:
        return False
    if kind == "LINE":
        a, b = tuple(entity.dxf.start), tuple(entity.dxf.end)
        return (near(a, want[0]) and near(b, want[1])) or (near(a, want[1]) and near(b, want[0]))
    if kind == "ARC":
        angle_delta = lambda a, b: abs((a - b + 180) % 360 - 180)
        return (near(tuple(entity.dxf.center), want[0]) and near([entity.dxf.radius], [want[1]])
                and angle_delta(entity.dxf.start_angle, want[2]) < 1e-6
                and angle_delta(entity.dxf.end_angle, want[3]) < 1e-6)
    if (not entity.closed or abs(entity.dxf.elevation) > TOLERANCE_MM or entity.dxf.const_width
            or any(any(abs(v) > 1e-12 for v in p[2:]) for p in entity.get_points())):
        return False
    got = [(p[0], p[1], 0.0) for p in entity.get_points()]
    if len(got) != len(want):
        return False
    return any(all(near(got[(i + shift) % len(got)], p) for i, p in enumerate(order))
               for order in (want, list(reversed(want))) for shift in range(len(got)))


def geometry_check(doc, requirements, sheet, profile):
    errors, evidence = [], []
    layers = {profile["layers"][key]["name"] for key in
              ("wall_external", "wall_internal", "opening", "room_boundary")}
    candidates = [e for e in doc.modelspace() if e.dxf.layer in layers]
    remaining = list(candidates)
    for eid, layer, kind, coordinates in requirements:
        entity = next((e for e in remaining if e.dxf.layer == layer and matches(e, kind, coordinates)), None)
        if entity is None:
            errors.append(f"{sheet}: geometry {eid}: missing or changed {kind} on {layer}")
            continue
        remaining.remove(entity)
        identity = "GEOMETRY_INFERRED"
        if entity.has_xdata("GRIDLINE"):
            tags = entity.get_xdata("GRIDLINE")
            if len(tags) != 1 or tags[0].code != 1000 or tags[0].value != eid:
                errors.append(f"{sheet}: geometry {eid}: incorrect GRIDLINE association at handle {entity.dxf.handle}")
            identity = "GRIDLINE_XDATA"
        evidence.append({"element_id": eid, "handle": entity.dxf.handle, "primitive": kind,
                         "identity": identity,
                         "geometry": ([list(entity.dxf.start), list(entity.dxf.end)] if kind == "LINE" else
                                      [list(entity.dxf.center), entity.dxf.radius, entity.dxf.start_angle,
                                       entity.dxf.end_angle] if kind == "ARC" else
                                      [list(p) for p in entity.get_points("xy")])})
    for e in remaining:
        identity = str(e.get_xdata("GRIDLINE")[0].value) if e.has_xdata("GRIDLINE") and e.get_xdata("GRIDLINE") else "UNKNOWN"
        errors.append(f"{sheet}: geometry {identity}: unexpected or duplicate {e.dxftype()} on {e.dxf.layer}, handle {e.dxf.handle}")
    return errors, evidence


def pdf_check(data, spec, profile, sheet, requirements, viewport):
    """Check page and straight plan segments in the PDF's own vector stream.

    This does not establish raster visibility, clipping, font quality or overlaps.
    """
    from pypdf import PdfReader
    name = sheet["number"] + ".pdf"
    reader = PdfReader(io.BytesIO(data), strict=True)
    errors = []
    if len(reader.pages) != 1:
        return [f"{name}: expected one sheet/page"], {}
    page = reader.pages[0]
    factor = 72 / 25.4
    pw, ph = profile["paper"][sheet["size"]]
    if (not near(tuple(map(float, page.mediabox)), [0, 0, pw * factor, ph * factor], PDF_TOLERANCE_PT)
            or page.cropbox != page.mediabox or page.rotation or page.get("/UserUnit", 1) != 1):
        errors.append(f"{name}: page size, crop, rotation or units differ from required sheet")
    expected_title = f"Gridline {spec['project']['name']} {sheet['number']} {spec['project']['revision']} {spec['project']['date']}"
    title = (reader.metadata or {}).get("/Title", "")
    if title and title != expected_title:
        errors.append(f"{name}: document identity/revision differs from spec")
    segments, path = [], []
    current = first = None

    def visit(op, args, cm, tm):
        nonlocal current, first, path
        def transformed(x, y):
            return (float(x) * cm[0] + float(y) * cm[2] + cm[4],
                    float(x) * cm[1] + float(y) * cm[3] + cm[5])
        if op == b"m":
            current = first = transformed(*args)
        elif op == b"l" and current is not None:
            end = transformed(*args)
            path.append((current, end))
            current = end
        elif op in (b"h", b"s", b"b", b"b*") and current is not None and first is not None:
            path.append((current, first))
            current = first
        if op in (b"S", b"s", b"B", b"B*", b"b", b"b*"):
            segments.extend(path)
        if op in (b"S", b"s", b"B", b"B*", b"b", b"b*", b"n", b"f", b"f*", b"F"):
            path = []
            current = first = None
        if op in (b"c", b"v", b"y"):
            current = transformed(*args[-2:])

    page.extract_text(visitor_operand_before=visit)
    if viewport is None:
        errors.append(f"{name}: no valid DXF viewport for independent plot mapping")
        return errors, {}
    vp = viewport.dxf
    def plotted(p):
        return ((p[0] - vp.view_center_point.x) / sheet["scale"] * factor + vp.center.x * factor,
                (p[1] - vp.view_center_point.y) / sheet["scale"] * factor + vp.center.y * factor)

    measured = 0
    plotted_layers = {layer["name"] for layer in profile["layers"].values() if layer["plot"]}
    for eid, layer, kind, coordinates in requirements:
        if layer not in plotted_layers or kind == "ARC":
            continue
        pairs = ([coordinates] if kind == "LINE" else
                 list(zip(coordinates, coordinates[1:] + coordinates[:1])))
        for a, b in pairs:
            a, b = plotted(a), plotted(b)
            if not any((near(a, c, PDF_TOLERANCE_PT) and near(b, d, PDF_TOLERANCE_PT))
                       or (near(a, d, PDF_TOLERANCE_PT) and near(b, c, PDF_TOLERANCE_PT)) for c, d in segments):
                errors.append(f"{name}: geometry {eid}: missing or incorrectly scaled plotted segment")
            measured += 1
    return errors, {"segments_checked": measured,
                    "identity": "PASS" if title == expected_title else "FAIL" if title else "UNKNOWN"}
