"""Original bounded digital/traffic examples lowered to existing offline MCP dialects.

No PLC runtime is emulated here. request_for() returns input to the real vendor
backend. Native acceptance and saved readback must be collected separately.
"""
from __future__ import annotations

from copy import deepcopy

VENDORS = ('outseal', 'haiwell', 'delta', 'schneider', 'codesys', 'beckhoff', 'sysmac')
CASES = (1, 2, 7)
DURATIONS = (2, 10, 3, 2, 10, 3, 2, 5)
LAMPS = tuple(a + c for a in ('North', 'South', 'East', 'West') for c in ('Red', 'Yellow', 'Green')) + ('PedRed', 'PedGreen')


def contact(name, inverted=False):
    return {'kind': 'NC' if inverted else 'NO', 'args': [name]}


def branch(*legs):
    return {'branch': [[contact(n) if isinstance(n, str) else n for n in leg] for leg in legs]}


def rung(comment, conditions, kind, *args):
    return {'comment': comment, 'elements': [*deepcopy(conditions), {'kind': kind, 'args': list(args)}]}


def make_case(number):
    if number in (1, 2):
        inputs = ['StartPB', 'StopHealthy', 'EStopHealthy'] + (['GuardHealthy'] if number == 1 else [])
        healthy = [contact(n) for n in inputs if n != 'StartPB']
        rungs = [
            rung('Arm after start release with all permissives healthy', [branch(['Armed'], [contact('StartPB', True)]), *healthy], 'OUT', 'Armed'),
            rung('Seal in run; permissive loss immediately drops run', [branch(['RunRequest'], ['StartPB', 'Armed']), *healthy], 'OUT', 'RunRequest'),
            rung('Three-second start warning delay', [contact('RunRequest')], 'TON', 'StartDelay', 'T#3S'),
            rung('Horn sounds only while the start delay is incomplete', [contact('RunRequest'), contact('StartDelay.Q', True)], 'OUT', 'Horn'),
            rung('Motor starts only after the warning delay', [contact('RunRequest'), contact('StartDelay.Q')], 'OUT', 'Motor'),
        ]
        return {'inputs': inputs, 'outputs': ['Motor', 'Horn'], 'bits': ['Armed', 'RunRequest'], 'timers': ['StartDelay'], 'rungs': rungs}
    if number != 7:
        raise ValueError('Only complete digital cases 01, 02 and 07 are defined by this generator')
    stages = [f'Stage{i}' for i in range(8)]
    holds = [f'Hold{i}' for i in range(8)]
    advances = [f'Advance{i}' for i in range(8)]
    timers = [f'StageTimer{i}' for i in range(8)]
    permits = ['NSGreenPermit', 'NSYellowPermit', 'EWGreenPermit', 'EWYellowPermit', 'PedGreenPermit']
    rungs = []
    for i, duration in enumerate(DURATIONS):
        rungs.append(rung(f'Phase {i}: nominal {duration} seconds', [contact(stages[i])], 'TON', timers[i], f'T#{duration}S'))
    # Snapshot all transition conditions before changing any phase bit. This
    # prevents a stale timer Q from cascading through several phases in one scan.
    for i in range(8):
        rungs.append(rung(f'Hold phase {i} until its timer finishes', [contact(stages[i]), contact(timers[i] + '.Q', True)], 'OUT', holds[i]))
        rungs.append(rung(f'Capture completed phase {i}', [contact(stages[i]), contact(timers[i] + '.Q')], 'OUT', advances[i]))
    for i in range(8):
        legs = [[holds[i]], [advances[(i - 1) % 8]]]
        if i == 0:
            legs.append([contact('Initialised', True)])
        rungs.append(rung(f'Update phase {i} from captured conditions only', [branch(*legs)], 'OUT', stages[i]))
    rungs.append(rung('Initialise non-retained zero-start example state once', [contact('Initialised', True)], 'SET', 'Initialised'))
    for permit, phase in zip(permits, (1, 2, 4, 5, 7)):
        conditions = [contact(stages[phase])] + [contact(s, True) for j, s in enumerate(stages) if j != phase]
        rungs.append(rung(f'{permit}: reject overlapping or corrupt phase bits', conditions, 'OUT', permit))
    for approach in ('North', 'South', 'East', 'West'):
        group = 'NS' if approach in ('North', 'South') else 'EW'
        rungs += [
            rung(f'{approach} red: no permitted green or yellow', [contact(group + 'GreenPermit', True), contact(group + 'YellowPermit', True)], 'OUT', approach + 'Red'),
            rung(f'{approach} independent yellow lamp', [contact(group + 'YellowPermit')], 'OUT', approach + 'Yellow'),
            rung(f'{approach} independent green lamp', [contact(group + 'GreenPermit')], 'OUT', approach + 'Green'),
        ]
    rungs += [rung('Pedestrian red outside the dedicated pedestrian phase', [contact('PedGreenPermit', True)], 'OUT', 'PedRed'),
              rung('Pedestrian green only with all vehicle phases inhibited', [contact('PedGreenPermit')], 'OUT', 'PedGreen')]
    return {'inputs': [], 'outputs': list(LAMPS), 'bits': ['Initialised', *stages, *holds, *advances, *permits], 'timers': timers, 'rungs': rungs}


def _timer_address(vendor, index):
    if vendor in ('codesys', 'beckhoff', 'sysmac'):
        return None
    return f'T.{index + 1}' if vendor == 'outseal' else f'%TM{index}' if vendor == 'schneider' else f'T{index}'


def symbol_map(vendor, number):
    if vendor not in VENDORS:
        raise ValueError(f'Unsupported example dialect: {vendor}')
    case = make_case(number)
    names = case['inputs'] + case['bits'] + case['outputs']
    if vendor in ('codesys', 'beckhoff', 'sysmac'):
        return {name: name for name in names + [t + '.Q' for t in case['timers']]}
    result = {}
    for i, name in enumerate(case['inputs']):
        result[name] = f'S.{i + 1}' if vendor == 'outseal' else f'%I0.{i}' if vendor == 'schneider' else f'X{i}'
    for i, name in enumerate(case['bits']):
        index = i + (10 if number == 7 else 0)
        result[name] = f'B.{index + 1}' if vendor == 'outseal' else f'%M{index}' if vendor == 'schneider' else f'M{index}'
    for i, name in enumerate(case['outputs']):
        if vendor == 'outseal':
            address = f'R.{i + 1}'
        elif number == 7:
            address = f'%M{100 + i}' if vendor == 'schneider' else f'M{100 + i}'
        else:
            address = f'%Q0.{i}' if vendor == 'schneider' else f'Y{i}'
        result[name] = address
    for i, timer in enumerate(case['timers']):
        address = _timer_address(vendor, i)
        suffix = '.DN' if vendor == 'outseal' else '.Q' if vendor == 'schneider' else ''
        result[timer + '.Q'] = address + suffix
    return result


def request_for(vendor, number):
    case = make_case(number)
    mapping = symbol_map(vendor, number)
    rungs = deepcopy(case['rungs'])
    def lower_contacts(elements):
        for element in elements:
            if 'branch' in element:
                for leg in element['branch']:
                    lower_contacts(leg)
            else:
                element['args'][0] = mapping[element['args'][0]]
    for row in rungs:
        lower_contacts(row['elements'][:-1])
        output = row['elements'][-1]
        if output['kind'] == 'TON':
            name, preset = output['args']
            if vendor in ('codesys', 'beckhoff', 'sysmac'):
                continue
            index = case['timers'].index(name)
            seconds = int(preset[2:-1])
            address = _timer_address(vendor, index)
            if vendor == 'delta':
                output.update(kind='TMR', args=[address, f'K{seconds * 10}'])
            elif vendor == 'outseal':
                output['args'] = [address, '1000', str(seconds)]
            elif vendor == 'schneider':
                output['args'] = [address, str(seconds), '1s']
            else:
                output['args'] = [address, str(seconds)]
        else:
            output['args'][0] = mapping[output['args'][0]]
            if output['kind'] == 'SET' and vendor == 'outseal':
                output['kind'] = 'OUTL'
    if vendor in ('codesys', 'beckhoff', 'sysmac'):
        return {'variables': [{'name': name, 'type': 'BOOL'} for name in case['inputs'] + case['bits'] + case['outputs']], 'rungs': rungs}
    aliases = {address: name for name, address in mapping.items() if not name.endswith('.Q')}
    if vendor == 'outseal':
        initial = [rung('Clear non-retained example state at startup', [contact(mapping[name])], 'OUTU', mapping[name]) for name in case['bits']]
        return {'name': f'Case{number:02}', 'board': 'Mega V3' if number == 7 else 'Nano V5', 'main': rungs, 'initial': initial, 'aliases': aliases}
    if vendor == 'schneider':
        return {'rungs': rungs, 'symbols': aliases}
    return {'rungs': rungs, 'aliases': aliases}


def siemens_documents(number):
    """V20 pattern: genuine LAD FCs, SCL timer helper, and an OB1 call chain."""
    case = make_case(number)
    state = f'State{number:02}'
    timer_fb = f'Timers{number:02}'
    all_bits = case['inputs'] + case['bits'] + case['outputs']
    done_bits = [timer + 'Q' for timer in case['timers']]
    data = [f'DATA_BLOCK "{state}"', "{ S7_Optimized_Access := 'TRUE' }", 'VERSION : 0.1', 'VAR']
    data += [f'    {name} : Bool := FALSE;' for name in all_bits + done_bits]
    data += ['END_VAR', 'BEGIN', 'END_DATA_BLOCK', '', f'FUNCTION_BLOCK "{timer_fb}"',
             "{ S7_Optimized_Access := 'TRUE' }", 'VERSION : 0.1', 'VAR_INPUT']
    data += [f'    Enable{i} : Bool;' for i in range(len(case['timers']))]
    data += ['END_VAR', 'VAR_OUTPUT']
    data += [f'    Done{i} : Bool;' for i in range(len(case['timers']))]
    data += ['END_VAR', 'VAR']
    data += [f'    Timer{i} : TON_TIME;' for i in range(len(case['timers']))]
    data += ['END_VAR', 'BEGIN']
    durations = [3] if number in (1, 2) else DURATIONS
    for i, duration in enumerate(durations):
        data += [f'    #Timer{i}(IN := #Enable{i}, PT := T#{duration}S);',
                 f'    #Done{i} := #Timer{i}.Q;']
    data += ['END_FUNCTION_BLOCK', '']

    def operand(name):
        return f'"{state}".{name.replace(".Q", "Q")}'

    def ladder_fc(name, rows):
        lines = ['{ S7_Optimized := "TRUE"; S7_Language := "LAD" }', f'FUNCTION "{name}" : Void']
        def contacts(elements):
            return [f'            {"Contact" if e["kind"] == "NO" else "I_Contact"}( {operand(e["args"][0])} )' for e in elements]
        for index, row in enumerate(rows):
            *condition, output = row['elements']
            legs = condition[0].get('branch')
            head, tail = (legs[0], condition[1:]) if legs else (condition, [])
            lines += ['    { S7_Language := "LAD" }', '    NETWORK', '        RUNG wire#powerrail', *contacts(head)]
            if legs:
                lines += [f'            wire#join{index}', *contacts(tail)]
            operation = {'OUT': 'Coil', 'SET': 'S_Coil'}[output['kind']]
            lines += [f'            {operation}( {operand(output["args"][0])} )', '        END_RUNG']
            if legs:
                for leg in legs[1:]:
                    lines += ['        RUNG wire#powerrail', *contacts(leg), f'        END_RUNG wire#join{index}']
            lines += ['    END_NETWORK', '']
        return '\ufeff' + '\n'.join([*lines, 'END_FUNCTION', ''])

    files = {'DataAndTimers.scl': '\n'.join(data)}
    boolean_rows = [row for row in case['rungs'] if row['elements'][-1]['kind'] != 'TON']
    if number in (1, 2):
        files[f'Request{number:02}.s7dcl'] = ladder_fc(f'Request{number:02}', boolean_rows[:2])
        files[f'Outputs{number:02}.s7dcl'] = ladder_fc(f'Outputs{number:02}', boolean_rows[2:])
    else:
        files[f'Logic{number:02}.s7dcl'] = ladder_fc(f'Logic{number:02}', boolean_rows)
    call = [f'FUNCTION "CallCase{number:02}" : Void', 'VERSION : 0.1', 'BEGIN']
    for i, name in enumerate(case['inputs']):
        call.append(f'    {operand(name)} := %I0.{i};')
    if number in (1, 2):
        call.append(f'    "Request{number:02}"();')
    parameters = []
    for i, timer in enumerate(case['timers']):
        enable = 'RunRequest' if number in (1, 2) else f'Stage{i}'
        parameters += [f'Enable{i} := {operand(enable)}', f'Done{i} => {operand(timer + ".Q")}']
    call.append(f'    "{timer_fb}_DB"(' + ', '.join(parameters) + ');')
    if number in (1, 2):
        call += [f'    "Outputs{number:02}"();', f'    %Q0.0 := {operand("Motor")};', f'    %Q0.1 := {operand("Horn")};']
    else:
        call.append(f'    "Logic{number:02}"();')
    call += ['END_FUNCTION', '']
    files['CallCase.scl'] = '\n'.join(call)
    files['Main.s7dcl'] = '\ufeff' + '\n'.join([
        '{ S7_Optimized := "TRUE"; S7_Language := "LAD" }', 'ORGANIZATION_BLOCK "Main"',
        '    { S7_Language := "LAD" }', '    NETWORK', '        RUNG wire#powerrail',
        f'            "CallCase{number:02}"()', '        END_RUNG', '    END_NETWORK', 'END_ORGANIZATION_BLOCK', ''])
    return files
