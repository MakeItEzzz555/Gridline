#!/usr/bin/env python3
"""Prepare a manual, read-only AutoCAD Mac inspection; never launches or controls CAD."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import stat
import sys
import tempfile
import uuid

MAX_BYTES = 16 * 1024 * 1024
APP = Path('/Applications/Autodesk/AutoCAD 2027/AutoCAD 2027.app')
TEMPLATE = Path(__file__).resolve().parents[1] / 'references/inspect.lsp.in'


def read_file(root: Path, name: str, limit: int = MAX_BYTES) -> bytes:
    """Pin every path component; reject symlinks and nonregular/oversized inputs."""
    path = Path(name)
    if path.is_absolute() or not path.parts or any(p in ('.', '..') for p in path.parts):
        raise ValueError('input must be relative to the selected root')
    if not root.is_absolute() or '..' in root.parts:
        raise ValueError('root must be absolute without traversal')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in (*root.parts[1:], *path.parts[:-1]):
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(source)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise ValueError('input must be a bounded regular file')
            with os.fdopen(source, 'rb', closefd=False) as handle:
                data = handle.read(limit + 1)
            if len(data) > limit:
                raise ValueError('input too large')
            return data
        finally:
            os.close(source)
    finally:
        os.close(fd)


def literal(value: str) -> str:
    if not value or len(value) > 2048 or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError('native path must be printable ASCII, at most 2048 characters')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def doctor() -> dict:
    result = {'schema': 'gridline-autocad-doctor.v1', 'host': 'AutoCAD Mac',
              'installed': APP.is_dir(), 'license': 'UNKNOWN', 'transport': 'MANUAL_AUTOLISP_CONSOLE',
              'mcp': 'NOT_CONFIGURED_BY_THIS_ADAPTER', 'read_probe': 'NOT_TESTED',
              'native_open': 'NOT_TESTED', 'audit': 'NOT_TESTED', 'edit_plot': 'NOT_TESTED',
              'dwg_dxf_roundtrip': 'NOT_TESTED', 'allowed_operations': ['inspect_selected_copy'],
              'host_actions_automatic': False}
    if APP.is_dir():
        info = plistlib.loads(read_file(APP, 'Contents/Info.plist', 1024 * 1024))
        result.update(bundle_id=info.get('CFBundleIdentifier'), version=info.get('CFBundleVersion'))
    return result


def prepare(root: Path, drawing: str, workspace: Path) -> dict:
    if Path(drawing).suffix.lower() != '.dxf':
        raise ValueError('first inspection accepts disposable DXF only')
    data = read_file(root, drawing)
    if not data:
        raise ValueError('empty drawing')
    # Private run directory limits exposure; host receives no output filename.
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError('workspace must exist')
    run = Path(tempfile.mkdtemp(prefix='gridline-autocad-', dir=workspace))
    copy = run / 'drawing.dxf'
    probe = uuid.uuid4().hex
    script = TEMPLATE.read_text().replace('@DRAWING@', literal(str(copy))).replace('@PROBE@', literal(probe))
    manifest = {'schema': 'gridline-autocad-session.v1', 'probe_id': probe,
                'copy': str(copy), 'source_sha256': hashlib.sha256(data).hexdigest(),
                'inspector_sha256': hashlib.sha256(script.encode('ascii')).hexdigest(),
                'states': doctor()}
    fd = os.open(run, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name, content in [('drawing.dxf', data), ('inspect.lsp', script.encode('ascii')),
                              ('session.json', (json.dumps(manifest, indent=2) + '\n').encode())]:
            target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            with os.fdopen(target, 'wb') as handle:
                handle.write(content)
    finally:
        os.close(fd)
    return {'session': str(run), 'copy': str(copy), 'load': f'(load {literal(str(run / "inspect.lsp"))})',
            'command': 'GRIDLINEINSPECT', 'rollback': 'Close the disposable copy without saving.'}


def receipt(session: Path, console: str) -> dict:
    manifest = json.loads(read_file(session, 'session.json', 32768))
    source = read_file(session, 'drawing.dxf')
    inspector = read_file(session, 'inspect.lsp', 32768)
    if (hashlib.sha256(source).hexdigest() != manifest['source_sha256'] or
            hashlib.sha256(inspector).hexdigest() != manifest['inspector_sha256']):
        raise ValueError('session source or inspector changed')
    text = read_file(session, console, 1024 * 1024).decode('utf-8')
    blocks = re.findall(r'GRIDLINE_READ_BEGIN\s*(\{[^\n]+\})\s*GRIDLINE_READ_END', text)
    if len(blocks) != 1:
        raise ValueError('exactly one complete host read block required')
    data = json.loads(blocks[0])
    if not isinstance(data, dict):
        raise ValueError('host report must be an object')
    if (data.get('schema') != 'gridline-autocad-read.v1' or data.get('probe_id') != manifest['probe_id']
            or data.get('document') != manifest['copy']):
        raise ValueError('wrong drawing or stale probe')
    if (type(data.get('dbmod_before')) is not int or type(data.get('dbmod_after')) is not int
            or data['dbmod_before'] != data['dbmod_after']):
        raise ValueError('drawing changed during probe')
    count = data.get('model_entity_count')
    types = data.get('entity_types')
    if (type(count) is not int or not 0 <= count <= 100000 or not isinstance(types, list)
            or any(not isinstance(p, list) or len(p) != 2 or not isinstance(p[0], str)
                   or type(p[1]) is not int or p[1] < 0 for p in types)
            or len({p[0] for p in types}) != len(types) or sum(p[1] for p in types) != count):
        raise ValueError('invalid entity counts')
    if (not isinstance(data.get('acadver'), str) or not data['acadver'].startswith('26.')
            or type(data.get('insunits')) is not int or not 0 <= data['insunits'] <= 24
            or not isinstance(data.get('platform'), str) or 'mac' not in data['platform'].lower()):
        raise ValueError('unsupported host or units metadata')
    for key in ('layers', 'layouts', 'viewports'):
        if not isinstance(data.get(key), list) or len(data[key]) > 2048:
            raise ValueError('invalid table metadata')
    if any(not isinstance(x, str) for x in data['layouts']):
        raise ValueError('invalid layout names')
    for layer in data['layers']:
        if (not isinstance(layer, dict) or not isinstance(layer.get('name'), str)
                or any(type(layer.get(k)) is not int for k in ('flags', 'color'))):
            raise ValueError('invalid layer metadata')
    for view in data['viewports']:
        if (not isinstance(view, dict) or not isinstance(view.get('layout'), str)
                or type(view.get('flags')) is not int
                or any(not math.isfinite(float(view[k])) or float(view[k]) <= 0
                       for k in ('paper_height', 'view_height'))):
            raise ValueError('invalid viewport metadata')
    for key in ('extmin', 'extmax'):
        if len(data.get(key, [])) != 3 or not all(math.isfinite(float(v)) for v in data[key]):
            raise ValueError('invalid extents')
    return {'schema': 'gridline-autocad-receipt.v1', 'state': 'READ_PROBED',
            'transport': 'MANUAL_AUTOLISP_CONSOLE', 'evidence_origin': 'OPERATOR_CAPTURE_UNAUTHENTICATED',
            'source_sha256_before': manifest['source_sha256'],
            'source_sha256_after': hashlib.sha256(source).hexdigest(),
            'inspector_sha256': manifest['inspector_sha256'],
            'console_sha256': hashlib.sha256(text.encode()).hexdigest(), 'readback': data,
            'audit': 'NOT_TESTED', 'edit_plot': 'NOT_TESTED', 'dwg_dxf_roundtrip': 'NOT_TESTED',
            'warnings': 'Review native opening/command history; inspector does not capture all host warnings.',
            'limitations': ['Counts cover top-level model-space entities, not nested block contents.',
                            'EXTMIN/EXTMAX are cached host values, not recomputed geometry.',
                            'File hashes do not prove in-memory drawing identity or authenticated host transport.']}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    prep = sub.add_parser('prepare')
    prep.add_argument('--root', type=Path, required=True)
    prep.add_argument('--drawing', required=True)
    prep.add_argument('--workspace', type=Path, required=True)
    rec = sub.add_parser('receipt')
    rec.add_argument('session', type=Path)
    rec.add_argument('console', help='Captured console file relative to session directory')
    args = p.parse_args(argv)
    try:
        result = doctor() if args.command == 'doctor' else (
            prepare(args.root, args.drawing, args.workspace) if args.command == 'prepare'
            else receipt(args.session, args.console))
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'BLOCKED: {type(exc).__name__}: invalid or inaccessible input', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
