#!/usr/bin/env python3
"""Offline source triage only. Never activate rules or certify a project."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

SKILL = Path(__file__).resolve().parents[1]
MAX_BYTES = 1024 * 1024
STAGES = {'briefing', 'concept', 'spatial-coordination', 'technical-design',
          'construction', 'handover', 'operation'}
KINDS = {'METHODOLOGY', 'EXCHANGE_STANDARD', 'DOCUMENTATION_STANDARD',
         'TECHNICAL_STANDARD', 'REGULATORY_SOURCE'}


def iso_date(value):
    """Parse an exact Gregorian YYYY-MM-DD date; do not accept compact ISO forms."""
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('date must be YYYY-MM-DD')
    return date.fromisoformat(value)


def unique_object(pairs):
    """Reject duplicate JSON keys instead of silently replacing earlier evidence."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate JSON key')
        obj[key] = value
    return obj


def read_json(path):
    """Read at most 1 MiB as UTF-8 JSON; return data and original-byte SHA256."""
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('input exceeds 1 MiB')
    def reject_constant(value):
        raise ValueError('nonfinite JSON')
    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except RecursionError as exc:
        raise ValueError('JSON is too deeply nested') from exc
    return data, hashlib.sha256(raw).hexdigest()


def validate_registry(registry):
    """Validate the bundled citation registry; metadata verification is not adoption."""
    if not isinstance(registry, dict) or type(registry.get('schema_version')) is not int or registry['schema_version'] != 1:
        raise ValueError('unsupported registry schema')
    sources = registry.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('registry requires sources')
    seen = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError('source must be an object')
        for key in ('id', 'title', 'issuer', 'domain', 'source_url', 'evidence_pointer',
                    'access_level', 'license_scope', 'obligation_source', 'risk', 'next_evidence'):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise ValueError(f'missing source {key}')
        if source['id'] in seen or not source['source_url'].startswith('https://'):
            raise ValueError('duplicate source or non-HTTPS citation')
        seen.add(source['id'])
        if source.get('kind') not in KINDS or source.get('publication_status') not in {'PUBLISHED', 'DRAFT', 'UNVERIFIED'}:
            raise ValueError('invalid source classification')
        for key in ('edition', 'adopted_edition', 'effective_from', 'withdrawn_on', 'reviewer'):
            if key not in source or (source[key] is not None and (not isinstance(source[key], str) or not source[key].strip())):
                raise ValueError(f'invalid source {key}')
        checked, due = iso_date(source['checked_on']), iso_date(source['review_due'])
        if due < checked:
            raise ValueError('source review window is reversed')
        for key in ('effective_from', 'withdrawn_on'):
            if source[key] is not None:
                iso_date(source[key])
        start, end = source['effective_from'], source['withdrawn_on']
        if start and end and iso_date(end) <= iso_date(start):
            raise ValueError('source validity window is reversed')
        scope = source.get('scope')
        if not isinstance(scope, dict) or set(scope) != {'countries', 'municipalities', 'project_types', 'stages'}:
            raise ValueError('source scope must be explicit')
        for values in scope.values():
            if values is not None and (not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values)):
                raise ValueError('invalid source scope values')
        if not isinstance(source.get('verified_clauses'), list) or not isinstance(source.get('exceptions'), list):
            raise ValueError('source clauses and exceptions must be explicit lists')


def select_sources(project, registry):
    """Classify explicitly requested editions without applying any technical rule.

    Missing context stays UNKNOWN. Territorial mismatches are NOT_APPLICABLE;
    stale/draft/unverified sources are UNVERIFIED. Reference-only classifications
    authorize neither construction nor compliance use, even with supplied approvals.
    The input dictionaries are never mutated.
    """
    validate_registry(registry)
    if not isinstance(project, dict):
        raise ValueError('project context must be an object')
    requests = project.get('requested_sources')
    if not isinstance(requests, list) or not 1 <= len(requests) <= 100:
        raise ValueError('request 1 to 100 source editions explicitly')
    for key in ('country', 'municipality', 'project_type', 'stage', 'as_of'):
        value = project.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f'{key} must be a string or null')
    country = project.get('country')
    if country and not re.fullmatch(r'[A-Z]{2}', country):
        raise ValueError('country must be an uppercase two-letter country code')
    if project.get('stage') and project['stage'] not in STAGES:
        raise ValueError('unsupported project stage')
    as_of = iso_date(project['as_of']) if project.get('as_of') else None
    missing = [k for k in ('country', 'municipality', 'project_type', 'stage', 'as_of')
               if not project.get(k) or not project[k].strip() or project[k].strip().upper() in {'UNKNOWN', 'UNDETERMINED'}]
    by_id = {s['id']: s for s in registry['sources']}
    results = []
    ids = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) - {'id', 'edition'}:
            raise ValueError('request requires id and optional edition only')
        sid, edition = request.get('id'), request.get('edition')
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError('source IDs must be nonempty and unique')
        if edition is not None and (not isinstance(edition, str) or not edition.strip()):
            raise ValueError('requested edition must be a string or null')
        ids.add(sid)
        source = by_id.get(sid)
        status, reason = 'UNKNOWN', 'SOURCE_NOT_REGISTERED'
        if source:
            mismatch = next((key for key, field in [('countries', 'country'), ('municipalities', 'municipality'),
                                                    ('project_types', 'project_type'), ('stages', 'stage')]
                             if source['scope'][key] is not None and field not in missing
                             and project[field] not in source['scope'][key]), None)
            if mismatch:
                status, reason = 'NOT_APPLICABLE', f'SCOPE_MISMATCH:{mismatch}'
            elif missing:
                reason = 'MISSING_CONTEXT:' + ','.join(missing)
            elif as_of < iso_date(source['checked_on']):
                reason = 'PREDATES_SOURCE_CHECK'
            elif source['withdrawn_on'] and as_of >= iso_date(source['withdrawn_on']):
                status, reason = 'UNVERIFIED', 'WITHDRAWN'
            elif source['effective_from'] and as_of < iso_date(source['effective_from']):
                status, reason = 'NOT_APPLICABLE', 'NOT_YET_EFFECTIVE'
            elif as_of > iso_date(source['review_due']):
                status, reason = 'UNVERIFIED', 'SOURCE_REVIEW_OVERDUE'
            elif source['publication_status'] != 'PUBLISHED':
                status, reason = 'UNVERIFIED', 'DRAFT_OR_UNVERIFIED_PUBLICATION'
            elif source['edition'] is None:
                status, reason = 'UNVERIFIED', 'SOURCE_EDITION_UNRESOLVED'
            elif edition is None:
                reason = 'REQUESTED_EDITION_REQUIRED'
            elif edition != source['edition']:
                status, reason = 'UNVERIFIED', 'EDITION_MISMATCH'
            elif source['kind'] in {'TECHNICAL_STANDARD', 'REGULATORY_SOURCE'}:
                status, reason = 'UNVERIFIED', 'ADOPTION_CLAUSES_AND_PROFESSIONAL_REVIEW_REQUIRED'
            else:
                status, reason = 'REFERENCE_ONLY', 'EXPLICIT_REFERENCE_EDITION;NO_RULE_ACTIVATION'
        results.append({'id': sid, 'requested_edition': edition, 'status': status, 'reason': reason,
                        'registered_edition': source['edition'] if source else None,
                        'source_url': source['source_url'] if source else None,
                        'next_evidence': source['next_evidence'] if source else 'Identify an authoritative source and edition.',
                        'rule_activation_allowed': False})
    return {'schema_version': 1, 'mode': 'RESEARCH_ONLY', 'rule_activation_allowed': False, 'results': results}


def main(argv=None):
    """Print a triage receipt; exit 2 for unresolved/invalid inputs, 0 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path, help='JSON source-selection context; does not edit a model')
    args = parser.parse_args(argv)
    try:
        project, project_hash = read_json(args.project)
        registry, registry_hash = read_json(SKILL / 'references/source-registry.json')
        result = select_sources(project, registry)
        result.update(project_sha256=project_hash, registry_sha256=registry_hash)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 2 if any(r['status'] in {'UNKNOWN', 'UNVERIFIED'} for r in result['results']) else 0
    except (ValueError, OSError, KeyError, TypeError):
        print(json.dumps({'mode': 'RESEARCH_ONLY', 'status': 'UNKNOWN',
                          'reason': 'INVALID_CONTEXT_OR_REGISTRY', 'rule_activation_allowed': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
