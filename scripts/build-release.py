#!/usr/bin/env python3
"""Build or verify reproducible, explicitly UNQUALIFIED bundles from a pinned Git SHA."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 10000
GIT_LOCATION_VARS = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
                     'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_PREFIX'}
SHA = re.compile(r'[0-9a-f]{40}')
VERSION = re.compile(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)')
MANIFESTS = ('plugin.json', '.codex-plugin/plugin.json', 'gemini-extension.json',
             'providers/claude/.claude-plugin/plugin.json', 'skills/manifest.json')


def digest(data):
    """Return a content identifier, not a publisher signature."""
    return hashlib.sha256(data).hexdigest()


def encode(value):
    """Use stable, UTF-8 JSON without timestamps or platform-dependent newlines."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def safe_name(name):
    """Reject traversal and Windows aliases before any archive entry is used."""
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('unsafe archive path')
    if PurePosixPath(name).is_absolute() or PurePosixPath(name).as_posix() != name:
        raise ValueError('noncanonical archive path')
    for part in name.split('/'):
        if part in {'', '.', '..'} or part.casefold() == '.git' or part.endswith((' ', '.')):
            raise ValueError('unsafe path component')
        if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            raise ValueError('Windows device path refused')
    return name


def validate_names(names):
    """Reject duplicate/case-colliding files and file/directory conflicts."""
    folded = set()
    for name in names:
        folded_name = unicodedata.normalize('NFC', safe_name(name)).casefold()
        if folded_name in folded:
            raise ValueError('duplicate or case-colliding archive path')
        folded.add(folded_name)
    for name in folded:
        if any(parent.as_posix() in folded for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
            raise ValueError('file/directory conflict')


def git_environment():
    """Keep child Git scoped to --repo without changing caller auth or configuration."""
    return {key: value for key, value in os.environ.items() if key not in GIT_LOCATION_VARS}


def git(repo, *args):
    """Read local Git objects only; never run source scripts or shell commands."""
    result = subprocess.run(['git', '--no-replace-objects', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', str(repo), *args], capture_output=True, check=True, timeout=60, env=git_environment())
    if len(result.stdout) > MAX_BYTES:
        raise ValueError('Git snapshot exceeds 32 MiB')
    return result.stdout


def snapshot(repo, source_sha):
    """Read exact regular blobs and modes; reject links, submodules and archive transforms."""
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ValueError('source requires an exact 40-character commit SHA')
    if git(repo, 'rev-parse', '--verify', source_sha + '^{commit}').decode().strip() != source_sha:
        raise ValueError('source is not the pinned commit')
    records = git(repo, 'ls-tree', '-r', '-z', source_sha).split(b'\0')
    expected = {}
    for record in filter(None, records):
        meta, path = record.split(b'\t', 1)
        mode, kind, blob_sha = meta.decode().split()
        name = safe_name(path.decode('utf-8'))
        if mode not in {'100644', '100755'} or kind != 'blob':
            raise ValueError('links, submodules and special Git entries are unsupported')
        expected[name] = (int(mode[-3:], 8), blob_sha)
    if not expected or len(expected) > MAX_FILES:
        raise ValueError('snapshot file count is out of bounds')
    validate_names(expected)
    files = {}
    raw = git(repo, 'archive', '--format=tar', source_sha)
    total = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            safe_name(member.name.rstrip('/'))
            if member.isdir():
                continue
            if not member.isfile() or member.name not in expected or member.name in files:
                raise ValueError('unexpected archive entry')
            total += member.size
            if total > MAX_BYTES:
                raise ValueError('snapshot payload exceeds 32 MiB')
            data = archive.extractfile(member).read(MAX_BYTES + 1)
            mode, blob_sha = expected[member.name]
            identity = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if identity != blob_sha:
                raise ValueError('Git export substitution changed a tracked blob')
            files[member.name] = (data, mode)
    if set(files) != set(expected):
        raise ValueError('Git export-ignore omitted tracked source files')
    return files, git(repo, 'rev-parse', source_sha + '^{tree}').decode().strip()


def packages(files):
    """Keep root adapters in source; flatten the existing self-contained Claude plugin."""
    versions = {json.loads(files[name][0])['version'] for name in MANIFESTS}
    marketplace = json.loads(files['.claude-plugin/marketplace.json'][0])
    entries = marketplace.get('plugins') if isinstance(marketplace, dict) else None
    if (not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict)
            or marketplace.get('name') != 'gridline'
            or entries[0].get('name') != 'gridline' or entries[0].get('source') != './providers/claude'):
        raise ValueError('unexpected Claude marketplace source')
    versions.update(item['version'] for item in entries)
    if 'distribution.json' in files:
        versions.add(json.loads(files['distribution.json'][0])['version'])
    if len(versions) != 1:
        raise ValueError('manifest version drift')
    version = versions.pop()
    # shortcut: stable three-part versions only; extend when prerelease manifest versions are adopted.
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError('requires an exact stable three-part manifest version')
    prefix = 'providers/claude/'
    claude = {name[len(prefix):]: content for name, content in files.items() if name.startswith(prefix)}
    canonical = {name[len('skills/'):]: value for name, value in files.items() if name.startswith('skills/') and '/' in name[len('skills/'):]}
    mirrored = {name[len('skills/'):]: value for name, value in claude.items() if name.startswith('skills/') and '/' in name[len('skills/'):]}
    if not canonical or canonical != mirrored:
        raise ValueError('whole-folder Claude skill drift')
    for name in ('plugin.json', 'gemini-extension.json', 'GEMINI.md', 'scripts/install-global.sh',
                 'scripts/install-global.ps1', 'README.md', 'LICENSE', 'CHANGELOG.md', '.agents/plugins/marketplace.json'):
        if name not in files:
            raise ValueError('required source entry point missing: ' + name)
    if '.claude-plugin/plugin.json' not in claude:
        raise ValueError('Claude root manifest missing')
    claude['LICENSE'] = files['LICENSE']
    return version, {'source': files, 'claude': claude}


def zip_bytes(files):
    """Store sorted regular entries with fixed date/modes, independent of zlib and OS."""
    validate_names(files)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, (data, mode) in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, data)
    return output.getvalue()


def read_zip(data):
    """Validate all entries in memory; never extract or execute an untrusted ZIP."""
    if len(data) > MAX_BYTES:
        raise ValueError('ZIP exceeds 32 MiB')
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= MAX_FILES:
            raise ValueError('ZIP file count out of bounds')
        validate_names([entry.orig_filename for entry in entries])
        if any(entry.filename != entry.orig_filename for entry in entries):
            raise ValueError('ZIP filename normalization refused')
        if sum(entry.file_size for entry in entries) > MAX_BYTES:
            raise ValueError('ZIP payload exceeds 32 MiB')
        for entry in entries:
            mode = entry.external_attr >> 16
            if (stat.S_IFMT(mode) != stat.S_IFREG or stat.S_IMODE(mode) not in {0o644, 0o755}
                    or entry.compress_type != zipfile.ZIP_STORED or entry.flag_bits & 1):
                raise ValueError('ZIP links, special modes, compression or encryption refused')
            files[entry.filename] = (archive.read(entry), stat.S_IMODE(mode))
    return files


def file_sbom(files, version, source_sha, created):
    """Describe tracked source files only; do not infer runtime dependencies or licenses."""
    entries, checksums, relationships = [], [], []
    package_id = 'SPDXRef-Package-source'
    for index, (name, (content, _mode)) in enumerate(sorted(files.items())):
        identity = f'SPDXRef-File-{index}'
        sha1 = hashlib.sha1(content).hexdigest()
        checksums.append(sha1)
        entries.append({'SPDXID': identity, 'fileName': './' + name,
                        'checksums': [{'algorithm': 'SHA1', 'checksumValue': sha1},
                                      {'algorithm': 'SHA256', 'checksumValue': digest(content)}],
                        'licenseConcluded': 'NOASSERTION', 'licenseInfoInFiles': ['NOASSERTION'],
                        'copyrightText': 'NOASSERTION'})
        relationships.append({'spdxElementId': package_id, 'relationshipType': 'CONTAINS',
                              'relatedSpdxElement': identity})
    relationships.append({'spdxElementId': 'SPDXRef-DOCUMENT', 'relationshipType': 'DESCRIBES',
                          'relatedSpdxElement': package_id})
    return {'spdxVersion': 'SPDX-2.3', 'dataLicense': 'CC0-1.0', 'SPDXID': 'SPDXRef-DOCUMENT',
            'name': 'Gridline tracked-source file SBOM',
            'documentNamespace': 'https://github.com/MakeItEzzz555/Gridline/spdx/' + source_sha,
            'creationInfo': {'created': created, 'creators': ['Tool: gridline-build-release-1'],
                             'comment': 'Reproducible creation date uses the source commit timestamp.'},
            'comment': 'Tracked source files only, including the nested Claude mirror. Excludes external '
                       'Python packages, provider clients and native hosts. No license scan or dependency '
                       'resolution performed; NOASSERTION requires separate review.',
            'packages': [{'SPDXID': package_id, 'name': 'gridline-source', 'versionInfo': version,
                          'downloadLocation': 'NOASSERTION', 'filesAnalyzed': True,
                          'packageVerificationCode': {'packageVerificationCodeValue':
                              hashlib.sha1(''.join(sorted(checksums)).encode()).hexdigest()},
                          'licenseConcluded': 'NOASSERTION', 'licenseDeclared': 'NOASSERTION',
                          'copyrightText': 'NOASSERTION'}],
            'files': entries, 'relationships': relationships}


def candidate(repo, source_sha):
    """Prepare bytes for an unqualified candidate; all provenance starts at Git objects."""
    files, tree = snapshot(repo, source_sha)
    version, bundles = packages(files)
    outputs, inventory, artifacts = {}, {}, []
    for provider, contents in bundles.items():
        name = f'gridline-{version}-{source_sha[:12]}-{provider}.zip'
        data = zip_bytes(contents)
        outputs[name] = data
        artifacts.append({'name': name, 'provider': provider, 'sha256': digest(data), 'size': len(data)})
        inventory[name] = {path: {'sha256': digest(content), 'size': len(content), 'mode': oct(mode)}
                           for path, (content, mode) in sorted(contents.items())}
    outputs['file-inventory.json'] = encode(inventory)
    epoch = int(git(repo, 'show', '-s', '--format=%ct', source_sha).decode().strip())
    created = datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    outputs['sbom.spdx.json'] = encode(file_sbom(files, version, source_sha, created))
    manifest = {'schema_version': 1, 'product': 'gridline', 'version': version,
                'source_sha': source_sha, 'source_tree_sha': tree,
                'qualification': 'UNQUALIFIED_CANDIDATE', 'publish_allowed': False,
                'artifacts': artifacts, 'inventory_sha256': digest(outputs['file-inventory.json']),
                'sbom_sha256': digest(outputs['sbom.spdx.json']),
                'gates': {'independent_review': 'NOT_RUN', 'native_hosts': 'NOT_TESTED',
                          'provider_upgrade_acceptance': 'NOT_TESTED', 'sbom': 'GENERATED_TRACKED_FILES_ONLY',
                          'publisher_attestation': 'NOT_BUILT', 'secret_and_license_review': 'NOT_RUN',
                          'owner_publication_approval': 'NOT_GRANTED'}}
    outputs['release-manifest.json'] = encode(manifest)
    outputs['SHA256SUMS'] = ''.join(f'{digest(data)}  {name}\n' for name, data in sorted(outputs.items())).encode()
    return outputs


def build(repo, source_sha, output):
    """Write a new private directory only; existing output paths are never replaced."""
    outputs = candidate(repo, source_sha)
    output.mkdir(mode=0o700)
    for name, data in sorted(outputs.items()):
        with (output / name).open('xb') as stream:
            stream.write(data)
    return outputs


def verify(repo, source_sha, directory):
    """Compare every candidate byte with trusted local pinned Git, plus ZIP readback.

    Recomputing checksums alone is insufficient: metadata or payload tampering is
    rejected even if the attacker rewrites SHA256SUMS. This does not authenticate
    the local checkout, publisher, professional approvals or remote source.
    """
    expected = candidate(repo, source_sha)
    if {p.name for p in directory.iterdir()} != set(expected):
        raise ValueError('unexpected or missing bundle files')
    for name, data in expected.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('bundle entry must be a regular file')
        with path.open('rb') as stream:
            actual = stream.read(MAX_BYTES + 1)
        if actual != data:
            raise ValueError('candidate differs from pinned source: ' + name)
        if name.endswith('.zip'):
            read_zip(actual)
    return json.loads(expected['release-manifest.json'])


def main(argv=None):
    """Build/verify local candidates; no tag, upload, install or publish command exists."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'build':
            build(args.repo, args.source_sha, args.out)
        receipt = verify(args.repo, args.source_sha, args.out)
        print(json.dumps({'status': 'CANDIDATE_INTEGRITY_VERIFIED', 'source_sha': receipt['source_sha'],
                          'qualification': receipt['qualification'], 'publish_allowed': False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError,
            tarfile.TarError, zipfile.BadZipFile) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(json.dumps({'status': 'BLOCKED', 'reason': reason, 'publish_allowed': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
