"""Finite scan-model checks of the actual lowered example requests, not PLC simulation."""
from __future__ import annotations

import re

import pytest

from contoh.teaching_cases import VENDORS, request_for, symbol_map


class ScanModel:
    """Test-only boolean/TON interpreter; reject anything outside this explicit subset."""
    def __init__(self, vendor, number):
        self.values = {}
        self.elapsed = {}
        mapping = symbol_map(vendor, number)
        inverse = {address: name for name, address in mapping.items()}
        request = request_for(vendor, number)
        self.rungs = request.get('main', request.get('rungs'))
        self.inverse = inverse

    def ref(self, address):
        return self.inverse.get(address, address)

    def scan(self, inputs=None, dt=0.1):
        self.values.update(inputs or {})
        def contacts(elements):
            result = True
            for element in elements:
                if 'branch' in element:
                    value = any(contacts(leg) for leg in element['branch'])
                else:
                    assert element['kind'] in ('NO', 'NC'), element
                    value = bool(self.values.get(self.ref(element['args'][0]), False))
                    if element['kind'] == 'NC':
                        value = not value
                result = result and value
            return result
        for rung in self.rungs:
            *condition, output = rung['elements']
            powered = contacts(condition)
            kind, args = output['kind'], output['args']
            name = self.ref(args[0])
            if kind == 'OUT':
                self.values[name] = powered
            elif kind in ('SET', 'OUTL'):
                if powered:
                    self.values[name] = True
            elif kind in ('TON', 'TMR'):
                if args[0].startswith('%'):
                    done_address = args[0] + '.Q'
                elif '.' in args[0] and not args[0].endswith('.Q'):
                    done_address = args[0] + '.DN'
                elif args[0].startswith('T') and args[0][1:].isdigit():
                    done_address = args[0]
                else:
                    done_address = args[0] + '.Q'
                name = self.ref(done_address).removesuffix('.Q')
                if kind == 'TMR':
                    duration = int(args[1].removeprefix('K')) / 10
                elif len(args) == 3:
                    duration = int(args[1]) * int(args[2]) / 1000 if '.' in args[0] and not args[0].startswith('%') else int(args[1])
                else:
                    duration = float(re.fullmatch(r'(?:T#)?(\d+)(?:[sS])?', str(args[1]))[1])
                self.elapsed[name] = round(self.elapsed.get(name, 0) + dt, 6) if powered else 0
                self.values[name + '.Q'] = powered and self.elapsed[name] >= duration
            else:
                raise ValueError(f'Unsupported scan-model instruction: {kind}')
        return dict(self.values)


@pytest.mark.parametrize('vendor', VENDORS)
@pytest.mark.parametrize('case', (1, 2))
def test_held_start_cannot_start_at_powerup_or_restart_after_stop(vendor, case):
    model = ScanModel(vendor, case)
    healthy = {'StartPB': True, 'StopHealthy': True, 'EStopHealthy': True, 'GuardHealthy': True}
    for _ in range(50):
        result = model.scan(healthy)
        assert not result.get('Motor', False)
        assert not result.get('Horn', False)
    model.scan({'StartPB': False})
    result = model.scan({'StartPB': True})
    assert result['Horn'] and not result['Motor']
    for _ in range(29):
        result = model.scan()
    assert result['Motor'] and not result['Horn']
    result = model.scan({'StopHealthy': False})
    assert not result['Motor'] and not result['Horn']
    for _ in range(50):
        result = model.scan({'StopHealthy': True})
        assert not result['Motor'] and not result['Horn']
    model.scan({'StartPB': False})
    assert model.scan({'StartPB': True})['Horn']


@pytest.mark.parametrize('vendor', VENDORS)
def test_guard_loss_drops_case01_and_requires_a_new_start(vendor):
    model = ScanModel(vendor, 1)
    model.scan({'StartPB': False, 'StopHealthy': True, 'EStopHealthy': True, 'GuardHealthy': True})
    for _ in range(35):
        result = model.scan({'StartPB': True})
    assert result['Motor']
    assert not model.scan({'GuardHealthy': False})['Motor']
    for _ in range(35):
        result = model.scan({'GuardHealthy': True})
        assert not result['Motor'] and not result['Horn']


@pytest.mark.parametrize('vendor', VENDORS)
def test_traffic_cycle_has_four_independent_triplets_and_no_conflicting_green(vendor):
    model = ScanModel(vendor, 7)
    seen = []
    for _ in range(850):
        result = model.scan()
        for approach in ('North', 'South', 'East', 'West'):
            assert sum(bool(result[approach + colour]) for colour in ('Red', 'Yellow', 'Green')) == 1
        assert result['PedRed'] != result['PedGreen']
        assert not (result['NorthGreen'] and result['EastGreen'])
        if result['PedGreen']:
            assert all(result[a + 'Red'] for a in ('North', 'South', 'East', 'West'))
        phase = ('NS' if result['NorthGreen'] else 'EW' if result['EastGreen'] else 'PED' if result['PedGreen'] else 'RED')
        if not seen or phase != seen[-1]:
            seen.append(phase)
    assert seen[:10] == ['RED', 'NS', 'RED', 'EW', 'RED', 'PED', 'RED', 'NS', 'RED', 'EW']


@pytest.mark.parametrize('vendor', VENDORS)
def test_corrupt_multiple_traffic_phases_command_all_red(vendor):
    model = ScanModel(vendor, 7)
    model.values.update({'Initialised': True, 'Stage1': True, 'Stage4': True})
    result = model.scan()
    assert all(result[a + 'Red'] for a in ('North', 'South', 'East', 'West'))
    assert result['PedRed'] and not result['PedGreen']
    assert not any(result[a + c] for a in ('North', 'South', 'East', 'West') for c in ('Green', 'Yellow'))
