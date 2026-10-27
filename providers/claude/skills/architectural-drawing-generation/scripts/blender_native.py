#!/usr/bin/env python3
"""Opt-in, local Blender export from Gridline's existing building-spec.v1.

Not a native CAD/BIM integration, reference-image reconstructor, or drawing sign-off.
No application preferences, existing models or global MCP settings are changed.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import stat
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SHAPE_DIR = HERE
sys.path.insert(0, str(SHAPE_DIR))
from building_spec import shape_errors, door_opens  # noqa: E402
from wall_topology import geometry_entries  # noqa: E402

DEFAULT_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
MAX_SPEC_BYTES = 1024 * 1024
MAX_ELEMENTS = 400
MAX_COORD_MM = 1_000_000


def _number(v, name, *, positive=False):
    """Return v as a float if finite, within MAX_COORD_MM and, when positive, above 0.

    Otherwise raise ValueError naming the field.
    """
    if type(v) not in (float, int) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number")
    if (positive and v <= 0) or abs(v) > MAX_COORD_MM:
        raise ValueError(f"{name} is invalid or outside supported bounds")
    return float(v)


def compile_scene(spec):
    """Compile a building-spec.v1 dict (mm) into a gridline-blender-scene.v0 dict (m).

    Walls become occupancy boxes split around hosted openings; openings become door or
    glass boxes. The input is deep-copied, never mutated. Raises ValueError for non-mm
    units, shape errors, duplicate IDs, unknown levels or hosts, openings that do not fit
    or overlap, or more than MAX_ELEMENTS entities.
    """
    if not isinstance(spec, dict):
        raise ValueError("building specification must be an object")
    if len(json.dumps(spec)) > MAX_SPEC_BYTES:
        raise ValueError("building specification too large")
    spec = copy.deepcopy(spec)
    for k in ("levels", "walls", "openings", "rooms", "grids", "sheets"):
        spec.setdefault(k, [])
    errors = shape_errors(spec)
    if errors:
        raise ValueError("; ".join(errors[:8]))
    if spec.get("units") != "mm":
        raise ValueError("Gridline Blender bridge requires explicit mm units")
    if not spec["levels"] or not spec["walls"]:
        raise ValueError("at least one level and wall are required")
    if sum(len(spec[k]) for k in ("levels", "walls", "openings")) > MAX_ELEMENTS:
        raise ValueError("too many model entities")
    levels, walls, ids = {}, {}, set()
    for i, level in enumerate(spec["levels"]):
        ident = level["id"]
        if ident in ids:
            raise ValueError(f"duplicate element ID {ident}")
        ids.add(ident)
        levels[ident] = (_number(level.get("elevation"), f"levels[{i}].elevation"),
                         _number(level.get("height"), f"levels[{i}].height", positive=True))
    for i, wall in enumerate(spec["walls"]):
        ident = wall["id"]
        if ident in ids:
            raise ValueError(f"duplicate element ID {ident}")
        ids.add(ident)
        if wall.get("level") not in levels:
            raise ValueError(f"wall {ident}: unknown level")
        p1, p2 = wall.get("start"), wall.get("end")
        if p1 is None or p2 is None:
            raise ValueError(f"wall {ident}: start and end are required")
        for p in (p1, p2):
            for x in p:
                _number(x, f"wall {ident} coordinate")
        length = math.dist(p1, p2)
        _number(length, f"wall {ident} length", positive=True)
        thick = _number(wall.get("thickness"), f"wall {ident} thickness", positive=True)
        if length <= 1 or thick > 5000:
            raise ValueError(f"wall {ident}: unsupported dimensions")
        walls[ident] = (wall, length, thick)
    openings = {name: [] for name in walls}
    for i, op in enumerate(spec["openings"]):
        ident = op["id"]
        if ident in ids:
            raise ValueError(f"duplicate element ID {ident}")
        ids.add(ident)
        host = op.get("wall")
        if host not in walls:
            raise ValueError(f"opening {ident}: unknown wall")
        if op.get("kind") not in ("window", "door"):
            raise ValueError(f"opening {ident}: unsupported kind")
        offset = _number(op.get("offset"), f"opening {ident} offset")
        width = _number(op.get("width"), f"opening {ident} width", positive=True)
        height = _number(op.get("height"), f"opening {ident} height", positive=True)
        sill = (_number(op.get("sill"), f"opening {ident} sill")
                if op["kind"] == "window" else 0.0)
        wall, length, thick = walls[host]
        _, wall_height = levels[wall["level"]]
        if offset < 0 or sill < 0 or offset + width > length + 1e-6 or sill + height > wall_height + 1e-6:
            raise ValueError(f"opening {ident}: does not fit inside wall in 3D")
        if op["kind"] == "door":
            door_opens(op, wall, spec["rooms"])
        openings[host].append((offset, offset + width, sill, sill + height, op))
    boxes, elements = [], []
    def box(kind, gid, host, center, dims, angle, metadata=None):
        """Append one box, converting mm to m; any dimension <= 1e-9 mm skips it."""
        if any(v <= 1e-9 for v in dims):
            return
        boxes.append({"name": f"{kind}_{gid}_{len(boxes):04d}",
                      "kind": kind, "gridline_id": gid, "host": host or "",
                      "center_m": [v / 1000 for v in center],
                      "dimensions_m": [v / 1000 for v in dims],
                      "rotation_z": angle, "metadata": metadata or {}})
    for ident, (w, length, thick) in walls.items():
        theta = math.atan2(w["end"][1] - w["start"][1], w["end"][0] - w["start"][0])
        c, s = math.cos(theta), math.sin(theta)
        zbase, zheight = levels[w["level"]]
        ops = sorted(openings[ident], key=lambda v: v[0])
        for prev, nex in zip(ops, ops[1:]):
            if nex[0] < prev[1] - 1e-6:
                raise ValueError(f"wall {ident}: overlapping hosted openings")
        # Source occupancy cells; worker exports only their union boundary.
        stops = sorted(set([0.0, length] + [p for a,b,*_ in ops for p in (a,b)]))
        for a,b in zip(stops, stops[1:]):
            if b - a <= 1e-6:
                continue
            mid = (a+b)/2
            covering = next((o for o in ops if o[0] < mid < o[1]), None)
            spans = ([(0, covering[2]), (covering[3], zheight)] if covering
                     else [(0, zheight)])
            for low, high in spans:
                if high - low <= 1e-6:
                    continue
                x = w["start"][0] + c * mid
                y = w["start"][1] + s * mid
                box("wall", ident, "", [x, y, zbase + (low + high)/2],
                    [b-a, thick, high-low], theta, {"level":w["level"]})
        elements.append({"id":ident,"kind":"wall","level":w["level"],
                         "length_mm":length,"height_mm":zheight,"thickness_mm":thick})
        for left,right,sill,head,op in ops:
            mid=(left+right)/2
            x=w["start"][0] + c*mid
            y=w["start"][1] + s*mid
            kind = "glass" if op["kind"] == "window" else "door"
            box(kind, op["id"], ident, [x,y,zbase + (sill+head)/2],
                [right-left, min(35, thick/3), head-sill], theta,
                {"opening_kind":op["kind"],"host_id":ident, "sill_mm":sill})
            elements.append({"id":op["id"],"kind":op["kind"],"host":ident,
                             "width_mm":right-left,"height_mm":head-sill,"sill_mm":sill,
                             **({"hinge":op["hinge"], "opens":op["opens"],
                                 "receiving_room":op.get("receiving_room", ""),
                                 "resolved_opens":door_opens(op, w, spec["rooms"])} if kind == "door" else {})})
    # No guessed foundations, ceilings, roofs, furniture or site. They require separate inputs.
    unverified=["Mixed oblique joins unsupported; common rotated orthogonal walls only",
                "Intentional material/level/joint groups are not unioned across boundaries",
                "Materials, window and door manufacturing details are illustrative",
                "Door slabs are closed; room intent metadata does not verify a 3D swing or collision clearance",
                "Roofs, floors, stairs, furnishings, foundations, MEP and site are not generated",
                "Image-reference similarity was not evaluated",
                "Native AutoCAD/DWG and IFC BIM interoperability not tested"]
    return {"schema":"gridline-blender-scene.v0", "source_units":"mm",
            "output_units":"m", "project": spec["project"].get("name","Unnamed"),
            "boxes":boxes,"elements":elements,"unverified":unverified}


def source_bytes(path):
    """Read at most MAX_SPEC_BYTES from a regular file, following no symlink in any component.

    Raises ValueError for '..', non-regular or oversized files; OSError when a
    component is missing or is a symlink.
    """
    # Pin components so source path swaps cannot turn reads into symlink escapes.
    path = Path(path).expanduser().absolute()
    if len(path.parts) < 2:
        raise ValueError('source must name a file')
    if sys.platform == 'darwin' and path.parts[1] in ('tmp', 'var'):
        path = Path('/private').joinpath(*path.parts[1:])
    if '..' in path.parts:
        raise ValueError("source traversal is unsupported")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("source must be a regular file")
            data = handle.read(MAX_SPEC_BYTES + 1)
        if len(data) > MAX_SPEC_BYTES:
            raise ValueError("oversized source")
        return data
    finally:
        os.close(directory)


def load_spec(path):
    """Load a JSON spec through source_bytes, rejecting NaN and Infinity."""
    return json.loads(source_bytes(path), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid {x}")))


def publish(tmp, out, receipts, *, names=("model.blend", "model.glb", "verification.json", "scene.json")):
    """Copy the named files from tmp, plus receipt.json, into a new out directory.

    Never overwrites: out is created with mode 0700 and each file exclusively with 0600,
    opening parents without following symlinks. Raises ValueError for unsafe names or if
    out is swapped during publication; a failure can leave a partial out behind.
    """
    if (not isinstance(names,(tuple,list)) or not names
            or any(not isinstance(name,str) or Path(name).name != name or '\\' in name or name in ('', '.', '..', 'receipt.json') for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('publication names must be distinct regular basenames')
    parent = os.open(out.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in out.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        os.mkdir(out.name, mode=0o700, dir_fd=parent)
        fd = os.open(out.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        for name in (*names, "receipt.json"):
            dest = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(dest, 'wb') as handle:
                if name == 'receipt.json':
                    handle.write((json.dumps(receipts, indent=2, sort_keys=True) + '\n').encode())
                else:
                    with (tmp / name).open('rb') as source:
                        shutil.copyfileobj(source, handle)
                handle.flush()
                os.fsync(handle.fileno())
        current = out.stat(follow_symlinks=False)
        pinned = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise ValueError("output directory changed during publication")
    finally:
        os.close(fd)


def run_blender(blender, worker, command, *args):
    """Run the worker in background Blender (factory startup, no auto-exec, 180 s timeout).

    Returns the CompletedProcess. A nonzero exit raises RuntimeError with the last 1,800
    characters of output; a hang raises subprocess.TimeoutExpired.
    """
    cmd=[str(blender), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1", "--python",
         str(worker), "--", command, *map(str,args)]
    result=subprocess.run(cmd, check=False, timeout=180, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Blender {command} failed (exit {result.returncode}): " +
                           (result.stderr + "\n" + result.stdout)[-1800:])
    return result


def main():
    """CLI: doctor probes the Blender binary; build SPEC OUT compiles, builds, verifies and publishes.

    OUT must be new. Returns 0, or 1 after printing a BLOCKED reason.
    """
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    sub=parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    b=sub.add_parser("build")
    b.add_argument("spec", type=Path)
    b.add_argument("out", type=Path)
    args=parser.parse_args()
    try:
        blender=args.blender.resolve(strict=True)
        if not blender.is_file() or blender.name not in ("Blender", "blender"):
            raise ValueError("not a Blender executable; supply a verified Blender binary")
        version=subprocess.run([str(blender),"--version"],capture_output=True,text=True,timeout=15,check=True).stdout.splitlines()[0]
        if not version.startswith("Blender "):
            raise ValueError("Blender version probe failed")
        if args.command=="doctor":
            print(json.dumps({"host":"Blender","version":version,"executable":str(blender),
                "state":"CLI_VERIFIED","model_readback":"NOT_TESTED","autocad":"NOT_TESTED"},indent=2))
            return 0
        source_file=args.spec.expanduser().absolute()
        consumed=source_bytes(source_file)
        spec=json.loads(consumed, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid {x}")))
        source_hash=hashlib.sha256(consumed).hexdigest()
        scene=compile_scene(spec)
        out=args.out.expanduser().absolute()
        parent=out.parent.resolve(strict=True)
        if out.exists() or out.is_symlink():
            raise ValueError("output path must be new; existing data must not be overwritten")
        if out.name in ("", ".", "..") or parent == Path("/"):
            raise ValueError("unsafe output directory")
        out = parent / out.name
        worker=HERE/"blender_native_worker.py"
        with tempfile.TemporaryDirectory(prefix=".gridline-blender-",dir=parent) as tmp:
            tmp=Path(tmp)
            scene_path=tmp/"scene.json"
            scene_path.write_text(json.dumps(scene,sort_keys=True),encoding="utf-8")
            run_blender(blender,worker,"build",scene_path,tmp)
            run_blender(blender,worker,"verify",scene_path,tmp)
            files={"model.blend":tmp/"model.blend","model.glb":tmp/"model.glb","verification.json":tmp/"verification.json"}
            for name,file in files.items():
                if not file.is_file() or file.stat().st_size == 0:
                    raise ValueError(f"required result {name} missing")
            if hashlib.sha256(source_bytes(source_file)).hexdigest() != source_hash:
                raise ValueError("source changed during build; refusing verification")
            receipts={"status":"SUPPORTED_LOCAL_3D_VERIFIED","blender_version":version,
                      "source_sha256":source_hash,
                      "supported_element_count":len(scene["elements"]),
                      "mesh_count":len(geometry_entries(scene)),
                      "source_occupancy_box_count":len(scene["boxes"]),
                      "files":{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},
                      "adapter_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "worker_sha256":hashlib.sha256(worker.read_bytes()).hexdigest(),
                      "geometry_code_sha256":{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest()
                          for n in ("wall_topology.py","mesh_qa.py","glb_qa.py")},
                      "scene_sha256":hashlib.sha256(scene_path.read_bytes()).hexdigest(),
                      "format_results":{"blend":"PASS", "glb":"PASS", "dwg":"NOT_TESTED", "ifc":"NOT_TESTED"},
                      "unverified":scene["unverified"]}
            publish(tmp, out, receipts)
        print(json.dumps({"output":str(out),**receipts},indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
