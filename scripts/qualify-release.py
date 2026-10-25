#!/usr/bin/env python3
"""Bind immutable candidate bytes to reviewed evidence, live provenance and owner approval."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location('candidate_builder', Path(__file__).with_name('build-release.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
REPO = 'MakeItEzzz555/Gridline'
WORKFLOW = REPO + '/.github/workflows/attest-candidate.yml'
GATES = {'security_review', 'architecture_review', 'tests', 'claude', 'codex',
         'gemini', 'native_declared', 'license_scope', 'secret_scan'}
COMMENT = re.compile(r'https://github\.com/MakeItEzzz555/Gridline/pull/[1-9][0-9]*#issuecomment-([1-9][0-9]*)')
MAX_BYTES = 2 * 1024 * 1024


def pairs(items):
    """Reject ambiguous evidence rather than selecting the last duplicate key."""
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate evidence key')
        result[key] = value
    return result


def decode(raw):
    """Read bounded JSON only; metadata never becomes executable shell text."""
    if len(raw) > MAX_BYTES:
        raise ValueError('evidence exceeds 2 MiB')
    def nonfinite(_value):
        raise ValueError('nonfinite evidence')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path):
    """Require regular evidence files; never follow a final symlink."""
    if path.is_symlink() or not path.is_file():
        raise ValueError('evidence must be a regular file')
    with path.open('rb') as stream:
        return decode(stream.read(MAX_BYTES + 1))


def gh(*args):
    """Use the installed trusted GitHub CLI; fixed callers select endpoints and policies."""
    result = subprocess.run(['gh', *args], capture_output=True, check=True, timeout=120)
    return decode(result.stdout)


def gate_evidence(path, tree):
    """Bind maintainer-reviewed local gate receipts to the exact reviewed source tree.

    These are trusted maintainer inputs, not independent proof that a provider
    test or professional review happened. Live CI, signatures and approval are
    verified separately. Scope descriptions must retain unsupported capabilities.
    """
    index = read(path)
    if not isinstance(index, dict) or set(index) != GATES:
        raise ValueError('every required gate must have exactly one evidence path')
    evidence = {}
    seen = set()
    base = path.parent.resolve()
    for gate, name in sorted(index.items()):
        target = base / builder.safe_name(name)
        resolved = target.resolve()
        if resolved in seen:
            raise ValueError('gate evidence paths must be distinct')
        seen.add(resolved)
        if not resolved.is_relative_to(base):
            raise ValueError('evidence escapes its directory')
        record = read(target)
        if (not isinstance(record, dict) or record.get('gate') != gate or record.get('status') != 'PASS'
                or record.get('source_tree_sha') != tree
                or not isinstance(record.get('scope'), str) or not record['scope'].strip()):
            raise ValueError('gate is missing, unverified or bound to another tree: ' + gate)
        evidence[gate] = {'record': record, 'sha256': builder.digest(builder.encode(record))}
    return evidence


def live_ci(sha):
    """Require successful GitHub Actions checks for this exact source SHA."""
    pages = gh('api', '--hostname', 'github.com', '--paginate', '--slurp', f'repos/{REPO}/commits/{sha}/check-runs?filter=latest&per_page=100')
    if (not isinstance(pages, list) or any(not isinstance(page, dict)
            or not isinstance(page.get('check_runs'), list)
            or any(not isinstance(run, dict) or not isinstance(run.get('app'), dict)
                   for run in page['check_runs']) for page in pages)):
        raise ValueError('unexpected CI response')
    runs = [run for page in pages for run in page.get('check_runs', [])
            if run.get('head_sha') == sha and run.get('app', {}).get('slug') == 'github-actions'
            and run.get('name') in {'validate', 'windows-installer'}]
    if ({run['name'] for run in runs} != {'validate', 'windows-installer'}
            or any(run.get('status') != 'completed' or run.get('conclusion') != 'success' for run in runs)):
        raise ValueError('exact-head Linux/Windows CI is incomplete or failed')
    return runs


def qualification(repo, sha, candidate, index, approval_url=None):
    """Prepare or qualify; preserve candidate bytes and require live external verification."""
    manifest = builder.verify(repo, sha, candidate)
    hashes = {p.name: builder.digest(p.read_bytes()) for p in sorted(candidate.iterdir())}
    evidence = gate_evidence(index, manifest['source_tree_sha'])
    evidence_hash = builder.digest(builder.encode(evidence))
    ci = live_ci(sha)
    attestations = {}
    for name in hashes:
        if not name.endswith('.zip'):
            continue
        verified = gh('attestation', 'verify', str((candidate / name).resolve()), '--repo', REPO,
                      '--signer-workflow', WORKFLOW, '--source-ref', 'refs/heads/main',
                      '--source-digest', sha, '--hostname', 'github.com', '--deny-self-hosted-runners', '--format', 'json')
        if (not isinstance(verified, list) or not verified
                or any(not isinstance(row, dict) or not isinstance(row.get('verificationResult'), dict)
                       for row in verified)):
            raise ValueError('no verified publisher attestation')
        attestations[name] = verified
    statement = (f'APPROVE GRIDLINE STABLE RELEASE\nsource_sha={sha}\n'
                 f'candidate_manifest_sha256={hashes["release-manifest.json"]}\n'
                 f'qualification_evidence_sha256={evidence_hash}')
    approval = None
    if approval_url is not None:
        match = COMMENT.fullmatch(approval_url)
        if not match:
            raise ValueError('approval must be a canonical Gridline PR comment URL')
        approval = gh('api', '--hostname', 'github.com', f'repos/{REPO}/issues/comments/{match[1]}')
        if (not isinstance(approval, dict) or approval.get('html_url') != approval_url
                or not isinstance(approval.get('user'), dict)
                or str(approval['user'].get('login', '')).casefold() != 'makeitezzz555'
                or not isinstance(approval.get('body'), str) or approval['body'].strip() != statement):
            raise ValueError('owner approval does not bind the source, artifacts and reviewed evidence')
    # Detect accidental changes while external checks were running.
    builder.verify(repo, sha, candidate)
    return {'schema_version': 1, 'product': 'gridline', 'version': manifest['version'],
            'qualification': 'QUALIFIED_LIMITED_RELEASE' if approval else 'AWAITING_OWNER_APPROVAL',
            'publish_allowed': approval is not None, 'source_sha': sha,
            'source_tree_sha': manifest['source_tree_sha'], 'candidate_sha256': hashes,
            'gate_evidence': evidence, 'gate_evidence_sha256': evidence_hash,
            'ci': ci, 'verified_attestations': attestations, 'owner_approval': approval,
            'required_owner_comment': statement,
            'limits': ['Candidate manifest remains its original build-time unqualified receipt.',
                       'Gate files are reviewed maintainer inputs, not automatic professional certification.',
                       'Recipients must independently verify the referenced live approval and attestations.']}


def main(argv=None):
    """No merge, tag, release upload or installation operation exists."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--evidence-index', type=Path, required=True)
    parser.add_argument('--approval-comment', help='omit to prepare an approval request; no qualification')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.out.resolve().is_relative_to(args.candidate.resolve()):
            raise ValueError('qualification output must remain outside immutable candidate')
        if args.out.exists() or args.out.is_symlink():
            raise ValueError('output must be new')
        receipt = qualification(args.repo, args.source_sha, args.candidate,
                                args.evidence_index, args.approval_comment)
        with args.out.open('xb') as stream:
            stream.write(builder.encode(receipt))
        print(json.dumps({'qualification': receipt['qualification'], 'publish_allowed': receipt['publish_allowed']}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
                          'publish_allowed': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
