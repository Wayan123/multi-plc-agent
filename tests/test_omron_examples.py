"""Exercise authored Omron LD, not a second hand-written process model."""
from pathlib import Path
import csv
import json
import shutil
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'contoh' / 'omron'))


class OmronInstructions(unittest.TestCase):
    def test_signed_multiply_and_long_divide_preserve_negative_values(self):
        from offline import Machine
        machine = Machine()
        rungs = [{'instructions': ['LD P_On', 'MOVL(498) &6000 D170',
                                  '*(420) D100 &2000 D110', '/L(431) D110 D170 D120',
                                  '-L(411) D120 &1000 D130']}]
        machine.scan(rungs, {'D100': 6000})
        self.assertEqual(machine.word('D110') | machine.word('D111') << 16, 12000000)
        self.assertEqual(machine.signed_long('D130'), 1000)
        machine.scan(rungs, {'D100': 0xFF38})  # -200, not 65336
        self.assertEqual(machine.signed_long('D120'), -66)  # signed division truncates toward zero
        self.assertEqual(machine.signed_long('D130'), -1066)

    def test_signed_comparison_does_not_treat_disconnected_input_as_large_positive(self):
        from offline import Machine
        m = Machine()
        m.scan([{'instructions': ['LD<S(312) D100 &0', 'OUT W0.00']},
                {'instructions': ['LD<(310) D100 &0', 'OUT W0.01']}], {'D100': 0x8000})
        self.assertTrue(m.bit('W0.00'))
        self.assertFalse(m.bit('W0.01'))

    def test_byte_unpacking_preserves_negative_temperature_and_ignores_padding(self):
        from offline import Machine
        m = Machine()
        m.scan([{'instructions': ['LD P_On', 'ANDW(034) D1254 #00FF D110', 'SWAP(637) &1 D110',
                                  'ANDW(034) D1255 #FF00 D111', 'SWAP(637) &1 D111',
                                  'ORW(035) D110 D111 D100',
                                  'ANDW(034) D1255 #00FF D112', 'SWAP(637) &1 D112',
                                  'ANDW(034) D1256 #FF00 D113', 'SWAP(637) &1 D113',
                                  'ORW(035) D112 D113 D101']}],
               {'D1254': 0x04FF, 'D1255': 0x3302, 'D1256': 0x22A7})
        self.assertEqual(m.signed_word('D100'), -205)
        self.assertEqual(m.word('D101'), 546)

    def test_unknown_opcode_is_an_error_not_a_passing_scenario(self):
        from offline import Machine
        with self.assertRaises(ValueError):
            Machine().scan([{'instructions': ['LD P_On', 'FAKE(999) D100']}], {})

class OmronModbusBoundaries(unittest.TestCase):
    def variants(self):
        folder = ROOT / 'contoh' / 'omron'
        for path in [folder / '05-cp1h-xy-md02' / 'cp1h-x40dt-d.json',
                     folder / '05-cp1h-xy-md02' / 'cp1h-xa40dt-d.json',
                     folder / '06-cp2e-n30dt-d-xy-md02' / 'program.json']:
            program = json.loads(path.read_text(encoding='utf-8'))
            base, auxiliary = (1200, 'A640') if program['device'] == 'CP2E-N' else (32200, 'A641')
            yield program, base, auxiliary

    def response(self, base, auxiliary):
        return {auxiliary + '.00': False, auxiliary + '.01': True, auxiliary + '.02': False,
                f'D{base+50}':1, f'D{base+51}':4, f'D{base+52}':0, f'D{base+53}':5,
                f'D{base+54}':0x0401, f'D{base+55}':0x3102, f'D{base+56}':0x22A7}

    def test_disable_while_busy_finishes_owned_request_without_publishing_validity(self):
        from offline import Machine
        for program, base, auxiliary in self.variants():
            with self.subTest(model=program['model']):
                m = Machine()
                rungs = [r for s in program['sections'] for r in s['rungs']]
                m.scan(rungs, {'W10.00':True}, 1000)
                m.scan(rungs, {}, 1000)
                m.scan(rungs, {'W10.00':False}, 1000)
                self.assertTrue(m.bit(auxiliary + '.00'))  # never cancel system execution
                self.assertTrue(m.bit('W20.00'))  # keep ownership until completion
                self.assertFalse(m.bit('W20.01'))
                m.scan(rungs, self.response(base, auxiliary))
                self.assertEqual((m.word('D100'), m.word('D101')), (305,546))
                self.assertFalse(m.bit('W20.00'))
                self.assertFalse(m.bit('W20.01'))
                m.scan(rungs, {'W10.00':True}, 1000)
                self.assertTrue(m.bit(auxiliary + '.00'))
                self.assertTrue(m.bit('W20.00'))
                self.assertFalse(m.bit('W20.01'))  # old normal flag cannot publish stale data
                m.scan(rungs, {})
                self.assertFalse(m.bit('W20.01'))
                response = self.response(base, auxiliary)
                response.update({f'D{base+54}':0x04FF, f'D{base+55}':0x3302})
                m.scan(rungs, response)
                self.assertEqual(m.signed_word('D100'), -205)
                self.assertTrue(m.bit('W20.01'))

    def test_independent_success_guards_retain_last_good_and_classify_error(self):
        from offline import Machine
        for program, base, auxiliary in self.variants():
            failures = [('function', {f'D{base+51}':3}, 0),
                        ('length', {f'D{base+53}':4}, 0),
                        ('raw_error_without_flag', {f'D{base+52}':128}, 128),
                        ('neither_completion_flag', {auxiliary+'.01':False}, 0)]
            for name, changes, raw_error in failures:
                with self.subTest(model=program['model'], failure=name):
                    m = Machine()
                    rungs = [r for s in program['sections'] for r in s['rungs']]
                    m.scan(rungs, {'W10.00':True}, 1000)
                    m.scan(rungs, {}, 1000)
                    m.scan(rungs, self.response(base, auxiliary))
                    m.scan(rungs, {}, 1000)
                    response = self.response(base, auxiliary)
                    response.update(changes)
                    m.scan(rungs, response)
                    self.assertEqual((m.word('D100'),m.word('D101')), (305,546))
                    self.assertFalse(m.bit('W20.01'))
                    self.assertTrue(m.bit('W20.02'))
                    self.assertFalse(m.bit('W20.00'))
                    self.assertEqual(m.word('D102'), raw_error)
                    self.assertEqual(m.word('D103'), 1)  # inconsistent/invalid response, distinct from raw code


class OmronArtifactBoundaries(unittest.TestCase):
    def test_modified_source_is_rejected_even_if_its_manifest_hash_is_updated(self):
        from check import check
        from check_sync import digest
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'omron'
            shutil.copytree(ROOT/'contoh'/'omron', copied, ignore=shutil.ignore_patterns('__pycache__'))
            case = copied/'01-cp1h-x40dt-d'
            source = case/'program.json'
            program = json.loads(source.read_text())
            program['sections'][0]['rungs'][0]['instructions'] = ['LD P_On', 'OUT 100.00']
            source.write_text(json.dumps(program), encoding='utf-8')
            manifest = json.loads((case/'manifest.json').read_text())
            manifest['files']['program.json'] = digest(source)
            (case/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Native evidence is stale'):
                check(copied)

    def test_wrong_cpu_template_is_rejected_before_backend_launch_or_output_write(self):
        from mcp_build import build, draft_seed
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            template = folder/'wrong-XA.cxt'
            template.write_text(draft_seed('CP1H','XA'), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'CPU mismatch'):
                build(folder/'not-needed-config.json',
                      ROOT/'contoh'/'omron'/'01-cp1h-x40dt-d'/'program.json',
                      folder/'new.cxt', template, False, folder/'receipt.json')
            self.assertFalse((folder/'new.cxt').exists())

    def bindings(self, manifests):
        rows = []
        for case, manifest in manifests.items():
            with (ROOT/'contoh'/'omron'/case/'signals.csv').open(newline='', encoding='utf-8') as handle:
                signal = next(s['signal'] for s in csv.DictReader(handle) if s['hmi_access']=='read')
            for model in manifest['models']:
                rows.append({'example_id':case,'variant':model,
                             'signals':[{'signal_id':signal,'hmi_tag':case+'.'+model,'access':'read'}]})
        return {'schema_version':1,'bindings':rows}

    def test_hmi_cannot_omit_second_cp1h_modbus_variant(self):
        from check_sync import canonical, verify_bindings
        folder = ROOT/'contoh'/'omron'
        manifests = canonical(folder)
        binding = self.bindings(manifests)
        binding['bindings'] = [r for r in binding['bindings']
                               if (r['example_id'],r['variant']) != ('05-cp1h-xy-md02','CP1H-XA40DT-D')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bindings.json'
            path.write_text(json.dumps(binding), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_bindings(path, folder, manifests)

    def test_hmi_cannot_turn_read_only_signal_into_write_access(self):
        from check_sync import canonical, verify_bindings
        folder = ROOT/'contoh'/'omron'
        manifests = canonical(folder)
        binding = self.bindings(manifests)
        binding['bindings'][0]['signals'][0]['access'] = 'write'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bindings.json'
            path.write_text(json.dumps(binding), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_bindings(path, folder, manifests)


class OmronReviewedGuards(unittest.TestCase):
    def test_receipt_cannot_overwrite_program_input(self):
        from mcp_build import build
        program = ROOT/'contoh'/'omron'/'01-cp1h-x40dt-d'/'program.json'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Receipt must not alias'):
                build(Path(directory)/'c.json', program, Path(directory)/'new.cxt', None, True, program)

    def test_template_with_second_program_is_rejected(self):
        from mcp_build import build, draft_seed
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            text = draft_seed('CP1H', 'X').replace('Program[0]:=', 'Program[0]:=\n  Program[1]:=', 1)
            (folder/'t.cxt').write_text(text, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'exactly one program'):
                build(folder/'c.json', ROOT/'contoh'/'omron'/'01-cp1h-x40dt-d'/'program.json',
                      folder/'new.cxt', folder/'t.cxt', False, folder/'r.json')

    def test_swapped_native_artifact_is_rejected_after_inventory_regeneration(self):
        from check import check
        from check_sync import digest
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)/'omron'
            shutil.copytree(ROOT/'contoh'/'omron', copied, ignore=shutil.ignore_patterns('__pycache__'))
            case = copied/'03-cp1h-xa-analog'
            manifest = json.loads((case/'manifest.json').read_text())
            target = case/manifest['artifacts'][0]['cxt']
            donor = copied/'02-cp1h-xa40dt-d'/json.loads((copied/'02-cp1h-xa40dt-d'/'manifest.json').read_text())['artifacts'][0]['cxt']
            target.write_bytes(donor.read_bytes())
            manifest['files'] = {k: digest(case/k) for k in manifest['files']}
            (case/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'differs from compiled evidence'):
                check(copied)

    def test_cp1h_modbus_case_requires_both_variants(self):
        from check_sync import verify_manifest
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory)/'05-cp1h-xy-md02'
            shutil.copytree(ROOT/'contoh'/'omron'/'05-cp1h-xy-md02', copied)
            manifest = json.loads((copied/'manifest.json').read_text())
            manifest['programs'] = manifest['programs'][:1]
            manifest['models'] = manifest['models'][:1]
            (copied/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fixed example contract'):
                verify_manifest(copied/'manifest.json')



if __name__ == '__main__':
    unittest.main()
