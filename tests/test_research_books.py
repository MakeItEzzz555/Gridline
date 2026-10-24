"""Check citation coverage and installation integrity, not book truth or compliance."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResearchBookTests(unittest.TestCase):
    def test_all_titles_have_claims_limits_and_portable_references(self):
        data = json.loads((ROOT / 'docs/research/books/bibliography.yaml').read_text())
        books = data['books']
        self.assertEqual({b['id'] for b in books}, {f'B{i:02}' for i in range(1, 16)})
        self.assertEqual(len(books), 15)
        claims = [json.loads(line) for line in (ROOT / 'docs/research/books/evidence-ledger.jsonl').read_text().splitlines()]
        self.assertEqual(len({c['claim_id'] for c in claims}), len(claims))
        for book in books:
            with self.subTest(book=book['id']):
                self.assertFalse(book['full_text_read'])
                self.assertEqual(book['normativity'], 'NONBINDING_REFERENCE')
                self.assertTrue(book['observed_contents'])
                self.assertTrue(book['challenge'])
                isbn = book['isbn']
                self.assertRegex(isbn, r'^\d{13}$')
                self.assertEqual(sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn)) % 10, 0)
                path = ROOT / book['playbook']
                self.assertIn('Counterexample:', path.read_text())
                self.assertIn('UNKNOWN', path.read_text())
                self.assertEqual(path.read_bytes(), (ROOT / 'providers/claude' / book['playbook']).read_bytes())
                skill = path.parents[1]
                self.assertIn(f'(references/{path.name})', (skill / 'SKILL.md').read_text())
                related = [c for c in claims if c['book_id'] == book['id']]
                self.assertEqual(len(related), 3)
                for claim in related:
                    self.assertTrue(claim['counterexample'])
                    self.assertTrue(claim['source_url'].startswith('https://'))
                    self.assertFalse(claim['redistribution_allowed'])
                    self.assertIsNone(claim['page'])
                    if claim['evidence_level'] == 'REASONED_INFERENCE':
                        self.assertEqual(claim['final_status'], 'NEEDS_PRO_REVIEW')

    def test_unresolved_publisher_is_not_counted_as_verified(self):
        books = json.loads((ROOT / 'docs/research/books/bibliography.yaml').read_text())['books']
        material = next(b for b in books if b['id'] == 'B14')
        self.assertEqual(material['metadata_status'], 'UNVERIFIED')
        self.assertEqual(material['contents_availability'], 'AUTHOR_OVERVIEW_ONLY')
        self.assertEqual(next(b for b in books if b['id'] == 'B02')['isbn'], '9781394279289')
