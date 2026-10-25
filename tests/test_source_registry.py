"""Source triage false-pass regressions; these tests establish no code compliance."""
import copy
import hashlib
import os
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/site-regulation-research'
spec = importlib.util.spec_from_file_location('source_selection', SKILL / 'scripts/select_sources.py')
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class SourceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((SKILL / 'references/source-registry.json').read_text(encoding='utf-8'))
        self.project = dict(country='CY', municipality='Nicosia', project_type='residential',
                            stage='technical-design', as_of='2026-10-25',
                            requested_sources=[dict(id='ifc4x3-add2', edition='4.3.2.0')])

    def select(self, source_id=None, edition=None, **context):
        project = {**self.project, **context}
        if source_id is not None:
            project['requested_sources'] = [dict(id=source_id, edition=edition)]
        report = selector.select_sources(project, self.registry)
        self.assertFalse(report['rule_activation_allowed'])
        self.assertEqual(report['mode'], 'RESEARCH_ONLY')
        self.assertTrue(all(not r['rule_activation_allowed'] for r in report['results']))
        return report['results'][0]

    def test_pinned_exchange_reference_is_not_compliance(self):
        before_project, before_registry = copy.deepcopy(self.project), copy.deepcopy(self.registry)
        self.assertEqual(self.select()['status'], 'REFERENCE_ONLY')
        self.assertEqual(self.select('riba-plan-of-work', '2020')['status'], 'REFERENCE_ONLY')
        self.assertEqual(self.select('ids', '1.0.0')['status'], 'REFERENCE_ONLY')
        self.assertEqual(self.project, before_project)
        self.assertEqual(self.registry, before_registry)

    def test_missing_context_and_missing_edition_are_unknown(self):
        for field in ('country', 'municipality', 'project_type', 'stage', 'as_of'):
            for missing in (None, ''):
                with self.subTest(field=field, missing=missing):
                    self.assertEqual(self.select(**{field: missing})['status'], 'UNKNOWN')
        for field in ('municipality', 'project_type'):
            self.assertEqual(self.select(**{field: '   '})['status'], 'UNKNOWN')
        self.assertEqual(self.select('ids')['reason'], 'REQUESTED_EDITION_REQUIRED')

    def test_country_and_local_scope_never_default_to_us(self):
        result = self.select('cy-building-permit', country='US')
        self.assertEqual((result['status'], result['reason']), ('NOT_APPLICABLE', 'SCOPE_MISMATCH:countries'))
        self.assertEqual(self.select('ibc')['status'], 'UNKNOWN')
        source = self.registry['sources'][0]
        source['scope']['municipalities'] = ['Nicosia']
        source['scope']['project_types'] = ['residential']
        source['scope']['stages'] = ['technical-design']
        for context, reason in [({'municipality': 'Limassol'}, 'municipalities'),
                                ({'project_type': 'hotel'}, 'project_types'),
                                ({'stage': 'concept'}, 'stages')]:
            self.assertEqual(self.select(source['id'], source['edition'], **context)['reason'], 'SCOPE_MISMATCH:' + reason)
        self.assertEqual(self.select(source['id'], source['edition'], municipality='UNKNOWN')['status'], 'UNKNOWN')

    def test_stale_wrong_or_unpublished_editions_cannot_be_references(self):
        for source_id, edition in [('ifc4x3-add2', '4.4.0.0'), ('iso13567-1', '1998'),
                                   ('cy-ec2-na-enquiry', 'public-enquiry:2024-11-28')]:
            self.assertEqual(self.select(source_id, edition)['status'], 'UNVERIFIED')
        self.assertEqual(self.select(as_of='2027-01-24')['reason'], 'SOURCE_REVIEW_OVERDUE')
        self.assertEqual(self.select(as_of='2026-10-24')['reason'], 'PREDATES_SOURCE_CHECK')
        self.assertEqual(self.select(as_of='2027-01-23')['status'], 'REFERENCE_ONLY')

    def test_unknown_adoption_or_user_approval_cannot_activate_rules(self):
        for source_id, edition in [('cy-eurocodes', None), ('cy-building-permit', None),
                                   ('cy-planning-permit', None), ('cy-building-controls', None),
                                   ('iso21542', '2021'), ('iso19650-1', '2018')]:
            self.assertEqual(self.select(source_id, edition)['status'], 'UNVERIFIED')
        # Even seemingly complete approval metadata is not an authenticated approval gateway.
        record = next(s for s in self.registry['sources'] if s['id'] == 'iso21542')
        record.update(adopted_edition='2021', reviewer='claimed professional', verified_clauses=['claimed clause'])
        self.assertEqual(self.select('iso21542', '2021', approved=True)['status'], 'UNVERIFIED')

    def test_effective_withdrawal_and_invalid_windows(self):
        source = next(s for s in self.registry['sources'] if s['id'] == 'ifc4x3-add2')
        source.update(effective_from='2026-10-26', withdrawn_on='2026-11-01')
        self.assertEqual(self.select()['reason'], 'NOT_YET_EFFECTIVE')
        self.assertEqual(self.select(as_of='2026-10-26')['status'], 'REFERENCE_ONLY')
        self.assertEqual(self.select(as_of='2026-11-01')['reason'], 'WITHDRAWN')
        source['withdrawn_on'] = source['effective_from']
        with self.assertRaises(ValueError):
            self.select()

    def test_invalid_context_fails_instead_of_coercing(self):
        contexts = [dict(country=8), dict(country='Cyprus'), dict(stage='made-up'),
                    dict(as_of='20261025'), dict(as_of='2026-02-30'),
                    dict(requested_sources=[]), dict(requested_sources='ids'),
                    dict(requested_sources=[dict(id='ids', edition=1)]),
                    dict(requested_sources=[dict(id='ids'), dict(id='ids')]),
                    dict(requested_sources=[dict(id='ids', approve=True)])]
        for context in contexts:
            with self.subTest(context=context), self.assertRaises(ValueError):
                self.select(**context)

    def test_malformed_registry_rejected(self):
        for mutation in ('schema', 'duplicate', 'scope', 'date', 'kind'):
            registry = copy.deepcopy(self.registry)
            if mutation == 'schema':
                registry['schema_version'] = True
            elif mutation == 'duplicate':
                registry['sources'].append(copy.deepcopy(registry['sources'][0]))
            elif mutation == 'scope':
                registry['sources'][0]['scope']['countries'] = 'CY'
            elif mutation == 'date':
                registry['sources'][0]['review_due'] = '2026-01-01'
            else:
                registry['sources'][0]['kind'] = 'APPROVED_LEGAL_RULE'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                selector.select_sources(self.project, registry)

    def test_reader_limits_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'context.json'
            for raw in [b'{', b'{"country":"CY","country":"US"}', b'{"x":NaN}',
                        b'\xff', b' ' * (selector.MAX_BYTES + 1)]:
                path.write_bytes(raw)
                with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                    selector.read_json(path)

    def test_isolated_skill_receipt_and_unresolved_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / 'installed/site-regulation-research'
            shutil.copytree(SKILL, installed)
            context = Path(tmp) / 'context.json'
            raw = json.dumps(self.project).encode()
            context.write_bytes(raw)
            command = [sys.executable, '-I', str(installed / 'scripts/select_sources.py')]
            ran = subprocess.run([*command, str(context)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            receipt = json.loads(ran.stdout)
            self.assertEqual(receipt['project_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt['registry_sha256'], hashlib.sha256((installed / 'references/source-registry.json').read_bytes()).hexdigest())
            self.assertEqual(context.read_bytes(), raw)
            ran = subprocess.run([*command, str(installed / 'references/example-source-context.json')], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 2, ran.stderr)
            self.assertFalse(json.loads(ran.stdout)['rule_activation_allowed'])
            context.write_text('{')
            ran = subprocess.run([*command, str(context)], capture_output=True, text=True)
            self.assertEqual((ran.returncode, json.loads(ran.stdout)['status']), (2, 'UNKNOWN'))

    def test_ascii_stdout_keeps_unicode_evidence_and_real_status(self):
        """An ASCII terminal must not misreport a valid source as invalid input."""
        with tempfile.TemporaryDirectory() as tmp:
            context = Path(tmp) / 'context.json'
            project = {**self.project, 'requested_sources': [
                {'id': 'cy-eurocodes', 'edition': None}]}
            context.write_text(json.dumps(project), encoding='utf-8')
            env = {**os.environ, 'PYTHONIOENCODING': 'ascii:strict',
                   'PYTHONUTF8': '0', 'LC_ALL': 'C'}
            result = subprocess.run(
                [sys.executable, '-X', 'utf8=0',
                 str(SKILL / 'scripts/select_sources.py'), str(context)],
                capture_output=True, text=True, encoding='ascii', env=env)
            self.assertEqual(result.returncode, 2, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['mode'], 'RESEARCH_ONLY')
            self.assertEqual(receipt['results'][0]['id'], 'cy-eurocodes')
            self.assertEqual(receipt['results'][0]['status'], 'UNVERIFIED')
            self.assertIn('–', receipt['results'][0]['next_evidence'])
            self.assertFalse(receipt['rule_activation_allowed'])

    def test_source_records_preserve_gaps_and_citations(self):
        selector.validate_registry(self.registry)
        self.assertEqual(len(self.registry['sources']), 12)
        for source in self.registry['sources']:
            self.assertEqual(source['national_adoption_status'], 'UNVERIFIED')
            self.assertEqual(source['verified_clauses'], [])
            self.assertIsNone(source['reviewer'])
            self.assertIsNone(source['adopted_edition'])
            self.assertIsNone(source['effective_from'])
            self.assertIsNone(source['withdrawn_on'])
