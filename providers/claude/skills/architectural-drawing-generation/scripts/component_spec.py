"""Bounded visual component requests; no executable expressions or host edits."""
import hashlib
import json
import math
import re

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}')
# Values are SI metres unless the field explicitly names another unit.
CATALOG = {
    'door': {'width': (.25, 10), 'height': (.25, 10), 'depth': (.05, .5), 'frame_size': (.05, .25)},
    'window': {'width': (.5, 10), 'height': (.2, 10), 'depth': (.07, 1), 'frame_size': (.02, .15)},
    'cabinet': {'width': (.1, 5), 'height': (.1, 5), 'depth': (.1, 3), 'thickness': (.005, .05)},
    'shelves': {'width': (.1, 5), 'height': (.1, 5), 'depth': (.1, 3), 'shelf_count': (1, 12, 'int'), 'side_thickness': (.005, .1), 'shelf_thickness': (.005, .1)},
    'column': {'radius': (.02, 1), 'height': (.1, 10)},
    'stairs': {'width': (.2, 5), 'tread_depth': (.05, 1), 'riser_height': (.05, .5), 'step_count': (1, 32, 'int'), 'tread_thickness': (.005, .1)},
    'roof': {'tiles_x': (1, 16, 'int'), 'tiles_y': (1, 16, 'int'), 'tile_scale': (.01, 3), 'angle_deg': (0, 70), 'thickness': (.001, .1)},
    'books': {'width': (.01, .5), 'height': (.05, 1), 'depth': (.05, 1), 'count': (1, 16, 'int')},
    'lamp': {'base_height': (.1, 2), 'shade_height': (.1, 2)},
    'roller': {'width': (.2, 5), 'height': (.2, 5)},
    'venetian': {'width': (.2, 5), 'height': (.2, 5), 'depth': (.02, .2), 'angle_deg': (0, 80)},
    'curtain': {'width': (.2, 5), 'height': (.2, 5), 'panels': (1, 5, 'int')},
    'window_panel': {'pane_width_cm': (10, 300, 'int'), 'pane_height_cm': (10, 300, 'int')},
}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def number(value, low, high, label, integer=False):
    if type(value) not in ((int,) if integer else (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f'{label}: expected {"integer" if integer else "finite number"} in [{low}, {high}]')


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{label}: expected exactly {sorted(expected)}')


def validate(spec):
    request_keys = ('schema', 'project_id', 'units', 'components') + (('building',) if isinstance(spec,dict) and 'building' in spec else ())
    keys(spec, request_keys, 'request')
    if spec['schema'] != 'gridline-components.v1' or spec['units'] != 'm':
        raise ValueError('explicit gridline-components.v1 schema and m units required')
    if not isinstance(spec['project_id'], str) or not ID.fullmatch(spec['project_id']):
        raise ValueError('invalid project_id')
    components = spec['components']
    if not isinstance(components, list) or not 1 <= len(components) <= 32:
        raise ValueError('expected 1..32 components')
    ids, source_ids = set(), set()
    materials = {}
    for item in components:
        item_keys=('id', 'source_element_id', 'host_id', 'kind', 'parameters', 'position_m', 'rotation_deg', 'material') + (('level_id',) if isinstance(item,dict) and 'level_id' in item else ())
        keys(item, item_keys, 'component')
        if 'level_id' in item and (not isinstance(item['level_id'],str) or not ID.fullmatch(item['level_id'])):
            raise ValueError('invalid level_id')
        for field in ('id', 'source_element_id'):
            if not isinstance(item[field], str) or not ID.fullmatch(item[field]):
                raise ValueError(f'invalid {field}')
        if item['id'] in ids or item['source_element_id'] in source_ids:
            raise ValueError('duplicate component/source identity')
        ids.add(item['id']); source_ids.add(item['source_element_id'])
        if not isinstance(item['host_id'], str) or (item['host_id'] and not ID.fullmatch(item['host_id'])):
            raise ValueError('invalid host_id')
        kind = item['kind']
        if not isinstance(kind, str) or kind not in CATALOG:
            raise ValueError('unsupported component; rooms/host cuts are not component adapters')
        keys(item['parameters'], CATALOG[kind], f'{kind} parameters')
        for name, limits in CATALOG[kind].items():
            number(item['parameters'][name], limits[0], limits[1], name, len(limits) == 3)
        params=item['parameters']
        if kind in ('door','window') and min(params['width'],params['height'])<=2*params['frame_size']+.01:
            raise ValueError('frame leaves no clear interior')
        if kind=='cabinet' and min(params['width'],params['height'],params['depth'])<=4*params['thickness']:
            raise ValueError('cabinet thickness consumes its body')
        if kind=='shelves' and (params['width']<=2*params['side_thickness'] or params['height']<=(params['shelf_count']+2)*params['shelf_thickness']):
            raise ValueError('shelf geometry has no remaining clear space')
        if kind=='stairs' and params['tread_thickness']>=min(params['riser_height'],params['tread_depth'])-.001:
            raise ValueError('stair thickness consumes rise/tread')
        if not isinstance(item['position_m'], list) or len(item['position_m']) != 3:
            raise ValueError('position_m must have three explicit coordinates')
        for value in item['position_m']:
            number(value, -100, 100, 'position_m')
        number(item['rotation_deg'], -360, 360, 'rotation_deg')
        material = item['material']
        material_keys = ('id', 'base_color', 'roughness', 'metallic') + (('asset_plan_sha256','uv_tile_size_m') if isinstance(material,dict) and 'asset_plan_sha256' in material else ())
        keys(material, material_keys, 'material')
        if not isinstance(material['id'], str) or not ID.fullmatch(material['id']):
            raise ValueError('invalid material identity')
        if not isinstance(material['base_color'], list) or len(material['base_color']) != 3:
            raise ValueError('base_color must have three channels')
        for value in material['base_color'] + [material['roughness'], material['metallic']]:
            number(value, 0, 1, 'material channel')
        if 'asset_plan_sha256' in material:
            if not isinstance(material['asset_plan_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',material['asset_plan_sha256']):
                raise ValueError('invalid asset plan SHA256')
            if not isinstance(material['uv_tile_size_m'],list) or len(material['uv_tile_size_m'])!=2:raise ValueError('explicit texture tile dimensions in metres required')
            for value in material['uv_tile_size_m']:number(value,.001,100,'texture tile size')
            if material['base_color'] != [1,1,1] or material['roughness'] != 1 or material['metallic'] != 0:
                raise ValueError('textured recipe requires explicit untinted white, roughness 1, metallic 0')
        if material['id'] in materials and materials[material['id']] != material:
            raise ValueError('material identity reused for different properties')
        materials[material['id']] = material
    if 'building' in spec:
        from blender_native import compile_scene
        from wall_topology import geometry_entries
        building=spec['building']
        scene=compile_scene(building)
        geometry_entries(scene)
        openings={o['id']:o for o in building['openings']}
        walls={w['id']:w for w in building['walls']}
        levels={level['id']:level for level in building['levels']}
        if any(item['material']['id'].startswith('shell_') for item in components):raise ValueError('shell_ material identities are reserved for building previews')
        reserved={e['name'] for e in geometry_entries(scene)} | {'Gridline_Building'}
        canonical_ids={i['id'] for key in ('walls','levels','openings','rooms') for i in building[key]}
        for item in components:
            if item['id'] in reserved or item['id'].startswith('building__'):raise ValueError('component uses a reserved shell identity')
            if not item['host_id']:
                if item['source_element_id'] in canonical_ids:raise ValueError('unhosted component reuses a canonical building identity')
                if item.get('level_id') not in levels: raise ValueError('unhosted building components need an explicit valid level_id')
                continue
            opening=openings.get(item['source_element_id'])
            if opening is None or item['kind'] not in ('door','window') or opening['wall']!=item['host_id'] or opening['kind']!=item['kind']:
                raise ValueError('component does not match a canonical hosted opening')
            wall=walls[opening['wall']];level=levels[wall['level']]
            if 'level_id' in item and item['level_id']!=wall['level']: raise ValueError('component and host levels differ')
            dx=wall['end'][0]-wall['start'][0];dy=wall['end'][1]-wall['start'][1]
            length=math.hypot(dx,dy);offset=opening['offset']+opening['width']/2
            wanted=[(wall['start'][0]+dx/length*offset)/1000,(wall['start'][1]+dy/length*offset)/1000,
                    (level['elevation']+opening.get('sill',0))/1000]
            p=item['parameters'];angle=math.radians(item['rotation_deg'])
            if (any(abs(a-b)>1e-7 for a,b in zip(item['position_m'],wanted))
                    or abs(math.cos(angle)-dx/length)>1e-7 or abs(math.sin(angle)-dy/length)>1e-7
                    or abs(p['width']-opening['width']/1000)>1e-7 or abs(p['height']-opening['height']/1000)>1e-7
                    or p['depth']>wall['thickness']/2000):
                raise ValueError('component dimensions/placement do not fit the canonical opening')
    elif any(item['host_id'] or 'level_id' in item for item in components):
        raise ValueError('hosted components require an explicit canonical building spec')
    return spec


def load(path):
    from archimesh_doctor import read_file
    return validate(json.loads(read_file(path),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON'))))
