import copy
import json
import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/architectural-drawing-generation/scripts'))
import project_brief as intake

FIXTURE = ROOT / 'skills/architectural-drawing-generation/references/incomplete-villa.brief.json'


def record(key, value, unit=None, status='CONFIRMED'):
    r = {'key': key, 'value': value, 'unit': unit, 'status': status, 'literal': str(value),
         'source': {'kind': 'user', 'location': 'test brief'}, 'confidence': 1,
         'targets': ['project'], 'revision': 1, 'evidence': ['test decision'],
         'disposition': 'MAPPED', 'approval': None}
    if status == 'CONFIRMED':
        r['approval'] = {'by': 'test operator', 'record_sha256': intake.approval_hash(r)}
    return r


def ready():
    return {'schema': 'gridline-project-brief.v1', 'mode': 'EXACT_3D',
            'ledger': {'schema': 'gridline-source-detail-ledger.v1', 'revision': 1, 'records': [
                record('units', 'mm'), record('plot_boundary', [[0, 0], [20000, 0], [20000, 10000]], 'mm'),
                record('floor_to_floor_heights', [3000], 'mm'),
                record('roof', {'type': 'flat', 'geometry_source': 'approved section S1'})]}}


class ProjectBriefTests(unittest.TestCase):
    def test_exact_intake_example_blocks_unknown_plot_heights_roof(self):
        brief = json.loads(FIXTURE.read_text())
        result = intake.evaluate(brief)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertEqual([q['key'] for q in result['questions']], ['plot_boundary', 'floor_to_floor_heights', 'roof'])
        self.assertEqual(brief['ledger']['records'][0]['status'], 'CONFIRMED')
        self.assertFalse(result['native_write_authorized'])
        with self.assertRaises(ValueError):
            intake.to_building_spec(brief, {})

    def test_concept_is_provisional_and_does_not_fill_missing_values(self):
        brief = json.loads(FIXTURE.read_text())
        brief['mode'] = 'CONCEPT'
        before = copy.deepcopy(brief)
        result = intake.evaluate(brief)
        self.assertEqual(result['state'], 'READY_CONCEPT_ONLY')
        self.assertTrue(result['provisional'])
        self.assertEqual(brief, before)
        self.assertFalse(result['native_write_authorized'])

    def test_confirmation_is_bound_to_exact_record_not_only_status(self):
        for change in [('value', [3500]), ('unit', 'm'), ('source', {'kind': 'user', 'location': 'new'})]:
            brief = ready()
            brief['ledger']['records'][2][change[0]] = change[1]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'approval'):
                intake.evaluate(brief)

    def test_conflicts_never_proceed_even_in_concept(self):
        brief = ready()
        brief['mode'] = 'CONCEPT'
        brief['ledger']['records'][2]['status'] = 'CONFLICT'
        self.assertEqual(intake.evaluate(brief)['state'], 'CONFLICT')

    def test_invalid_numeric_values_and_undecided_roof_cannot_be_ready(self):
        for value in ([0], [True], ['3000'], [-1]):
            brief = ready()
            brief['ledger']['records'][2] = record('floor_to_floor_heights', value, 'mm')
            self.assertEqual(intake.evaluate(brief)['state'], 'NEEDS_INPUT')
        brief['ledger']['records'][2] = record('floor_to_floor_heights', [3000], 'unknown')
        self.assertEqual(intake.evaluate(brief)['state'], 'NEEDS_INPUT')
        brief = ready()
        brief['ledger']['records'][3] = record('roof', {'type': 'UNDECIDED', 'geometry_source': 'none'})
        self.assertEqual(intake.evaluate(brief)['state'], 'NEEDS_INPUT')

    def test_duplicate_ids_missing_units_and_unmapped_detail_rejected(self):
        brief = ready()
        brief['ledger']['records'].append(copy.deepcopy(brief['ledger']['records'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            intake.evaluate(brief)
        brief = ready()
        brief['ledger']['records'][0].pop('unit')
        with self.assertRaises(ValueError):
            intake.evaluate(brief)
        brief = ready()
        brief['ledger']['records'][0]['targets'] = []
        with self.assertRaisesRegex(ValueError, 'targets'):
            intake.evaluate(brief)

    def test_single_unscaled_image_creates_full_unknown_inventory(self):
        brief = ready()
        image = record('photo', None, status='UNKNOWN')
        image['source'] = {'kind': 'image', 'location': 'supplied-photo.png', 'region': [0, 0, 100, 100]}
        image.update(disposition='UNKNOWN', reason='single perspective, hidden geometry')
        brief['ledger']['records'].append(image)
        result = intake.evaluate(brief)
        keys = {x['key'] for x in result['blockers']}
        self.assertIn('reference_scale', keys)
        self.assertTrue(set(intake.DETAILS).issubset(keys))
        self.assertEqual(result['state'], 'NEEDS_INPUT')

    def test_degenerate_crossing_boundary_and_confirmed_blocked_detail_fail(self):
        for points in ([[0, 0], [0, 0], [0, 0]], [[0, 0], [1, 0], [2, 0]],
                       [[0, 0], [3, 3], [0, 2], [3, 0]]):
            brief = ready()
            brief['ledger']['records'][1] = record('plot_boundary', points, 'mm')
            self.assertEqual(intake.evaluate(brief)['state'], 'NEEDS_INPUT')
        for key in ('roof', 'extra_detail'):
            brief = ready()
            r = record(key, {'type': 'flat', 'geometry_source': 'S1'})
            r.update(disposition='BLOCKED', reason='requires confirmation')
            r['approval']['record_sha256'] = intake.approval_hash(r)
            if key == 'roof':
                brief['ledger']['records'][3] = r
            else:
                brief['ledger']['records'].append(r)
            self.assertEqual(intake.evaluate(brief)['state'], 'NEEDS_INPUT')

    def test_translation_missing_height_blocks_without_keyerror(self):
        brief = ready()
        building = json.loads((ROOT / 'skills/architectural-drawing-generation/references/example-house.building.json').read_text())
        height = building['levels'][0]['height']
        brief['ledger']['records'][2] = record('floor_to_floor_heights', [height], 'mm')
        building['levels'][0].pop('height')
        with self.assertRaisesRegex(ValueError, 'source level heights conflict'):
            intake.to_building_spec(brief, building)

    def test_translation_float_rounding_accepts_converted_heights(self):
        brief = ready()
        building = json.loads((ROOT / 'skills/architectural-drawing-generation/references/example-house.building.json').read_text())
        # Binary floating point conversions from metres need mm-level tolerance.
        height_mm = 123.456
        brief['ledger']['records'][2] = record('floor_to_floor_heights', [height_mm / 1000], 'm')
        building['levels'][0]['height'] = height_mm
        self.assertEqual(intake.to_building_spec(brief, building), building)
        building['levels'][0]['height'] = height_mm + 0.002
        with self.assertRaisesRegex(ValueError, 'conflict'):
            intake.to_building_spec(brief, building)

    def test_cli_rejects_symlink_and_reads_regular_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            regular = root / 'brief.json'
            regular.write_text(json.dumps(ready()))
            self.assertEqual(intake.main([str(regular)]), 0)
            symlink = root / 'shortcut.json'
            symlink.symlink_to(regular)
            self.assertEqual(intake.main([str(symlink)]), 2)

    def test_ready_intake_is_not_bim_delivery_or_native_write_permission(self):
        brief = ready()
        self.assertEqual(intake.evaluate(brief)['state'], 'READY')
        self.assertFalse(intake.evaluate(brief)['native_write_authorized'])
        brief['mode'] = 'BIM_DELIVERY'
        result = intake.evaluate(brief)
        self.assertEqual(result['state'], 'NEEDS_INPUT')
        self.assertIn('bim_evidence', {x['key'] for x in result['blockers']})

    def test_source_translation_checks_existing_heights_and_preserves_source(self):
        brief = ready()
        building = json.loads((ROOT / 'skills/architectural-drawing-generation/references/example-house.building.json').read_text())
        height = building['levels'][0]['height']
        brief['ledger']['records'][2] = record('floor_to_floor_heights', [height / 1000], 'm')
        translated = intake.to_building_spec(brief, building)
        self.assertEqual(translated, building)
        self.assertIsNot(translated, building)
        building['levels'][0]['height'] += 100
        with self.assertRaisesRegex(ValueError, 'conflict'):
            intake.to_building_spec(brief, building)


if __name__ == '__main__':
    unittest.main()
