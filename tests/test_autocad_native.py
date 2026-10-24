import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'skills/autocad-dwg-workflow/scripts/autocad_native.py'
spec = importlib.util.spec_from_file_location('autocad_native', MODULE)
cad = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cad)


class AutoCADNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'sample.dxf').write_bytes(b'disposable test data')

    def session(self):
        result = cad.prepare(self.root, 'sample.dxf', self.root)
        return Path(result['session'])

    def console(self, run):
        manifest = json.loads((run / 'session.json').read_text())
        return {'schema': 'gridline-autocad-read.v1', 'probe_id': manifest['probe_id'],
                'document': manifest['copy'], 'acadver': '26.0s', 'platform': 'macOS Version 15.7 (Arm64)',
                'insunits': 4, 'dbmod_before': 1, 'dbmod_after': 1,
                'model_entity_count': 3, 'entity_types': [['LINE', 3]],
                'layers': [], 'layouts': ['A-101'], 'viewports': [],
                'extmin': ['0', '0', '0'], 'extmax': ['1000', '1000', '0']}

    def capture(self, run, data):
        (run / 'console.txt').write_text('GRIDLINE_READ_BEGIN\n' + json.dumps(data) + '\nGRIDLINE_READ_END')
        return cad.receipt(run, 'console.txt')

    def test_prepare_is_new_private_copy_and_never_autoruns(self):
        a, b = self.session(), self.session()
        self.assertNotEqual(a, b)
        self.assertEqual(a.stat().st_mode & 0o777, 0o700)
        self.assertEqual((a / 'drawing.dxf').read_bytes(), (self.root / 'sample.dxf').read_bytes())
        text = (a / 'inspect.lsp').read_text()
        self.assertNotIn('@DRAWING@', text)
        self.assertIn('(gl-q ' + cad.literal(json.loads((a / 'session.json').read_text())['probe_id']) + ')', text)
        self.assertIn('(assoc 41 d)', text)
        self.assertNotIn('(assoc 40 d)', text)
        self.assertNotIn('(command ', text)
        self.assertNotIn('(open ', text)
        self.assertEqual(text.count('(c:GRIDLINEINSPECT)'), 0)

    def test_generated_lisp_is_balanced_without_drawing_write_calls(self):
        import re
        text = (self.session() / 'inspect.lsp').read_text()
        tokens = re.findall(r'"(?:\\.|[^"\\])*"|;[^\n]*|[()]', text)
        depth = 0
        for token in tokens:
            if token == '(':
                depth += 1
            elif token == ')':
                depth -= 1
                self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)
        tokens = iter(re.findall(r'"(?:\\.|[^"\\])*"|;[^\n]*|[()]|[^\s()]+', text))
        def expression(token):
            if token != '(':
                return token
            items = []
            for token in tokens:
                if token == ')':
                    if items and items[0] == 'if':
                        self.assertIn(len(items), (3, 4), 'AutoLISP if must have condition and branches')
                    return items
                if not token.startswith(';'):
                    items.append(expression(token))
            self.fail('unclosed expression')
        for token in tokens:
            if not token.startswith(';'):
                expression(token)
        for symbol in ('command', 'command-s', 'entmod', 'entdel', 'entmake', 'setvar', 'eval', 'startapp'):
            self.assertNotRegex(text, r'\(' + symbol + r'\s')

    def test_traversal_and_symlinks_are_rejected(self):
        (self.root / 'link.dxf').symlink_to(self.root / 'sample.dxf')
        for name in ('../sample.dxf', str(self.root / 'sample.dxf'), 'link.dxf'):
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                cad.prepare(self.root, name, self.root)
        (self.root / 'sub').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            cad.read_file(self.root, 'sub/sample.dxf')

    def test_size_and_special_file_limits(self):
        with self.assertRaises(ValueError):
            cad.read_file(self.root, 'sample.dxf', 2)
        (self.root / 'empty.dxf').touch()
        with self.assertRaises(ValueError):
            cad.prepare(self.root, 'empty.dxf', self.root)
        import os
        os.mkfifo(self.root / 'fifo')
        with self.assertRaises(ValueError):
            cad.read_file(self.root, 'fifo')

    def test_lisp_literal_does_not_execute_input(self):
        self.assertEqual(cad.literal('a"b\\c'), '"a\\"b\\\\c"')
        for value in ('x\n(command)', 'x\x00', 'x' * 2049):
            with self.assertRaises(ValueError):
                cad.literal(value)

    def test_receipt_never_upgrades_read_to_audit_or_mcp(self):
        run = self.session()
        result = self.capture(run, self.console(run))
        self.assertEqual(result['state'], 'READ_PROBED')
        self.assertEqual(result['audit'], 'NOT_TESTED')
        self.assertEqual(result['dwg_dxf_roundtrip'], 'NOT_TESTED')
        self.assertEqual(result['source_sha256_before'], result['source_sha256_after'])
        self.assertEqual(result['evidence_origin'], 'OPERATOR_CAPTURE_UNAUTHENTICATED')

    def test_wrong_document_stale_probe_mutation_and_bad_counts_block(self):
        run = self.session()
        for key, value in [('document', '/other.dxf'), ('probe_id', 'stale'),
                           ('dbmod_after', 9), ('model_entity_count', 4),
                           ('insunits', True), ('acadver', '25.0'), ('extmin', ['NaN', '0', '0'])]:
            data = self.console(run)
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.capture(run, data)

    def test_missing_host_and_malformed_console_cannot_pass(self):
        run = self.session()
        for content in ('host closed', 'GRIDLINE_READ_BEGIN\n{bad}\nGRIDLINE_READ_END'):
            (run / 'console.txt').write_text(content)
            with self.assertRaises(ValueError):
                cad.receipt(run, 'console.txt')
        (run / 'drawing.dxf').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.capture(run, self.console(run))


if __name__ == '__main__':
    unittest.main()
