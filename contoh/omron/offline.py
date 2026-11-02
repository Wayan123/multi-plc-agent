"""Limited scan evaluator for these teaching examples. NOT CX-Simulator or a compiler.

Only explicitly implemented instructions execute; unknown instructions fail. Auxiliary
status, analog conversion and serial responses are scenario inputs, not simulated devices.
Words wrap to 16 bits. Signed multiplication/division use Omron's documented widths.
"""
from __future__ import annotations
import operator
import re


def signed(n: int, width: int) -> int:
    n &= (1 << width) - 1
    return n - (1 << width) if n & (1 << (width - 1)) else n


def next_word(address: str, offset: int) -> str:
    m = re.fullmatch(r'([A-Z]*)(\d+)', address.upper())
    if not m:
        raise ValueError(f'Not a word address: {address}')
    return f'{m[1]}{int(m[2]) + offset}'


class Machine:
    def __init__(self):
        self.memory: dict[str, int] = {}
        self.elapsed: dict[str, int] = {}
        self.previous: dict[str, bool] = {}
        self.scans = 0
        self.writes: list[str] = []

    def word(self, address: str) -> int:
        address = address.upper()
        if address.startswith('#'):
            return int(address[1:], 16) & 0xFFFF
        if address.startswith('&'):
            return int(address[1:]) & 0xFFFF
        return self.memory.get(next_word(address, 0), 0)

    def signed_word(self, address: str) -> int:
        return signed(self.word(address), 16)

    def long(self, address: str) -> int:
        if address.startswith(('#', '&')):
            return int(address[1:], 16 if address[0] == '#' else 10) & 0xFFFFFFFF
        return self.word(address) | self.word(next_word(address, 1)) << 16

    def signed_long(self, address: str) -> int:
        return signed(self.long(address), 32)

    def put_word(self, address: str, value: int):
        address = next_word(address, 0)
        self.memory[address] = int(value) & 0xFFFF
        self.writes.append(address)

    def put_long(self, address: str, value: int):
        self.put_word(address, value)
        self.put_word(next_word(address, 1), value >> 16)

    def bit(self, address: str) -> bool:
        if address == 'P_On':
            return True
        if address == 'P_Off':
            return False
        m = re.fullmatch(r'([A-Z]*\d+)\.(\d+)', address.upper())
        if m:
            return bool(self.word(m[1]) & (1 << int(m[2])))
        if re.fullmatch(r'T\d+', address.upper()):
            return bool(self.word(address))
        raise ValueError(f'Not a bit address: {address}')

    def put_bit(self, address: str, value: bool):
        m = re.fullmatch(r'([A-Z]*\d+)\.(\d+)', address.upper())
        if not m:
            raise ValueError(f'Not a bit destination: {address}')
        mask = 1 << int(m[2])
        self.put_word(m[1], self.word(m[1]) | mask if value else self.word(m[1]) & ~mask)

    def scan(self, rungs: list[dict], inputs: dict[str, int | bool], dt_ms: int = 100):
        if dt_ms < 0:
            raise ValueError('Negative scan duration')
        for address, value in inputs.items():
            (self.put_bit if '.' in address else self.put_word)(address, value)
        self.put_bit('A200.11', self.scans == 0)
        self.writes = []
        for rung in rungs:
            self._rung(rung['instructions'], dt_ms)
        self.scans += 1

    def _rung(self, lines: list[str], dt_ms: int):
        acc = False
        stack: list[bool] = []
        compare = {'=': operator.eq, '<>': operator.ne, '>': operator.gt,
                   '<': operator.lt, '>=': operator.ge, '<=': operator.le}
        for line in lines:
            parts = line.split()
            if not parts or parts[0].startswith("'"):
                continue
            op = re.sub(r'\(\d+\)$', '', parts[0]).upper()
            args = parts[1:]
            m = re.fullmatch(r'(LD|AND|OR)(<>|>=|<=|=|>|<)(S?)', op)
            if m:
                read = self.signed_word if m[3] else self.word
                value = compare[m[2]](read(args[0]), read(args[1]))
                if m[1] == 'LD':
                    stack.append(acc)
                    acc = value
                elif m[1] == 'AND':
                    acc = acc and value
                else:
                    acc = acc or value
            elif op in {'LD', 'LDNOT', 'AND', 'ANDNOT', 'OR', 'ORNOT'}:
                value = self.bit(args[0])
                if op.endswith('NOT'):
                    value = not value
                if op.startswith('LD'):
                    stack.append(acc)
                    acc = value
                elif op.startswith('AND'):
                    acc = acc and value
                else:
                    acc = acc or value
            elif op in {'ANDLD', 'ORLD'}:
                prev = stack.pop()
                acc = prev and acc if op == 'ANDLD' else prev or acc
            elif op == 'OUT':
                self.put_bit(args[0], acc)
            elif op in {'SET', 'RSET'}:
                if acc:
                    self.put_bit(args[0], op == 'SET')
            elif op == 'DIFU':
                key = args[0]
                self.put_bit(key, acc and not self.previous.get(key, False))
                self.previous[key] = acc
            elif op == 'TIM':
                key = f'T{int(args[0])}'
                self.elapsed[key] = self.elapsed.get(key, 0) + dt_ms if acc else 0
                target = int(args[1].lstrip('#')) * 100  # TIM BCD, 100 ms units
                self.put_word(key, int(acc and self.elapsed[key] >= target))
            elif op == 'MOV':
                if acc:
                    self.put_word(args[1], self.word(args[0]))
            elif op == 'MOVL':
                if acc:
                    self.put_long(args[1], self.long(args[0]))
            elif op in {'ANDW', 'ORW'}:
                if acc:
                    a, b = self.word(args[0]), self.word(args[1])
                    self.put_word(args[2], a & b if op == 'ANDW' else a | b)
            elif op == 'SWAP':
                if acc:
                    for i in range(self.word(args[0])):
                        dest = next_word(args[1], i)
                        value = self.word(dest)
                        self.put_word(dest, (value << 8) | (value >> 8))
            elif op == '*':
                if acc:
                    self.put_long(args[2], self.signed_word(args[0]) * self.signed_word(args[1]))
            elif op in {'-L', '+L'}:
                if acc:
                    a, b = self.signed_long(args[0]), self.signed_long(args[1])
                    result = a - b if op == '-L' else a + b
                    if not -(1 << 31) <= result < (1 << 31):
                        raise ValueError('Signed32 arithmetic overflow')
                    self.put_long(args[2], result)
            elif op == '/L':
                if acc:
                    a, b = self.signed_long(args[0]), self.signed_long(args[1])
                    if b == 0 or (a == -(1 << 31) and b == -1):
                        raise ValueError('Undefined signed32 division')
                    quotient = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
                    self.put_long(args[2], quotient)
                    self.put_long(next_word(args[2], 2), a - quotient * b)
            elif op == 'END':
                break
            else:
                raise ValueError(f'Unsupported offline instruction: {line}')


def run_scenarios(program: dict) -> list[dict]:
    rungs = [rung for section in program['sections'] for rung in section['rungs']]
    results = []
    for scenario in program['scenarios']:
        m = Machine()
        for i, scan in enumerate(scenario['scans']):
            m.scan(rungs, scan.get('inputs', {}), scan.get('dt_ms', 100))
            for address, expected in scan.get('expect', {}).items():
                actual = m.bit(address) if '.' in address or address.startswith('T') else m.word(address)
                if actual != expected:
                    raise AssertionError(f"{program['id']}/{scenario['name']} scan {i} {address}: {actual} != {expected}")
        results.append({'scenario': scenario['name'], 'scans': m.scans, 'passed': True})
    return results
