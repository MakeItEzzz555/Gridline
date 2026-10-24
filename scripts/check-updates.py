#!/usr/bin/env python3
"""Opt-in, read-only stable-release discovery; never download or install code."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'MakeItEzzz555/Gridline'
API = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_BYTES = 1_048_576
SEMVER = re.compile(
    r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
    r'(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?'
    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
)


def version_key(value):
    """Return exact SemVer precedence, ignoring build metadata; reject loose tags."""
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('invalid SemVer')
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError('invalid SemVer')
    major, minor, patch, pre, _build = match.groups()
    identifiers = tuple((0, int(x)) if x.isascii() and x.isdigit() else (1, x)
                        for x in pre.split('.')) if pre else ()
    return int(major), int(minor), int(patch), not bool(pre), identifiers


def read_json(stream):
    """Read bounded UTF-8 JSON from a local fixture or an HTTPS response."""
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('release response exceeds 1 MiB')
    try:
        return json.loads(raw.decode("utf-8"))
    except RecursionError as exc:
        raise ValueError("release JSON is too deeply nested") from exc


class NoRedirect(HTTPRedirectHandler):
    """Reject redirects rather than follow a release feed to another origin."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('release feed redirect refused')


def fetch_release():
    """Fetch only the fixed public GitHub endpoint, without credentials or retries."""
    request = Request(API, headers={'Accept': 'application/vnd.github+json',
                                    'User-Agent': 'Gridline-update-checker'})
    with build_opener(NoRedirect()).open(request, timeout=10) as response:
        return read_json(response)


def assess_release(installed, release):
    """Classify stable release metadata without treating it as artifact approval."""
    current = version_key(installed)
    if not isinstance(release, dict):
        raise ValueError('release must be a JSON object')
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('only published stable releases are accepted')
    tag = release.get('tag_name')
    if not isinstance(tag, str) or not tag.startswith('v'):
        raise ValueError('release requires an exact v-prefixed SemVer tag')
    available = tag[1:]
    latest = version_key(available)
    if not latest[3]:
        raise ValueError('prerelease tag cannot be a stable update')
    url = f'https://github.com/{REPOSITORY}/releases/tag/{tag}'
    if release.get('html_url') != url:
        raise ValueError('release URL does not match trusted repository and tag')
    status = 'UPDATE_AVAILABLE' if latest > current else 'CURRENT' if latest == current else 'LOCAL_AHEAD'
    return {'status': status, 'installed_version': installed, 'release_version': available,
            'release_url': url, 'artifact_verification': 'NOT_CHECKED',
            'source_sha': None, 'install_authorized': False,
            'next_step': 'Review release diff, permissions, provenance and checksums before provider-specific installation.'}


def main(argv=None):
    """Print JSON; no network by default, exit 2 for unknown or invalid evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--check-network', action='store_true', help='consent to one public GitHub request')
    source.add_argument('--release-json', type=Path, help='read a captured GitHub release response offline')
    parser.add_argument('--installed-version', help='exact installed SemVer; defaults to this checkout manifest')
    args = parser.parse_args(argv)
    try:
        installed = args.installed_version
        if installed is None:
            installed = json.loads((ROOT / 'plugin.json').read_text())['version']
        version_key(installed)
        if args.release_json:
            with args.release_json.open('rb') as stream:
                release = read_json(stream)
        elif args.check_network:
            release = fetch_release()
        else:
            print(json.dumps({'status': 'UNKNOWN', 'reason': 'NETWORK_NOT_REQUESTED',
                              'installed_version': installed, 'install_authorized': False}))
            return 0
        result = assess_release(installed, release)
        result['evidence'] = 'LOCAL_FIXTURE' if args.release_json else 'PUBLIC_GITHUB_API'
        print(json.dumps(result))
        return 0
    except (URLError, TimeoutError):
        result = {'status': 'UNKNOWN', 'reason': 'OFFLINE_OR_API_UNAVAILABLE'}
    except (ValueError, OSError, KeyError, TypeError):
        result = {'status': 'UNKNOWN', 'reason': 'INVALID_RELEASE_OR_LOCAL_METADATA'}
    print(json.dumps({**result, 'install_authorized': False}))
    return 2


if __name__ == '__main__':
    sys.exit(main())
