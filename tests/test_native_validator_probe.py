"""An unavailable provider validation command must not produce false acceptance."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('bash') and os.name == 'posix', 'POSIX validation harness')
class NativeValidatorProbeTests(unittest.TestCase):
    def probe(self, advertised, prefixed=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Keep host CLIs out of PATH; the harness still needs standard shell tools.
            for name in ('dirname', 'grep'):
                (root / name).symlink_to(shutil.which(name))
            marker = root / 'invoked'
            cli = root / 'gemini'
            cli.write_text('#!/bin/sh\n'
                           'if [ "$1 $2" = "extensions --help" ]; then\n'
                           + ('  echo "  ' + ('gemini extensions ' if prefixed else '') + 'validate  Validate an extension"\n' if advertised else '  echo "  install  Install an extension"\n')
                           + '  exit 0\nfi\n'
                           + 'echo invoked > "$GRIDLINE_PROBE_MARKER"\nexit 17\n')
            cli.chmod(0o755)
            result = subprocess.run([shutil.which('bash'), str(ROOT / 'scripts/validate-native.sh')],
                                    env={**os.environ, 'PATH': str(root),
                                         'GRIDLINE_PROBE_MARKER': str(marker)},
                                    capture_output=True, text=True, timeout=30)
            return result, marker.exists()

    def test_missing_validator_is_explicitly_not_tested(self):
        result, invoked = self.probe(False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Gemini CLI: NOT_TESTED', result.stdout)
        self.assertFalse(invoked)

    def test_advertised_validator_failure_cannot_pass(self):
        for prefixed in (False, True):
            with self.subTest(prefixed=prefixed):
                result, invoked = self.probe(True, prefixed=prefixed)
                self.assertEqual(result.returncode, 17, result.stderr)
                self.assertTrue(invoked)
