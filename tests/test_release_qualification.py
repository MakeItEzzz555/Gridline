"""Qualification cannot turn incomplete, tampered or unapproved candidates into releases."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import test_release_artifacts as fixtures

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qualifier', ROOT / 'scripts/qualify-release.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReleaseArtifactTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo, self.sha, self.base = self.fixture.repo, self.fixture.a, self.fixture.base
        self.candidate = self.base / 'candidate'
        q.builder.build(self.repo, self.sha, self.candidate)
        self.manifest = json.loads((self.candidate / 'release-manifest.json').read_text())
        self.index = self.base / 'index.json'
        self.index.write_text(json.dumps({name: name + '.json' for name in q.GATES}))
        for name in q.GATES:
            (self.base / (name + '.json')).write_text(json.dumps({'gate': name, 'status': 'PASS',
                'source_tree_sha': self.manifest['source_tree_sha'], 'scope': 'mock fixture only'}))
        self.approval_url = 'https://github.com/MakeItEzzz555/Gridline/pull/41#issuecomment-123'
        self.statement = None
        self.ci_result = [{'check_runs': [{'id': i, 'head_sha': self.sha,
            'app': {'slug': 'github-actions'}, 'name': name, 'status': 'completed',
            'conclusion': 'success'} for i, name in enumerate(('validate', 'windows-installer'))]}]

    def external(self, *args):
        if args[0] == 'attestation':
            self.assertIn('--source-digest', args)
            self.assertEqual(args[args.index('--source-digest') + 1], self.sha)
            self.assertIn('--source-ref', args)
            self.assertIn('refs/heads/main', args)
            self.assertIn(q.WORKFLOW, args)
            self.assertIn('--deny-self-hosted-runners', args)
            self.assertEqual(args[args.index('--hostname') + 1], 'github.com')
            return [{'verificationResult': {'fixture': 'not a live cryptographic receipt'}}]
        if '/issues/comments/' in args[-1]:
            return {'html_url': self.approval_url, 'user': {'login': 'MakeItEzzz555'}, 'body': self.statement}
        return self.ci_result

    def run_qualification(self, approval=None):
        return q.qualification(self.repo, self.sha, self.candidate, self.index, approval)

    def test_prepare_and_exact_approval_preserve_all_candidate_bytes(self):
        before = {p.name: p.read_bytes() for p in self.candidate.iterdir()}
        with patch.object(q, 'gh', side_effect=self.external):
            prepared = self.run_qualification()
            self.assertFalse(prepared['publish_allowed'])
            self.statement = prepared['required_owner_comment']
            result = self.run_qualification(self.approval_url)
        self.assertTrue(result['publish_allowed'])
        self.assertEqual(result['qualification'], 'QUALIFIED_LIMITED_RELEASE')
        self.assertEqual(len(result['candidate_sha256']), 6)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.candidate.iterdir()})
        self.assertEqual(json.loads(before['release-manifest.json'])['qualification'], 'UNQUALIFIED_CANDIDATE')

    def test_unverified_wrong_tree_and_missing_gates_block_before_network(self):
        record = self.base / 'gemini.json'
        for value in ({'gate': 'gemini', 'status': 'NOT_TESTED', 'source_tree_sha': self.manifest['source_tree_sha'], 'scope': 'fixture'},
                      {'gate': 'gemini', 'status': 'PASS', 'source_tree_sha': '0' * 40, 'scope': 'fixture'}):
            record.write_text(json.dumps(value))
            with patch.object(q, 'gh') as live, self.assertRaises(ValueError):
                self.run_qualification()
            live.assert_not_called()
        self.index.write_text('{}')
        with patch.object(q, 'gh') as live, self.assertRaises(ValueError):
            self.run_qualification()
        live.assert_not_called()

    def test_gate_identity_and_distinct_evidence_cannot_be_collapsed(self):
        shared = self.base / 'shared.json'
        shared.write_text(json.dumps({'gate': 'architecture_review', 'status': 'PASS',
            'source_tree_sha': self.manifest['source_tree_sha'], 'scope': 'generic stamp'}))
        self.index.write_text(json.dumps({name: shared.name for name in q.GATES}))
        with patch.object(q, 'gh') as live, self.assertRaisesRegex(ValueError, 'distinct'):
            self.run_qualification()
        live.assert_not_called()
        self.index.write_text(json.dumps({name: name + '.json' for name in q.GATES}))
        record = self.base / 'gemini.json'
        value = json.loads(record.read_text()); value['gate'] = 'claude'
        record.write_text(json.dumps(value))
        with patch.object(q, 'gh') as live, self.assertRaises(ValueError):
            self.run_qualification()
        live.assert_not_called()

    def test_ci_and_attestation_failure_never_qualify(self):
        self.ci_result[0]['check_runs'][0]['conclusion'] = 'failure'
        with patch.object(q, 'gh', side_effect=self.external), self.assertRaises(ValueError):
            self.run_qualification()
        self.ci_result[0]['check_runs'][0]['conclusion'] = 'success'
        def failed_signature(*args):
            if args[0] == 'attestation':
                raise subprocess.CalledProcessError(1, ['gh', *args])
            return self.external(*args)
        with patch.object(q, 'gh', side_effect=failed_signature), self.assertRaises(subprocess.CalledProcessError):
            self.run_qualification()

    def test_wrong_owner_or_changed_evidence_invalidates_approval(self):
        with patch.object(q, 'gh', side_effect=self.external):
            self.statement = self.run_qualification()['required_owner_comment']
            record = self.base / 'gemini.json'
            value = json.loads(record.read_text()); value['scope'] = 'changed after approval'
            record.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'owner approval'):
                self.run_qualification(self.approval_url)
        def wrong_owner(*args):
            value = self.external(*args)
            if '/issues/comments/' in args[-1]:
                value['user']['login'] = 'other-user'
            return value
        with patch.object(q, 'gh', side_effect=wrong_owner), self.assertRaisesRegex(ValueError, 'owner approval'):
            self.run_qualification(self.approval_url)

    def test_tamper_duplicate_json_and_output_overwrite_block(self):
        self.index.write_text('{"gemini":"a","gemini":"b"}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            q.read(self.index)
        (self.candidate / 'SHA256SUMS').write_text('tampered')
        with patch.object(q, 'gh') as live, self.assertRaises(ValueError):
            self.run_qualification()
        live.assert_not_called()
        with contextlib.redirect_stderr(io.StringIO()):
            code = q.main(['--repo', str(self.repo), '--source-sha', self.sha,
                '--candidate', str(self.candidate), '--evidence-index', str(self.index),
                '--out', str(self.candidate / 'approval.json')])
        self.assertEqual(code, 2)
        self.assertFalse((self.candidate / 'approval.json').exists())
        existing = self.base / 'existing.json'
        existing.write_text('preserve this receipt')
        with patch.object(q, 'qualification') as qualify, contextlib.redirect_stderr(io.StringIO()):
            code = q.main(['--repo', str(self.repo), '--source-sha', self.sha,
                '--candidate', str(self.candidate), '--evidence-index', str(self.index), '--out', str(existing)])
        self.assertEqual(code, 2)
        qualify.assert_not_called()
        self.assertEqual(existing.read_text(), 'preserve this receipt')

    def test_malformed_live_response_is_rejected(self):
        for response in ({}, [1], [{'check_runs': [None]}]):
            with patch.object(q, 'gh', return_value=response), self.assertRaises(ValueError):
                self.run_qualification()
