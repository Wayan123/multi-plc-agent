"""Build authored LD through the actual multi-plc-agent stdio router, never hardware.

A native-exported empty CXT is preferred (--template). --draft-seed explicitly creates
an original text seed with CPU profiles observed in installed Omron StaticInfo.xml;
it is NOT a native-created or compiled project. It never converts a CP1E template.
Backend implementation stays external: no unlicensed code is bundled here.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]

# Original seed facts read from installed CX-Server StaticInfo.xml, not vendor files.
# These are draft construction profiles, not native compiler acceptance.
CPU_SEED_SETTINGS = {
    ('CP1H', 'X'): 'CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;UM:UM,0,43008,WORD,RW,1,RAM;',
    ('CP1H', 'XA'): 'CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;UM:UM,0,43008,WORD,RW,1,RAM;',
    ('CP2E-N', 'N'): 'CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;UM:UM,0,43008,WORD,RW,1,RAM;',
    ('CP1L', 'M'): 'UM:UM,0,22528,WORD,RW,1,RAM;CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;',
    ('CP1L', 'L'): 'UM:UM,0,12288,WORD,RW,1,RAM;CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;',
    ('CP1L', 'L10'): 'UM:UM,0,12288,WORD,RW,1,RAM;CLOCK:TRUE;GATE:FALSE;REMOTE:FALSE;',
    ('CJ2M', 'CPU31'): 'UM:UM,0,53248,WORD,RW,1,RAM;CLOCK:TRUE;GATE:TRUE;REMOTE:TRUE;EM:E,0,32768,WORD,RW,1,RAM;',
}


def cpu_identity(text: str) -> tuple[str, str]:
    configs = re.findall(r'Config:="([^"\r\n]+)";', text)
    if len(configs) != 1:
        raise ValueError('Require exactly one PLC configuration in the CXT')
    dev = re.search(r'(?:\[DEV\]|;)DEV:([^;]+);', configs[0])
    cpu = re.search(r';CPU:([^;]+);', configs[0])
    if not dev or not cpu:
        raise ValueError('CXT lacks explicit DEV and CPU identifiers')
    return dev[1], cpu[1]


def draft_seed(device: str, cpu: str, binary_timers: bool = False) -> str:
    settings = CPU_SEED_SETTINGS.get((device, cpu))
    if settings is None:
        raise ValueError('No evidenced draft CPU profile; require a native exported template')
    config = f'[DEV]DEV:{device};CPU:{cpu};{settings}'
    return f'''CXProgVer:="1.5";
WrittenByCXPVersion:="9.73";
FileType:=1;
Name:="OmronTeachingExample";
Core:=
BEGIN
 CDMPath:="";
END;
ResourceCount:=1;
Resource[0]:=
BEGIN
 Name:="ExampleResource";
 TCSettingBinary:={1 if binary_timers else 0};
 PLC:=
 BEGIN
  Name:="ExamplePLC";
  Config:="{config}";
 END;
 GlobalVariables:=
 BEGIN
  VariableList:=
  BEGIN_LIST_$#[1]
  END_LIST_$#[1];
  VariableCount:=0;
 END;
 Programs:=
 BEGIN
  Program[0]:=
  BEGIN
   Name:="Main";
   FileType:=2;
   LocalVariables:=
   BEGIN
    VariableList:=
    BEGIN_LIST_$#[2]
    END_LIST_$#[2];
    VariableCount:=0;
   END;
   TaskID:=256;
   OpStart:=1;
   Sections:=
   BEGIN
    SC:=2;
    Sec[0]:=
    BEGIN
     IEC1131Type:=11;
     CompileInline:=0;
     SecType:=0;
     SecName:="Section1";
     ProgramData:=
     BEGIN
      RC:=0;
     END;
    END;
    Sec[1]:=
    BEGIN
     IEC1131Type:=11;
     CompileInline:=0;
     SecType:=0;
     SecName:="END";
     ProgramData:=
     BEGIN
      RC:=1;
      R[0]:=
      BEGIN
       Com:="";
       Flags:="1,0";
       FBversion:="";
       SL:=
$?St$Bk?_#[3]
END(001)
$?St$Bk?_#[3]
       AtchCmts:=
       BEGIN
        CC:=0;
       END;
      END;
     END;
    END;
   END;
  END;
 END;
END;
'''


class Rpc:
    def __init__(self, config: Path):
        self.messages: queue.Queue = queue.Queue()
        self.errors = tempfile.TemporaryFile()
        self.proc = subprocess.Popen([sys.executable, '-m', 'multiplc', '--config', str(config)],
                                     cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.errors, text=True, encoding='utf-8')
        self.sequence = 0
        self.receipts: list[dict] = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                self.messages.put(json.loads(line))
        except Exception as error:
            self.messages.put(error)
        finally:
            self.messages.put(EOFError('Router stdout closed'))

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        self.proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.sequence,
                                         'method': method, 'params': params}) + '\n')
        self.proc.stdin.flush()
        while True:
            response = self.messages.get(timeout=120)
            if isinstance(response, Exception):
                raise response
            if response.get('id') == self.sequence:
                break
        self.receipts.append({'method': method, 'tool': params.get('name'), 'response': response})
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']

    def tool(self, tool_name: str, **arguments):
        result = self.request('tools/call', {'name': tool_name, 'arguments': arguments})
        texts = [c['text'] for c in result.get('content', []) if c.get('type') == 'text']
        payload = json.loads(texts[0]) if len(texts) == 1 else texts
        if result.get('isError'):
            raise RuntimeError(payload)
        return payload

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        self.errors.close()


def build(config_path: Path, program_path: Path, output: Path, template: Path | None,
          use_draft: bool, receipt: Path):
    program = json.loads(program_path.read_text(encoding='utf-8'))
    if output.is_symlink() or output.with_suffix('.cxp').is_symlink():
        raise ValueError('Output CXT/CXP must not be symlinks')
    output = output.resolve()
    if output.suffix.lower() != '.cxt' or output.exists() or output.with_suffix('.cxp').exists():
        raise ValueError('Output must be a NEW .cxt path, with neither .cxt nor .cxp already present')
    protected = {output, output.with_suffix('.cxp'), program_path.resolve(), config_path.resolve()}
    if template:
        protected.add(template.resolve())
    if receipt.is_symlink() or receipt.resolve() in protected:
        raise ValueError('Receipt must not alias the output, program, template or config')
    timer_counter_mode = program.get('timer_counter_mode', 'bcd')
    if timer_counter_mode not in {'bcd', 'binary'}:
        raise ValueError('Unknown timer/counter mode; require bcd or binary')
    if template:
        text = template.read_text(encoding='utf-8-sig')
    elif use_draft:
        text = draft_seed(program['device'], program['cpu'], timer_counter_mode == 'binary')
    else:
        raise ValueError('Supply --template or explicitly select --draft-seed (not native validation)')
    if cpu_identity(text) != (program['device'], program['cpu']):
        raise ValueError(f"CPU mismatch: {cpu_identity(text)} is not {(program['device'], program['cpu'])}")
    binary_timers = bool(re.search(r'^\s*TCSettingBinary:=1;\s*$', text, re.M))
    if binary_timers != (timer_counter_mode == 'binary'):
        raise ValueError('Template timer/counter mode differs from the authored program')
    if len(re.findall(r'^\s*Program\[\d+\]:=', text, re.M)) != 1:
        raise ValueError('Template must contain exactly one program; refusing to retain other control code')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    omron = [(key, value) for key, value in config['backends'].items()
             if value.get('vendor') == 'omron' and value.get('enabled', True)]
    if len(omron) != 1:
        raise ValueError('Config must identify exactly one enabled Omron backend')
    key, backend = omron[0]
    argv = list(backend.get('args', []))
    if '--project' not in argv or '--allow-write' not in argv:
        raise ValueError('Omron backend requires explicit --project and --allow-write')
    argv[argv.index('--project') + 1] = str(output.resolve())
    argv = [a for a in argv if a not in {'--auto-reload-cxp', '--no-auto-reload-cxp'}]
    argv += ['--no-auto-reload-cxp']
    backend = dict(backend, args=argv)
    config['backends'] = {key: backend}  # do not start unrelated PLC backends
    prefix = backend.get('prefix', 'omron_')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf-8', newline='\r\n')
    result = {'model': program['model'], 'cpu_profile': list(cpu_identity(text)),
              'seed': 'authored_draft' if use_draft else 'native_export',
              'mcp_write': 'failed', 'readback': False, 'native_compile': 'not_run',
              'hardware': 'not_run'}
    with tempfile.TemporaryDirectory(prefix='mpa-omron-') as directory:
        cfg = Path(directory) / 'config.json'
        cfg.write_text(json.dumps(config), encoding='utf-8')
        rpc = Rpc(cfg)
        try:
            rpc.request('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                      'clientInfo': {'name': 'omron-example-builder', 'version': '1'}})
            status = rpc.tool('list_plc_backends')
            if any(row['status'] != 'running' for row in status['backends']):
                raise RuntimeError(status)
            rpc.request('tools/list', {})
            summary = rpc.tool(prefix + 'list_sections')
            for section in summary:
                existing = rpc.tool(prefix + 'list_rungs', section=section['name'], mode='full')
                if any(any(line.strip() not in {'', 'END(001)'} for line in rung['instructions'])
                       for rung in existing['items']):
                    raise ValueError('Template is not empty; refusing to append another control program')
            for section in program['sections']:
                rpc.tool(prefix + 'add_section', section_name=section['name'], before_section='END')
                for index, rung in enumerate(section['rungs']):
                    rpc.tool(prefix + 'insert_rung', section=section['name'], index=index,
                             instructions=rung['instructions'], comment=rung['comment'])
            validation = rpc.tool(prefix + 'validate_project')
            if not validation.get('ok'):
                raise ValueError(validation)
            rpc.tool(prefix + 'commit_project', backup=True, reload_cxp=False)
            for section in program['sections']:
                loaded = rpc.tool(prefix + 'list_rungs', section=section['name'], mode='full')['items']
                if [r['instructions'] for r in loaded] != [r['instructions'] for r in section['rungs']]:
                    raise AssertionError('MCP instruction readback differs from authored JSON')
            if cpu_identity(output.read_text(encoding='utf-8-sig')) != (program['device'], program['cpu']):
                raise AssertionError('CPU changed during backend write')
            result.update(mcp_write='passed', readback=True, rung_count=sum(len(s['rungs']) for s in program['sections']))
        except Exception as error:
            result['error'] = str(error)
            raise
        finally:
            rpc.close()
            # Local receipts may contain machine paths; public manifests only copy status summaries.
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({'result': result, 'mcp_receipts': rpc.receipts}, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--program', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    seed = parser.add_mutually_exclusive_group(required=True)
    seed.add_argument('--template', type=Path)
    seed.add_argument('--draft-seed', action='store_true')
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.config, args.program, args.output, args.template, args.draft_seed, args.receipt), indent=2))
    except (ValueError, OSError, RuntimeError, AssertionError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
