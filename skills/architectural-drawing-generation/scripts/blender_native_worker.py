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


def verify(scene,out):
    bpy.ops.wm.open_mainfile(filepath=str(out/"model.blend"))
    expected={b["name"]:b for b in scene["boxes"]}
    mesh_objs=[ob for ob in bpy.data.objects if ob.type=="MESH"]
    if len(mesh_objs)!=len(expected):
        raise ValueError(f"native .blend mesh count {len(mesh_objs)} != {len(expected)}")
    evidence={}
    for ob in mesh_objs:
        if ob.name not in expected:
            raise ValueError(f"unexpected native object {ob.name}")
        e=expected[ob.name]
        if ob.get("gridline_id") != e["gridline_id"]:
            raise ValueError("Gridline ID lost on native object")
        dims=sorted(float(v) for v in ob.dimensions)
        wanted=sorted(e["dimensions_m"])
        if max(abs(a-b) for a,b in zip(dims,wanted))>0.00025:
            raise ValueError(f"native geometry dimension mismatch {ob.name}: {dims}/{wanted}")
        if (Vector(ob.location)-Vector(e["center_m"])).length>0.00025:
            raise ValueError(f"native geometry location mismatch {ob.name}")
        evidence[ob.name]={"id":ob["gridline_id"],"dimension_m":dims}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out/"model.glb"))
    glb_mesh=[ob for ob in bpy.data.objects if ob.type=="MESH"]
    if len(glb_mesh)!=len(expected):
        raise ValueError(f"GLB mesh count {len(glb_mesh)} != {len(expected)}")
    imported={ob.name:ob for ob in glb_mesh}
    if set(imported)!=set(expected):
        raise ValueError(f"GLB object identity mismatch; expected {len(expected)}")
    for name,e in expected.items():
        obj=imported[name]
        dims=sorted(float(v) for v in obj.dimensions)
        want=sorted(e["dimensions_m"])
        if max(abs(a-b) for a,b in zip(dims,want))>0.001:
            raise ValueError(f"GLB dimensions lost for {name}: {dims}/{want}")
        if (Vector(obj.location)-Vector(e["center_m"])).length>0.001:
            raise ValueError(f"GLB location drift for {name}")
    result={"status":"PASS","native_mesh_count":len(mesh_objs),
            "glb_mesh_count":len(glb_mesh),"scope":"SUPPORTED_BOX_GEOMETRY_ONLY",
            "native_inspected":evidence,"known_limitations":scene["unverified"]}
    (out/"verification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("BLENDER_READBACK_PASS:",len(mesh_objs))


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
