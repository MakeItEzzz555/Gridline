"""Shape/type preconditions for building-spec.v1, before geometric arithmetic."""
import math


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def shape_errors(spec):
    errors = []
    if spec.get("schema_version", "building-spec.v1") != "building-spec.v1":
        errors.append("unsupported schema_version (expected building-spec.v1)")
    if not isinstance(spec.get("project"), dict):
        errors.append("project must be an object")
    for group in ("levels", "grids", "walls", "openings", "rooms", "sheets"):
        items = spec.get(group)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            errors.append(f"{group} must be an array of objects")
    if errors:
        return errors

    def numbers(value, path):
        if type(value) in (int, float) and not finite(value):
            errors.append(f"{path} must be finite")
        elif isinstance(value, dict):
            for key, item in value.items():
                numbers(item, f"{path}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                numbers(item, f"{path}[{i}]")
    numbers(spec, "spec")
    for key in ("name", "number", "architect", "drawn_by", "status", "revision", "date"):
        if not isinstance(spec["project"].get(key), str):
            errors.append(f"project.{key} must be a string")
    for key in ("client", "address", "checked_by"):
        if key in spec["project"] and not isinstance(spec["project"][key], str):
            errors.append(f"project.{key} must be a string")
    if "north_deg" in spec["project"] and not finite(spec["project"]["north_deg"]):
        errors.append("project.north_deg must be a finite number")
    numeric = {"levels": ("elevation", "height"), "walls": ("thickness",),
               "openings": ("offset", "width", "height"), "sheets": ("scale",)}
    for group in ("levels", "grids", "walls", "openings", "rooms", "sheets"):
        for index, item in enumerate(spec[group]):
            label = f"{group}[{index}]"
            id_key = "number" if group == "sheets" else "id"
            ident = item.get(id_key)
            if not isinstance(ident, str) or not ident.strip() or len(ident.encode("utf-8")) > 255:
                errors.append(f"{label}.{id_key} must be a nonempty string of at most 255 bytes")
            for key in numeric.get(group, ()):
                # Missing wall/opening fields retain the existing precise diagnostics.
                if key in item and not finite(item[key]):
                    errors.append(f"{label}.{key} must be a finite number, not text or boolean")
            for key in ("level", "wall", "kind", "type", "size", "hinge", "opens", "receiving_room", "operation"):
                if key in item and not isinstance(item[key], str):
                    errors.append(f"{label}.{key} must be a string")
            if group in ("levels", "rooms") and not isinstance(item.get("name"), str):
                errors.append(f"{label}.name must be a string")
            if group in ("walls", "grids"):
                for key in ("start", "end"):
                    if key in item and not point(item[key]):
                        errors.append(f"{label}.{key} must contain exactly two finite numeric coordinates")
            if group == "rooms":
                boundary = item.get("boundary", [])
                if not isinstance(boundary, list) or any(not point(p) for p in boundary):
                    errors.append(f"{label}.boundary must be an array of finite 2D points")
            if group == "openings" and item.get("opens") == "into_room" and item.get("kind") != "door":
                errors.append(f"{label}: into_room is only supported for doors")
            if group == "openings" and "sill" in item and not finite(item["sill"]):
                errors.append(f"{label}.sill must be a finite number")
            if group == "sheets" and isinstance(ident, str) and ("/" in ident or "\\" in ident or ident in (".", "..")):
                errors.append(f"{label}.number cannot contain path separators")
    return errors


def point(value):
    return isinstance(value, list) and len(value) == 2 and all(finite(v) for v in value)


def inside_room(p, boundary):
    """Ray casting including the boundary within 0.01 mm computational tolerance."""
    inside = False
    x, y = p
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx*dx + dy*dy
        t = max(0, min(1, ((x-a[0])*dx + (y-a[1])*dy)/length2)) if length2 else 0
        if math.hypot(x-a[0]-t*dx, y-a[1]-t*dy) <= 0.01:
            return True
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y-a[1])*dx/dy:
            inside = not inside
    return inside


def door_opens(opening, wall, rooms):
    """Resolve opt-in room intent; explicit legacy wall-relative sides stay unchanged."""
    if opening.get('hinge') not in ('start', 'end'):
        raise ValueError(f"door {opening['id']}: hinge must be start|end")
    if opening.get('operation', 'single_hinged') != 'single_hinged':
        raise ValueError(f"door {opening['id']}: only single_hinged operation is supported")
    intent = opening.get('opens')
    if intent in ('left', 'right'):
        return intent
    if intent != 'into_room':
        raise ValueError(f"door {opening['id']}: opens must be left|right|into_room")
    receiving = [r for r in rooms if r['id'] == opening.get('receiving_room')]
    if len(receiving) != 1 or receiving[0].get('level') != wall['level']:
        raise ValueError(f"door {opening['id']}: into_room needs one receiving_room on the host level")
    boundary = receiving[0].get('boundary', [])
    if len(boundary) < 3:
        raise ValueError(f"door {opening['id']}: receiving_room needs a polygon")
    dx, dy = wall['end'][0]-wall['start'][0], wall['end'][1]-wall['start'][1]
    length = math.hypot(dx, dy)
    if not length:
        raise ValueError(f"door {opening['id']}: host wall has zero length")
    ux, uy = dx/length, dy/length
    def point(along, across):
        return (wall['start'][0]+ux*along-uy*across, wall['start'][1]+uy*along+ux*across)
    middle = opening['offset'] + opening['width']/2
    half = wall['thickness']/2
    # A near-face probe establishes association, not a statutory clearance.
    sides = [side for side in (1, -1) if inside_room(point(middle, side*(half+0.02)), boundary)]
    if len(sides) != 1 or not inside_room(point(middle, sides[0]*half), boundary):
        raise ValueError(f"door {opening['id']}: receiving_room is ambiguous or not adjacent to the opening")
    side = sides[0]
    hinge = opening['offset'] + (opening['width'] if opening['hinge'] == 'end' else 0)
    closed = 1 if opening['hinge'] == 'start' else -1
    # Sample the swept sector for room-boundary conflicts; furniture/other doors are not modeled.
    for degrees in range(0, 91, 15):
        angle = math.radians(degrees)
        for radius in (opening['width']/2, opening['width']):
            if not inside_room(point(hinge+closed*radius*math.cos(angle), side*(half+radius*math.sin(angle))), boundary):
                raise ValueError(f"door {opening['id']}: sampled swing leaves receiving_room; review hinge, width and room geometry")
    return 'left' if side == 1 else 'right'
