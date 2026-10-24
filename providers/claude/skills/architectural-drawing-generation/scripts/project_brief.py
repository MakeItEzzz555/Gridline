#!/usr/bin/env python3
"""Versioned source-detail intake gate. No native calls and no inferred dimensions."""
import argparse
import copy
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import sys

from building_spec import shape_errors

MAX_BYTES = 1024 * 1024
STATUSES = {'CONFIRMED', 'PROPOSED', 'UNKNOWN', 'CONFLICT', 'BLOCKED'}
MODES = {'CONCEPT', 'EXACT_3D', 'BIM_DELIVERY'}
QUESTIONS = {
    'units': 'Confirm the project length unit (mm or m).',
    'plot_boundary': 'Supply the measured plot boundary and survey source, or mark it UNKNOWN.',
    'floor_to_floor_heights': 'Supply each floor-to-floor height; clear ceiling height is insufficient.',
    'roof': 'Choose and approve the roof geometry; UNDECIDED remains blocked for exact 3D.',
    'reference_scale': 'Supply a calibrated reference scale or one known dimension and its image endpoints.',
}
DETAILS = ('openings', 'facade_profiles', 'roof_parapet', 'storeys', 'balconies', 'railings',
           'frames_mullions', 'finishes', 'colors_roughness', 'edges', 'stairs', 'landscape',
           'lighting', 'camera', 'occluded_geometry')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def approval_hash(record):
    return digest({k: v for k, v in record.items() if k != 'approval'})


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= 1_000_000


def boundary_valid(points):
    if (not isinstance(points, list) or not 3 <= len(points) <= 128
            or any(not isinstance(p, list) or len(p) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1_000_000
                for v in p) for p in points)):
        return False
    if len({tuple(p) for p in points}) != len(points):
        return False
    edges = list(zip(points, points[1:] + points[:1]))
    if abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)) < 1e-9:
        return False
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            boxes_overlap = (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
                             and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])))
            if boxes_overlap and cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0:
                return False
    return True


def validate(brief):
    if not isinstance(brief, dict) or brief.get('schema') != 'gridline-project-brief.v1':
        raise ValueError('unsupported ProjectBrief schema')
    if brief.get('mode') not in MODES:
        raise ValueError('unsupported delivery mode')
    ledger = brief.get('ledger')
    if not isinstance(ledger, dict) or ledger.get('schema') != 'gridline-source-detail-ledger.v1':
        raise ValueError('SourceDetailLedger v1 required')
    if type(ledger.get('revision')) is not int or ledger['revision'] < 1:
        raise ValueError('positive ledger revision required')
    records = ledger.get('records')
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError('bounded records array required')
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('record must be an object')
        key = record.get('key')
        if not isinstance(key, str) or not key.strip() or key in indexed:
            raise ValueError('missing or duplicate detail key')
        indexed[key] = record
        if record.get('status') not in STATUSES or 'value' not in record or 'unit' not in record:
            raise ValueError(f'{key}: status, value and unit required')
        if not isinstance(record.get('literal'), str):
            raise ValueError(f'{key}: literal source text required')
        source = record.get('source')
        if (not isinstance(source, dict) or source.get('kind') not in {'user', 'file', 'survey', 'image', 'host'}
                or not isinstance(source.get('location'), str) or not source['location'].strip()):
            raise ValueError(f'{key}: source kind and location required')
        if source['kind'] == 'image':
            region = source.get('region')
            if (not isinstance(region, list) or len(region) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in region)
                    or region[2] <= region[0] or region[3] <= region[1]):
                raise ValueError(f'{key}: image pixel region [left,top,right,bottom] required')
        confidence = record.get('confidence')
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f'{key}: confidence must be between zero and one')
        revision = record.get('revision')
        if type(revision) is not int or not 1 <= revision <= ledger['revision']:
            raise ValueError(f'{key}: invalid revision')
        if (not isinstance(record.get('evidence'), list)
                or any(not isinstance(x, str) or not x.strip() for x in record['evidence'])):
            raise ValueError(f'{key}: evidence array required')
        targets = record.get('targets')
        if (not isinstance(targets, list) or any(not isinstance(x, str) or not x.strip() for x in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError(f'{key}: unique element targets required')
        disposition = record.get('disposition')
        if disposition not in {'MAPPED', 'OUT_OF_SCOPE', 'UNKNOWN', 'BLOCKED'}:
            raise ValueError(f'{key}: explicit detail disposition required')
        if disposition == 'MAPPED' and not targets:
            raise ValueError(f'{key}: mapped detail requires element targets')
        if disposition != 'MAPPED' and not record.get('reason'):
            raise ValueError(f'{key}: unmapped detail requires a reason')
        if record['status'] == 'CONFIRMED':
            approval = record.get('approval')
            if (record['value'] is None or not record['evidence'] or not isinstance(approval, dict)
                    or not isinstance(approval.get('by'), str) or not approval['by'].strip()
                    or approval.get('record_sha256') != approval_hash(record)):
                raise ValueError(f'{key}: confirmation needs evidence and approval of this exact record')
    return indexed


def evaluate(brief):
    records = validate(brief)
    blockers = []
    questions = []
    def block(key, reason):
        if key not in {x['key'] for x in blockers}:
            blockers.append({'key': key, 'reason': reason})
            questions.append({'key': key, 'question': QUESTIONS.get(key, f'Resolve or explicitly scope out {key} with evidence.')})
    for key in QUESTIONS:
        if key == 'reference_scale':
            continue
        record = records.get(key)
        if not record or record['status'] != 'CONFIRMED' or record['disposition'] != 'MAPPED':
            block(key, record['status'] if record else 'UNKNOWN')
            continue
        value = record['value']
        if key == 'units' and value not in ('mm', 'm'):
            block(key, 'Unsupported units; metric alone must specify mm or m.')
        if key == 'plot_boundary':
            if record['unit'] not in ('mm', 'm') or not boundary_valid(value):
                block(key, 'Measured boundary coordinates and units required.')
        if key == 'floor_to_floor_heights' and (record['unit'] not in ('mm', 'm') or
                not isinstance(value, list) or not value or not all(positive(v) for v in value)):
            block(key, 'Positive floor-to-floor heights and units required.')
        if key == 'roof' and (not isinstance(value, dict) or not isinstance(value.get('type'), str)
                              or value['type'].upper() in ('', 'UNKNOWN', 'UNDECIDED')
                              or not isinstance(value.get('geometry_source'), str) or not value['geometry_source'].strip()):
            block(key, 'Approved roof type and dimensioned geometry source required.')
    images = any(r['source']['kind'] == 'image' for r in records.values())
    if images:
        scale = records.get('reference_scale')
        if not scale or scale['status'] != 'CONFIRMED' or scale['unit'] != 'mm/pixel' or not positive(scale['value']):
            block('reference_scale', 'UNKNOWN or uncalibrated image scale')
        for key in DETAILS:
            record = records.get(key)
            if not record or record['status'] != 'CONFIRMED' or record['disposition'] in ('UNKNOWN', 'BLOCKED'):
                block(key, 'Observable/hidden detail inventory is incomplete or unresolved.')
    for key, record in records.items():
        if (record['disposition'] in ('UNKNOWN', 'BLOCKED')
                or record['status'] == 'CONFLICT'
                or (record['status'] != 'CONFIRMED' and record['disposition'] != 'OUT_OF_SCOPE')):
            block(key, record['status'])
    conflict = any(r['status'] == 'CONFLICT' for r in records.values())
    if brief['mode'] == 'BIM_DELIVERY':
        block('bim_evidence', 'IFC schema, IDS, semantic and native-host delivery evidence not implemented by intake.')
    state = 'CONFLICT' if conflict else ('READY_CONCEPT_ONLY' if brief['mode'] == 'CONCEPT' else 'NEEDS_INPUT') if blockers else 'READY'
    return {'schema': 'gridline-intake-result.v1', 'state': state, 'mode': brief['mode'],
            'brief_sha256': digest(brief), 'blockers': blockers, 'questions': questions[:3],
            'remaining_question_count': max(0, len(questions) - 3),
            'provisional': brief['mode'] == 'CONCEPT', 'native_write_authorized': False,
            'coverage': [{'key': r['key'], 'status': r['status'], 'targets': r['targets'],
                          'disposition': r['disposition']} for r in records.values()],
            'unverified': ['No model construction, image interpretation, reference fidelity or professional acceptance.']}


def to_building_spec(brief, building):
    """Check source shape and height consistency only; geometry validation is downstream."""
    result = evaluate(brief)
    if result['state'] != 'READY' or brief['mode'] != 'EXACT_3D':
        raise ValueError('exact source translation blocked by intake')
    records = validate(brief)
    errors = shape_errors(building)
    if errors:
        raise ValueError('; '.join(errors[:5]))
    if building.get('units') != 'mm':
        raise ValueError('building-spec.v1 requires mm')
    heights = records['floor_to_floor_heights']
    scale = 1000 if heights['unit'] == 'm' else 1
    actual = [x.get('height') for x in building['levels']]
    expected = [v * scale for v in heights['value']]
    if (len(actual) != len(expected) or any(
            type(a) not in (int, float) or not math.isfinite(a)
            or not math.isclose(a, e, rel_tol=0, abs_tol=1e-6)
            for a, e in zip(actual, expected))):
        raise ValueError('source level heights conflict with approved floor-to-floor heights')
    # No geometry-fit or roof/site validation here; existing CAD/host validators remain mandatory.
    return copy.deepcopy(building)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('brief', type=Path)
    args = parser.parse_args(argv)
    try:
        if stat.S_ISLNK(os.lstat(args.brief).st_mode):
            raise ValueError('brief must not be a symlink')
        # Windows lacks O_NOFOLLOW/O_NONBLOCK; retain explicit lstat rejection.
        flags = (os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                 | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
        fd = os.open(args.brief, flags)
        with os.fdopen(fd, 'rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError('brief must be a regular file')
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('brief exceeds 1 MiB')
        brief = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        result = evaluate(brief)
        print(json.dumps(result, indent=2))
        return 0 if result['state'] in ('READY', 'READY_CONCEPT_ONLY') else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('BLOCKED: invalid or inaccessible brief: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
