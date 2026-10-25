"""Execute the actual manual-workflow source guard against hostile selections."""
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('bash'), 'workflow guard requires bash')
class AttestationGuardTests(unittest.TestCase):
    def guard(self, **changes):
        workflow = (ROOT / '.github/workflows/attest-candidate.yml').read_text()
        script = textwrap.dedent(workflow.split('        run: |\n', 1)[1].split('      - uses:', 1)[0])
        env = {**os.environ, 'GITHUB_REPOSITORY': 'MakeItEzzz555/Gridline',
               'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': 'a' * 40,
               'EXPECTED_SOURCE_SHA': 'a' * 40, **changes}
        return subprocess.run([shutil.which('bash'), '-c', script], env=env,
                              capture_output=True, text=True, timeout=10).returncode

    def test_exact_main_source_is_accepted(self):
        self.assertEqual(self.guard(), 0)

    def test_fork_branch_moving_source_and_injected_input_are_rejected(self):
        for changes in ({'GITHUB_REPOSITORY': 'other/Gridline'},
                        {'GITHUB_REF': 'refs/heads/feature'},
                        {'EXPECTED_SOURCE_SHA': 'b' * 40},
                        {'EXPECTED_SOURCE_SHA': 'main'},
                        {'EXPECTED_SOURCE_SHA': '$(exit 0)'}):
            with self.subTest(changes=changes):
                self.assertNotEqual(self.guard(**changes), 0)
