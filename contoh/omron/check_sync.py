"""Verify canonical example files and optional HMI/Content Studio pins; no writes or network."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS = {'01-cp1h-x40dt-d','02-cp1h-xa40dt-d','03-cp1h-xa-analog',
       '04-analog-scaling','05-cp1h-xy-md02','06-cp2e-n30dt-d-xy-md02',
       '07-cp1h-x40dt-d-traffic-light'}
CPU = {'CP1H-X40DT-D': ('CP1H', 'X'), 'CP1H-XA40DT-D': ('CP1H', 'XA'), 'CP2E-N30DT-D': ('CP2E-N', 'N')}
MODELS = {'01-cp1h-x40dt-d': {'CP1H-X40DT-D'}, '02-cp1h-xa40dt-d': {'CP1H-XA40DT-D'},
          '03-cp1h-xa-analog': {'CP1H-XA40DT-D'}, '04-analog-scaling': {'CP1H-XA40DT-D'},
          '05-cp1h-xy-md02': {'CP1H-X40DT-D', 'CP1H-XA40DT-D'},
          '06-cp2e-n30dt-d-xy-md02': {'CP2E-N30DT-D'},
          '07-cp1h-x40dt-d-traffic-light': {'CP1H-X40DT-D'}}
REQUIRED = {'README.md', 'prompt.id.md', 'signals.csv', 'verification.json'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Path escapes canonical root: {relative}')
    return path


def verify_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['schema_version'] != 1 or manifest['id'] != path.parent.name:
        raise ValueError(f'Invalid manifest identity: {path}')
    if not manifest['files'] or not manifest['programs'] or not manifest['models']:
        raise ValueError('Manifest requires files, programs and exact models')
    artifacts = {value for artifact in manifest.get('artifacts', []) for value in artifact.values()}
    missing = (REQUIRED | set(manifest['programs']) | artifacts) - set(manifest['files'])
    if missing:
        raise ValueError(f'Required files are absent from hashed inventory: {sorted(missing)}')
    for name, expected in manifest['files'].items():
        source = child(path.parent, name)
        if digest(source) != expected:
            raise ValueError(f'Stale source hash: {manifest["id"]}/{name}')
    models = []
    for name in manifest['programs']:
        if name not in manifest['files']:
            raise ValueError(f'Unhashed program: {name}')
        program = json.loads(child(path.parent, name).read_text(encoding='utf-8'))
        if CPU.get(program['model']) != (program['device'], program['cpu']):
            raise ValueError(f'Model/CPU contract violated: {name}')
        models.append(program['model'])
    if set(models) != MODELS.get(manifest['id']) or sorted(models) != sorted(manifest['models']) \
            or len(set(models)) != len(models):
        raise ValueError('Program models do not match the fixed example contract')
    sources = manifest['source_refs']
    if not sources or len({s['id'] for s in sources}) != len(sources):
        raise ValueError('Missing or repeated source reference IDs')
    return manifest


def canonical(root: Path) -> dict[str, dict]:
    paths = list(root.glob('*/manifest.json'))
    manifests = {path.parent.name: verify_manifest(path) for path in paths}
    if set(manifests) != IDS:
        raise ValueError(f'Require all canonical examples, found: {sorted(manifests)}')
    return manifests


def verify_consumer(path: Path, root: Path, manifests: dict[str, dict]):
    consumer = json.loads(path.read_text(encoding='utf-8'))
    if consumer['schema_version'] != 1:
        raise ValueError('Unsupported consumer schema')
    if (path.parent / consumer['canonical_root']).resolve() != root.resolve():
        raise ValueError(f'Consumer points to a different canonical root: {path}')
    refs = consumer['examples']
    if len(refs) != len(IDS) or {ref['example_id'] for ref in refs} != IDS:
        raise ValueError('Consumer must pin each canonical example exactly once')
    for ref in refs:
        case = ref['example_id']
        manifest_path = child(root, ref['manifest'])
        if manifest_path != (root / case / 'manifest.json').resolve():
            raise ValueError(f'Manifest belongs to a different example: {case}')
        if digest(manifest_path) != ref['manifest_sha256']:
            raise ValueError(f'Stale consumer pin: {case}')
        actual_refs = {source['id'] for source in manifests[case]['source_refs']}
        if set(ref['source_refs']) != actual_refs:
            raise ValueError(f'Source references differ: {case}')


def verify_bindings(path: Path, root: Path, manifests: dict[str, dict]):
    document = json.loads(path.read_text(encoding='utf-8'))
    if document['schema_version'] != 1:
        raise ValueError('Unsupported bindings schema')
    expected = {(case, model) for case, m in manifests.items() for model in m['models']}
    seen, tags = set(), set()
    for row in document['bindings']:
        key = (row['example_id'], row['variant'])
        if key not in expected or key in seen:
            raise ValueError(f'Unknown/repeated example/model binding: {key}')
        seen.add(key)
        with (root / key[0] / 'signals.csv').open(encoding='utf-8', newline='') as handle:
            signals = {s['signal']: s for s in csv.DictReader(handle)}
        local_signals = set()
        if not row['signals']:
            raise ValueError(f'Empty HMI binding: {key}')
        for binding in row['signals']:
            if set(binding) != {'signal_id', 'hmi_tag', 'access'} or binding['access'] != 'read':
                raise ValueError(f'HMI binding must be read-only with no address fields: {key}')
            signal = binding['signal_id']
            if signal not in signals or signal in local_signals:
                raise ValueError(f'Missing/repeated canonical signal: {key}/{signal}')
            local_signals.add(signal)
            if signals[signal]['hmi_access'] not in {'read', 'read_write'}:
                raise ValueError(f'PLC signal is not readable by HMI: {key}/{signal}')
            if not binding['hmi_tag'] or binding['hmi_tag'] in tags:
                raise ValueError(f'Empty/repeated HMI tag: {binding["hmi_tag"]}')
            tags.add(binding['hmi_tag'])
    if seen != expected:
        raise ValueError('HMI bindings omit an example/model (including both CP1H Modbus variants)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical-root', type=Path, default=ROOT)
    parser.add_argument('--consumer', action='append', default=[], type=Path)
    parser.add_argument('--bindings', type=Path)
    args = parser.parse_args()
    try:
        manifests = canonical(args.canonical_root)
        for path in args.consumer:
            verify_consumer(path, args.canonical_root, manifests)
        if args.bindings:
            verify_bindings(args.bindings, args.canonical_root, manifests)
        print(json.dumps({'examples':len(manifests),'consumer_indices':len(args.consumer),
                          'hmi_bindings_checked':args.bindings is not None,'passed':True}))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
