"""Fixed-template Blender bpy worker; only invoked with typed Gridline scene data."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def create_material(name, rgb, roughness=0.66, metallic=0.0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*rgb,1)
    mat.use_nodes=True
    p=mat.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value=(*rgb,1)
        p.inputs["Roughness"].default_value=roughness
        p.inputs["Metallic"].default_value=metallic
        if name == "Gridline Glass":
            p.inputs["Alpha"].default_value=0.52
    return mat


def build(scene, out):
    if scene.get("schema") != "gridline-blender-scene.v0":
        raise ValueError("unsupported scene schema")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    world=bpy.context.scene
    world.unit_settings.system="METRIC"
    world.unit_settings.scale_length=1.0
    world.render.engine="BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {
        x.identifier for x in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    } else world.render.engine
    mats={
        "wall":create_material("Gridline Wall",(.69,.73,.77)),
        "door":create_material("Gridline Door",(.34,.41,.47),0.5),
        "glass":create_material("Gridline Glass",(.26,.56,.69),0.22),
    }
    for entry in scene["boxes"]:
        dims=entry["dimensions_m"]
        if not all(0 < d < 2000 and math.isfinite(d) for d in dims):
            raise ValueError("invalid geometry box")
        bpy.ops.mesh.primitive_cube_add(size=1, location=entry["center_m"])
        obj=bpy.context.object
        obj.name=entry["name"]
        obj.dimensions=dims
        obj.rotation_euler[2]=entry["rotation_z"]
        obj["gridline_id"]=entry["gridline_id"]
        obj["gridline_kind"]=entry["kind"]
        obj["gridline_host"]=entry["host"]
        obj["gridline_source_units"]="mm"
        obj["gridline_schema"]="gridline-blender-scene.v0"
        for k,v in entry["metadata"].items():
            if k in ("id", "kind", "host", "source_units", "schema"):
                raise ValueError("metadata cannot replace reserved identity fields")
            if type(v) in (str,int,float,bool):
                obj["gridline_"+k]=v
        obj.data.materials.append(mats[entry["kind"]])
    # A camera and light are for inspection; they are not architectural geometry.
    if scene["boxes"]:
        xs=[b["center_m"][0] for b in scene["boxes"]]
        ys=[b["center_m"][1] for b in scene["boxes"]]
        zs=[b["center_m"][2] for b in scene["boxes"]]
        center=Vector(((min(xs)+max(xs))/2,(min(ys)+max(ys))/2,(min(zs)+max(zs))/2))
        extent=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs),5)
        bpy.ops.object.camera_add(location=center+Vector((extent*1.3,-extent*1.5,extent*1.05)))
        camera=bpy.context.object
        camera.name="Gridline_Inspection_Camera"
        direction=center-camera.location
        camera.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
        world.camera=camera
        camera.data.type="ORTHO"
        camera.data.ortho_scale=extent*2.8
        bpy.ops.object.light_add(type="AREA", location=center+Vector((0,0,extent*1.8)))
        lamp=bpy.context.object
        lamp.name="Gridline_Inspection_Light"
        lamp.data.energy=2000
        lamp.data.shape="DISK"
        lamp.data.size=extent
    world["gridline_model_status"]="SUPPORTED_LOCAL_3D_PREVIEW_ONLY"
    world["gridline_project"]=scene["project"]
    world["gridline_source_units"]="mm"
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"model.blend"),check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(out/"model.glb"),export_format="GLB",
                               export_extras=True,export_cameras=False,export_lights=False)
    print(f"BLENDER_BUILD: {len(scene['boxes'])} mesh objects")


def verify_object(obj, entry, tolerance):
    for key, wanted in {"gridline_id": entry["gridline_id"], "gridline_kind": entry["kind"],
                        "gridline_host": entry["host"], "gridline_source_units": "mm",
                        "gridline_schema": "gridline-blender-scene.v0"}.items():
        if obj.get(key) != wanted:
            raise ValueError(f"identity/host metadata lost: {obj.name} {key}")
    cx, cy, cz = entry["center_m"]
    dx, dy, dz = (v / 2 for v in entry["dimensions_m"])
    angle = entry["rotation_z"]
    c, s = math.cos(angle), math.sin(angle)
    corners = [(cx + c*x - s*y, cy + s*x + c*y, cz + z)
               for x in (-dx, dx) for y in (-dy, dy) for z in (-dz, dz)]
    measured = [tuple(obj.matrix_world @ vertex.co) for vertex in obj.data.vertices]
    if (not measured or len(measured) > 128 or
            any(not math.isfinite(v) for point in measured for v in point)):
        raise ValueError(f"invalid mesh coordinates: {obj.name}")
    # Both directions catch missing corners and extra/deformed vertices, including parenting drift.
    error = max(max(min(math.dist(a, b) for b in corners) for a in measured),
                max(min(math.dist(a, b) for b in measured) for a in corners))
    if error > tolerance:
        raise ValueError(f"world geometry mismatch: {obj.name} ({error} m)")
    materials = obj.data.materials
    expected_material = {"wall": "Gridline Wall", "door": "Gridline Door", "glass": "Gridline Glass"}[entry["kind"]]
    if len(materials) != 1 or materials[0] is None or materials[0].name != expected_material:
        raise ValueError(f"material assignment lost: {obj.name}")
    if any(p.material_index != 0 for p in obj.data.polygons):
        raise ValueError(f"mesh references missing material slot: {obj.name}")
    return {"id": entry["gridline_id"], "host": entry["host"], "kind": entry["kind"],
            "material": materials[0].name, "world_corner_error_m": error,
            "world_min_m": [min(p[i] for p in measured) for i in range(3)],
            "world_max_m": [max(p[i] for p in measured) for i in range(3)]}


def verify(scene,out):
    bpy.ops.wm.open_mainfile(filepath=str(out/"model.blend"))
    units = bpy.context.scene.unit_settings
    if units.system != "METRIC" or abs(units.scale_length - 1) > 1e-9:
        raise ValueError("native scene units changed")
    expected={b["name"]:b for b in scene["boxes"]}
    evidence = {}
    for format_name, tolerance in (("blend", 0.00025), ("glb", 0.001)):
        if format_name == "glb":
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=str(out/"model.glb"))
        objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
        if len(objects) != len(expected) or {obj.name for obj in objects} != set(expected):
            raise ValueError(f"{format_name} mesh identity/count mismatch")
        evidence[format_name] = {obj.name: verify_object(obj, expected[obj.name], tolerance) for obj in objects}
    result={"status":"PASS", "native_mesh_count":len(evidence["blend"]),
            "glb_mesh_count":len(evidence["glb"]), "scope":"SUPPORTED_BOX_GEOMETRY_ONLY",
            "tolerances_m":{"blend":0.00025,"glb":0.001}, "readback":evidence,
            "known_limitations":scene["unverified"] + ["Material appearance/nodes/textures and mesh topology not verified"]}
    (out/"verification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("BLENDER_READBACK_PASS:",len(expected))


def main():
    args=sys.argv[sys.argv.index("--")+1:]
    if len(args)!=3 or args[0] not in ("build","verify"):
        raise SystemExit("usage: Blender --background --python worker -- build|verify scene.json output-dir")
    mode,src,out=args
    scene=json.loads(Path(src).read_text())
    if mode=="build":
        build(scene,Path(out))
    else:
        verify(scene,Path(out))


if __name__=="__main__":
    main()
