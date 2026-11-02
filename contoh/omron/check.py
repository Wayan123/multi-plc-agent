"""Run canonical LD scenarios and verify recorded native artifacts. Does not run a PLC."""
import json
from pathlib import Path
from check_sync import ROOT, canonical, child, digest
from mcp_build import cpu_identity
from offline import run_scenarios


def check(root: Path = ROOT) -> dict:
    manifests = canonical(root)
    results = []
    for case, manifest in sorted(manifests.items()):
        artifacts = manifest['artifacts']
        if len(artifacts) != len(manifest['programs']) or {a['program'] for a in artifacts} != set(manifest['programs']):
            raise ValueError('Native evidence must cover every program exactly once')
        for artifact in manifest['artifacts']:
            program_path = child(root / case, artifact['program'])
            program = json.loads(program_path.read_text(encoding='utf-8'))
            evidence = json.loads(child(root / case, artifact['verification']).read_text(encoding='utf-8'))
            if evidence['program_sha256'] != digest(program_path):
                raise ValueError(f'Native evidence is stale for {case}/{artifact["program"]}')
            if (evidence['model'], evidence['device'], evidence['cpu']) != (program['model'], program['device'], program['cpu']):
                raise ValueError('Native evidence CPU/model differs from the source')
            if evidence['mcp_write'] != 'passed' or evidence['mcp_readback'] != 'identical':
                raise ValueError('No successful MCP write/readback evidence')
            if evidence['native_compile'] != 'passed' or evidence['native_errors'] != 0:
                raise ValueError('Recorded native compiler did not pass')
            for kind in ('cxt', 'cxp'):
                if evidence.get(kind + '_sha256') != digest(child(root / case, artifact[kind])):
                    raise ValueError(f'Native {kind.upper()} differs from compiled evidence: {case}')
            cxt = child(root / case, artifact['cxt']).read_text(encoding='utf-8-sig')
            if cpu_identity(cxt) != (program['device'], program['cpu']):
                raise ValueError('Native CXT has a different CPU')
            if not set(artifact.values()) <= set(manifest['files']):
                raise ValueError('Artifact is absent from hashed manifest inventory')
            scenarios = run_scenarios(program)
            results.append({'example':case,'model':program['model'],'scenarios_passed':len(scenarios),
                            'scan_count':sum(s['scans'] for s in scenarios),
                            'recorded_native_errors':evidence['native_errors'],
                            'recorded_native_warnings':evidence['native_warnings'],
                            'hardware':'not_run','cx_simulator':'not_run'})
    return {'examples':len(manifests),'programs':len(results),
            'scenarios_passed':sum(r['scenarios_passed'] for r in results),'results':results,
            'note':'Native results are recorded editor evidence, not a new compiler invocation.'}


if __name__ == '__main__':
    try:
        print(json.dumps(check(), ensure_ascii=False, indent=2))
    except (ValueError, AssertionError, OSError, KeyError) as error:
        raise SystemExit(str(error))
