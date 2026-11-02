"""Behavioral checks for fourteen independent traffic-light output addresses."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'contoh' / 'omron'))
from offline import Machine


class TrafficLightTest(unittest.TestCase):
    def test_all_lamps_have_expected_color_in_every_phase(self):
        path = ROOT / 'contoh/omron/07-cp1h-x40dt-d-traffic-light/program.json'
        program = json.loads(path.read_text(encoding='utf-8'))
        rungs = [r for s in program['sections'] for r in s['rungs']]
        heads = [('100.00','100.01','100.02'), ('100.03','100.04','100.05'),
                 ('100.06','100.07','101.00'), ('101.01','101.02','101.03')]
        for phase in range(9):
            with self.subTest(phase=phase):
                m = Machine()
                m.scan(rungs, {}, 0)
                m.scan(rungs, {'D0': phase}, 0)
                expected_ns = 2 if phase == 1 else 1 if phase == 2 else 0
                expected_ew = 2 if phase == 4 else 1 if phase == 5 else 0
                for i, head in enumerate(heads):
                    expected = expected_ns if i < 2 else expected_ew
                    self.assertEqual([m.bit(bit) for bit in head], [j == expected for j in range(3)])
                self.assertEqual(m.bit('101.04'), phase != 7)
                self.assertEqual(m.bit('101.05'), phase == 7)


if __name__ == '__main__':
    unittest.main()
