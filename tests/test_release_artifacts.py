"""Pinned source, hostile ZIP and disposable installer upgrade/rollback tests."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_builder', ROOT / 'scripts/build-release.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@unittest.skipUnless(shutil.which('git'), 'release snapshots require Git')
class ReleaseArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Gridline fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', str(self.base / 'no-hooks'))
        self.version('1.0.0', 'A')
        for name in ('README.md', 'LICENSE', 'CHANGELOG.md', 'GEMINI.md'):
            self.write(name, 'fixture\n')
        self.write('.agents/plugins/marketplace.json', '{}')
        self.write('agents/example.md', 'fixture\n')
        self.write('providers/claude/agents/example.md', 'fixture\n')
        self.write('providers/claude/README.md', 'fixture\n')
        for name in ('install-global.sh', 'install-global.ps1'):
            self.write('scripts/' + name, (ROOT / 'scripts' / name).read_bytes())
        self.a = self.commit()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True).stdout.decode().strip()

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())

    def version(self, version, body):
        for name in builder.MANIFESTS:
            self.write(name, json.dumps({'name': 'gridline', 'version': version}))
        self.write('.claude-plugin/marketplace.json', json.dumps({'name': 'gridline', 'plugins': [
            {'name': 'gridline', 'version': version, 'source': './providers/claude'}]}))
        skill = f'---\nname: example\ndescription: fixture\n---\n{body}\n'
        self.write('skills/example/SKILL.md', skill)
        self.write('providers/claude/skills/example/SKILL.md', skill)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture snapshot')
        return self.git('rev-parse', 'HEAD')

    def test_reproducible_pinned_snapshot_excludes_dirty_and_untracked_files(self):
        first = builder.build(self.repo, self.a, self.base / 'one')
        self.write('skills/example/SKILL.md', 'uncommitted mutation')
        self.write('.env', 'untracked fake secret')
        second = builder.build(self.repo, self.a, self.base / 'two')
        self.assertEqual(first, second)
        receipt = builder.verify(self.repo, self.a, self.base / 'two')
        self.assertEqual(receipt['source_sha'], self.a)
        self.assertFalse(receipt['publish_allowed'])
        self.assertEqual(receipt['qualification'], 'UNQUALIFIED_CANDIDATE')
        for name, raw in first.items():
            if name.endswith('.zip'):
                self.assertNotIn('.env', builder.read_zip(raw))
        with self.assertRaises(FileExistsError):
            builder.build(self.repo, self.a, self.base / 'one')

    def test_checkout_line_endings_do_not_change_archive_bytes(self):
        baseline = builder.candidate(self.repo, self.a)
        self.git('config', 'core.autocrlf', 'true')
        self.git('config', 'core.eol', 'crlf')
        self.assertEqual(builder.candidate(self.repo, self.a), baseline)

    def test_manifest_and_mirror_drift_block_before_output_creation(self):
        self.write('gemini-extension.json', '{"name":"gridline","version":"1.1.0"}')
        sha = self.commit()
        with self.assertRaises(ValueError):
            builder.build(self.repo, sha, self.base / 'bad')
        self.assertFalse((self.base / 'bad').exists())
        self.version('1.0.0', 'A')
        self.write('providers/claude/skills/example/SKILL.md', 'drift')
        with self.assertRaises(ValueError):
            builder.candidate(self.repo, self.commit())

    def test_tampering_even_with_recomputed_checksums_is_rejected(self):
        out = self.base / 'candidate'
        original = builder.build(self.repo, self.a, out)
        for name in original:
            with self.subTest(name=name):
                (out / name).write_bytes(original[name] + b'tampered')
                with self.assertRaises(ValueError):
                    builder.verify(self.repo, self.a, out)
                (out / name).write_bytes(original[name])
        manifest = json.loads(original['release-manifest.json'])
        manifest['publish_allowed'] = True
        (out / 'release-manifest.json').write_bytes(builder.encode(manifest))
        files = {name: (out / name).read_bytes() for name in original if name != 'SHA256SUMS'}
        (out / 'SHA256SUMS').write_text(''.join(f'{builder.digest(raw)}  {name}\n' for name, raw in sorted(files.items())))
        with self.assertRaises(ValueError):
            builder.verify(self.repo, self.a, out)
        with self.assertRaises((ValueError, subprocess.SubprocessError)):
            builder.verify(self.repo, '0' * 40, out)

    def test_zip_traversal_alias_links_and_duplicates_are_rejected(self):
        cases = [('../escape',), ('/absolute',), ('C:/escape',), ('a\\escape',),
                 ('./hidden',), ('a//b',), ('A', 'a'), ('same', 'same'),
                 ('a', 'a/b'), ('CON.txt',), ('foo.',), ('e\u0301', '\u00e9')]
        for names in cases:
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w') as archive:
                for name in names:
                    info = zipfile.ZipInfo(name.replace('\\', '/'))
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, b'x')
            raw = output.getvalue()
            if len(names) == 1 and '\\' in names[0]:
                raw = raw.replace(names[0].replace('\\', '/').encode(), names[0].encode())
            with self.subTest(names=names), self.assertRaises(ValueError):
                builder.read_zip(raw)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b'../../escape')
        with self.assertRaises(ValueError):
            builder.read_zip(output.getvalue())
        with self.assertRaises(ValueError):
            builder.read_zip(b'x' * (builder.MAX_BYTES + 1))

    def test_git_export_ignore_and_substitution_are_not_silent(self):
        self.write('.gitattributes', 'README.md export-ignore\n')
        with self.assertRaises(ValueError):
            builder.candidate(self.repo, self.commit())
        self.write('.gitattributes', 'README.md export-subst\n')
        self.write('README.md', '$Format:%H$\n')
        with self.assertRaises(ValueError):
            builder.candidate(self.repo, self.commit())

    def test_submodules_and_git_links_are_rejected(self):
        self.git('update-index', '--add', '--cacheinfo', f'160000,{self.a},vendor')
        self.git('commit', '-qm', 'submodule fixture')
        with self.assertRaises(ValueError):
            builder.candidate(self.repo, self.git('rev-parse', 'HEAD'))
        # Create a Git symlink entry without requiring OS symlink privileges on Windows.
        self.git('rm', '--cached', '-q', 'vendor')
        blob = subprocess.run(['git', '-C', str(self.repo), 'hash-object', '-w', '--stdin'],
                              input=b'../../escape', check=True, capture_output=True).stdout.decode().strip()
        self.git('update-index', '--add', '--cacheinfo', f'120000,{blob},link')
        self.git('commit', '-qm', 'link fixture')
        with self.assertRaises(ValueError):
            builder.candidate(self.repo, self.git('rev-parse', 'HEAD'))

    @unittest.skipUnless(shutil.which('bash') and os.name != 'nt', 'Bash filesystem upgrade smoke requires POSIX; Windows installer is separate CI')
    def test_archive_a_to_b_tamper_block_and_backup_rollback(self):
        a_dir = self.base / 'a'
        a_outputs = builder.build(self.repo, self.a, a_dir)
        self.version('1.1.0', 'B')
        b = self.commit()
        b_dir = self.base / 'b'
        b_outputs = builder.build(self.repo, b, b_dir)
        home = self.base / 'home'
        home.mkdir()
        installed = home / '.codex/skills/example/SKILL.md'
        foreign = home / '.codex/skills/foreign/SKILL.md'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('foreign survives')
        env = {**os.environ, 'HOME': str(home), 'CODEX_HOME': str(home / '.codex')}

        def install(outputs, sha, directory, tag):
            builder.verify(self.repo, sha, directory)
            # Materialize only the already-verified in-memory source payload; never reopen an untrusted ZIP.
            name = next(name for name in outputs if name.endswith('-source.zip'))
            tree = self.base / ('extracted-' + tag)
            tree.mkdir()
            for path, (data, mode) in builder.read_zip(outputs[name]).items():
                target = tree / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(mode)
            ran = subprocess.run(['bash', str(tree / 'scripts/install-global.sh'), 'codex'],
                                 env=env, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

        install(a_outputs, self.a, a_dir, 'a')
        a_bytes = installed.read_bytes() + b'local customization\n'
        installed.write_bytes(a_bytes)
        corrupt = next(name for name in b_outputs if name.endswith('-source.zip'))
        (b_dir / corrupt).write_bytes(b'tampered archive')
        with self.assertRaises(ValueError):
            install(b_outputs, b, b_dir, 'corrupt')
        self.assertEqual(installed.read_bytes(), a_bytes)
        (b_dir / corrupt).write_bytes(b_outputs[corrupt])
        install(b_outputs, b, b_dir, 'b')
        self.assertIn(b'\nB\n', installed.read_bytes())
        backup = list((home / '.codex/backups').glob('*/skills/example/SKILL.md'))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_bytes(), a_bytes)
        installed.write_bytes(backup[0].read_bytes())
        self.assertEqual(installed.read_bytes(), a_bytes)
        self.assertEqual(foreign.read_text(), 'foreign survives')

    def test_real_repo_archives_keep_runnable_skill_and_entry_points(self):
        sha = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
        outputs = builder.build(ROOT, sha, self.base / 'real')
        for name, raw in outputs.items():
            if not name.endswith('.zip'):
                continue
            files = builder.read_zip(raw)
            target = self.base / name.removesuffix('.zip')
            target.mkdir()
            for path, (data, mode) in files.items():
                dest = target / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                dest.chmod(mode)
            self.assertTrue((target / 'LICENSE').is_file())
            if name.endswith('-source.zip'):
                for path in ('.codex-plugin/plugin.json', 'gemini-extension.json', 'scripts/install-global.ps1'):
                    self.assertTrue((target / path).is_file())
            else:
                self.assertTrue((target / '.claude-plugin/plugin.json').is_file())
            skill = target / 'skills/architectural-drawing-generation'
            ran = subprocess.run([sys.executable, '-I', str(skill / 'scripts/aec_draw.py'),
                                  str(skill / 'references/concept-plan.drawing.json'), '--validate-only'],
                                 capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)
