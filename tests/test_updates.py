"""Adversarial stable-release discovery; all network calls are mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('updates', ROOT / 'scripts/check-updates.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def release(version='0.8.0', **changes):
    value = {'tag_name': f'v{version}', 'draft': False, 'prerelease': False,
             'html_url': f'https://github.com/MakeItEzzz555/Gridline/releases/tag/v{version}'}
    return {**value, **changes}


class UpdateTests(unittest.TestCase):
    def invoke(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = u.main(list(args))
        return code, json.loads(out.getvalue())

    def test_no_implicit_network_or_install(self):
        with patch.object(u, 'fetch_release', side_effect=AssertionError('network')):
            code, data = self.invoke('--installed-version', '0.7.0')
        self.assertEqual(code, 0)
        self.assertEqual(data['reason'], 'NETWORK_NOT_REQUESTED')
        self.assertFalse(data['install_authorized'])

    def test_stable_upgrade_equal_and_downgrade(self):
        for current, status in [('0.7.0', 'UPDATE_AVAILABLE'), ('0.8.0', 'CURRENT'),
                                ('0.9.0', 'LOCAL_AHEAD'), ('0.8.0-rc.1', 'UPDATE_AVAILABLE')]:
            with self.subTest(current=current):
                data = u.assess_release(current, release())
                self.assertEqual(data['status'], status)
                self.assertFalse(data['install_authorized'])
                self.assertEqual(data['artifact_verification'], 'NOT_CHECKED')
                self.assertIsNone(data['source_sha'])
        self.assertEqual(u.assess_release('0.8.0+local', release('0.8.0+remote'))['status'], 'CURRENT')

    def test_semver_precedence_and_invalid_tags(self):
        ordered = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',
                   '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0']
        self.assertEqual(sorted(ordered, key=u.version_key), ordered)
        for value in ['01.2.3', '1.2', 'v1.2.3', '1.2.3-01', '1.2.3-', '１.2.3',
                      '1.2.3\n', '1.2.3/../../x', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                u.version_key(value)

    def test_untrusted_draft_preview_or_malformed_release_rejected(self):
        for value in [[], None, {}, release(draft=True), release(prerelease=True),
                      release(draft=0), release('0.8.0-rc.1'),
                      release(html_url='https://evil.example/releases/tag/v0.8.0'),
                      release(html_url='https://github.com/Other/Gridline/releases/tag/v0.8.0'),
                      release(tag_name='v0.8.0/../../x'), release(tag_name=4)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                u.assess_release('0.7.0', value)

    def test_size_invalid_json_and_redirect(self):
        for raw in [b'not json', b' ' * (u.MAX_BYTES + 1), b'\xff']:
            with self.subTest(raw=raw[:10]), self.assertRaises(ValueError):
                u.read_json(io.BytesIO(raw))
        with patch.object(u.json, 'loads', side_effect=RecursionError), self.assertRaises(ValueError):
            u.read_json(io.BytesIO(b'{}'))
        with self.assertRaises(ValueError):
            u.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://localhost/')

    def test_explicit_network_offline_and_invalid_local_evidence(self):
        with patch.object(u, 'fetch_release', side_effect=URLError('private details')):
            code, data = self.invoke('--check-network', '--installed-version', '0.7.0')
        self.assertEqual(code, 2)
        self.assertEqual(data['reason'], 'OFFLINE_OR_API_UNAVAILABLE')
        self.assertNotIn('private', json.dumps(data))
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / 'release.json'
            fixture.write_text(json.dumps(release()))
            code, data = self.invoke('--release-json', str(fixture), '--installed-version', '0.7.0')
            self.assertEqual((code, data['status'], data['evidence']), (0, 'UPDATE_AVAILABLE', 'LOCAL_FIXTURE'))
            fixture.write_text('{')
            code, data = self.invoke('--release-json', str(fixture))
            self.assertEqual(code, 2)
            self.assertEqual(data['status'], 'UNKNOWN')

    def test_distribution_contract(self):
        data = json.loads((ROOT / 'distribution.json').read_text())
        self.assertEqual(data['version'], json.loads((ROOT / 'plugin.json').read_text())['version'])
        self.assertEqual(data['release_feed'], u.API)
        self.assertEqual(data['release_qualification'], 'NOT_VERIFIED')
        self.assertEqual(data['network_default'], 'off')
        self.assertFalse(data['install_automation'])
        self.assertEqual(len(data['providers']), 4)
        for provider in data['providers'].values():
            self.assertEqual(json.loads((ROOT / provider['manifest']).read_text())['version'], data['version'])
