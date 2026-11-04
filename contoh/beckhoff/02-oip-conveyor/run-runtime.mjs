// Real-runtime harness using Open Industry Project's MIT-licensed loop and probe interfaces.
// Upstream notice: simulation/OIP-LICENSE. No vendor or GPL runtime binary is bundled.
// Operator opt-in is for an isolated local lab, never equipment.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
const [mode, oipArg, target, outArg] = process.argv.slice(2);
const option = n => {
    const i = process.argv.indexOf(n);
    if (i < 0) return null;
    const value = process.argv[i + 1];
    if (!value || value.startsWith('--')) throw Error(`${n} requires a value`);
    return value;
};
if (!['openplc', 'beckhoff'].includes(mode) || !oipArg || !target || !outArg || !process.argv.includes('--allow-lab-write'))
    throw Error('usage: node run-runtime.mjs openplc|beckhoff OIP_CHECKOUT LOOPBACK_URL|OWNED_UM_NETID OUTPUT --allow-lab-write [--credentials PRIVATE_JSON] [--only TEST_FILE]');
const oipRoot = resolve(oipArg), example = dirname(fileURLToPath(import.meta.url)), project = join(example, 'simulation'), out = resolve(outArg);
if (out.toLowerCase() === example.toLowerCase() || out.toLowerCase().startsWith((example + sep).toLowerCase()))
    throw Error('Keep runtime build bundles and logs outside this public example');
if (mode === 'openplc') {
    const u = new URL(target);
    if (u.protocol !== 'https:' || !['127.0.0.1', 'localhost'].includes(u.hostname) || u.port !== '8443')
        throw Error('Only an explicitly identified loopback HTTPS lab runtime on 8443 is allowed');
}
mkdirSync(out, { recursive: true });
const lib = n => import(pathToFileURL(join(oipRoot, 'scripts/lib', n)).href);
const { loadOurs, flattenTags, sleep } = await lib('conveyor-loop.mjs');
const { loadEditor, setOffline, UPLOAD_ENTRIES } = await lib('openplc-editor.mjs');
const { buildProgramZip, remoteDevice } = await lib('openplc-deploy.mjs');
const { RuntimeClient } = await lib('openplc-runtime.mjs');
class ProvisionedRuntimeClient extends RuntimeClient {
    request(method, path, options) {
        if (path === 'create-user')
            throw Error('Refusing account bootstrap; provision the dedicated lab runtime separately');
        return super.request(method, path, options);
    }
}
const { listenModbus } = await lib('modbus-tcp-listen.mjs');
const manifest = JSON.parse(readFileSync(join(project, 'project.json'), 'utf8'));
const scene = JSON.parse(readFileSync(join(project, 'scene.json'), 'utf8'));
const ours = await loadOurs({ test: '/src/core/project/projectTest.ts', probe: '/src/core/project/projectProbe.ts', runner: '/src/editor/project/projectTestRunner.ts' });
const { TestEvaluator, TraceRecorder, FaultInjector, faultActive, validateTestSpec } = ours.more.test;
const { ProbeSampler, cargoInZone } = ours.more.probe;
const inputs = ['StartPB', 'StopNC', 'EStopHealthy', 'PartSensor', 'CountReset', 'BeltRunning'];
const outputs = ['Horn', 'Motor', 'BatchLamp', 'RunReq', 'BatchCounter.CV'];
let server = null, client = null, ads = null, adsReady = false, io = null, exchange = null, stats = null, programIdentity = {};
const sha = s => createHash('sha256').update(s).digest('hex');
try {
    if (mode === 'openplc') {
        setOffline(true);
        const editor = await loadEditor(UPLOAD_ENTRIES);
        const config = { protocol: 'modbus-tcp-server', host: '127.0.0.1', port: 5026, points: [...inputs.map((n, i) => ({ tag: 'MAIN.' + n, area: 'discreteInput', address: i })), { tag: 'MAIN.Spawned', area: 'inputRegister', address: 0, type: 'DINT' }, { tag: 'MAIN.Delivered', area: 'inputRegister', address: 2, type: 'INT' }, ...outputs.slice(0, 4).map((n, i) => ({ tag: 'MAIN.' + n, area: 'coil', address: i })), { tag: 'MAIN.BatchCounter.CV', area: 'holdingRegister', address: 10, type: 'INT' }] };
        const checked = ours.validateExternalIo(config);
        if (!checked.ok)
            throw Error(JSON.stringify(checked.errors));
        const source = readFileSync(join(project, 'plc/MAIN.st'), 'utf8');
        const body = source.slice(source.indexOf('RunReq :='), source.lastIndexOf('END_PROGRAM')).trim();
        const declarations = config.points.map(p => { const name = p.tag === 'MAIN.BatchCounter.CV' ? 'CountValue' : p.tag.slice(5); const loc = ours.addressForModbusPoint(p.area, p.address, ours.registerWords(p.type)); return `    ${name} AT ${loc} : ${p.type ?? 'BOOL'};`; }).join('\n');
        const text = `PROGRAM MAIN\nVAR\n${declarations}\nEND_VAR\nVAR\n    PartPulse : BOOL;\n    LastPartSensor : BOOL;\n    StartDelay : TON;\n    BatchCounter : CTU;\nEND_VAR\n${body}\n(* Read-only process-image observation of the actual CTU; not part of control logic. *)\nCountValue := BatchCounter.CV;\nEND_PROGRAM\n` + readFileSync(join(project, 'plc/Pilot.st'), 'utf8');
        const built = buildProgramZip(ours, editor, { text, device: remoteDevice(ours, checked.io, '127.0.0.1', 20), locations: config.points.map(p => ours.addressForModbusPoint(p.area, p.address, ours.registerWords(p.type))), outDir: out });
        programIdentity = { source_sha256: sha(source), control_body_sha256: sha(body), located_export_sha256: sha(text), zip_sha256: sha(built.zip), observer: 'CountValue mirrors the real CTU CV; RunReq is located in output image; control statements unchanged' };
        const runtime = new ProvisionedRuntimeClient(target);
        const version = await runtime.waitReady();
        if (version !== 'v4.3.2')
            throw Error('Unexpected runtime version ' + version);
        const secretFile = option('--credentials');
        if (!secretFile || !existsSync(secretFile))
            throw Error('Supply an existing private lab credential JSON; this runner never bootstraps accounts');
        const credentials = JSON.parse(readFileSync(secretFile, 'utf8'));
        const login = await runtime.login(credentials.username, credentials.password);
        client = runtime;
        console.log(JSON.stringify({ runtime: version, lab_account_created: login.created }));
        await client.stop();
        await client.deploy(built.zip);
        console.log('REAL_OPENPLC_COMPILE_SUCCESS');
        io = new ours.ModbusServerIo(checked.io);
        server = await listenModbus(io, checked.io);
        await client.start();
        await client.waitStatus('RUNNING');
        exchange = async (tags) => { io.writeSimTags(tags); return io.plcTags(); };
        stats = () => io.stats;
    }
    else {
        const require = createRequire(join(oipRoot, 'apps/desktop/package.json'));
        const { AdsLink } = require('./adsIo.cjs');
        ads = new AdsLink();
        const netId = target;
        if (!netId)
            throw Error('Explicit owned usermode NetId required');
        const open = await ads.open({ netId, port: 851 });
        if (open.error || open.localNetId === netId)
            throw Error('Refusing unavailable or kernel-local target');
        const state = await ads.state();
        if (state.code || state.ads !== 5)
            throw Error('Owned PLC is not RUN: ' + JSON.stringify(state));
        const names = [...inputs, 'Spawned', 'Delivered', ...outputs].map(n => 'MAIN.' + n);
        const binding = await ads.bind(names.map(name => ({ name })));
        if (binding.error || binding.tags.some(t => t.code))
            throw Error('Native symbols did not bind: ' + JSON.stringify(binding));
        exchange = async (tags) => { const writes = Object.entries(tags).filter(([n]) => names.includes(n) && !outputs.some(x => 'MAIN.' + x === n)).map(([name, value]) => ({ name, value })); const r = await ads.exchange(writes, outputs.map(n => 'MAIN.' + n)); if (r.error || r.writes.some(x => x) || r.reads.some(x => x.code))
            throw Error('ADS exchange failed: ' + JSON.stringify(r)); return Object.fromEntries(outputs.map((n, i) => ['MAIN.' + n, r.reads[i].value])); };
        adsReady = true;
        stats = () => ({ native_ads: true });
        programIdentity = { native_boot_receipt: 'usermode-boot-transfer.json' };
    }
    const results = [];
    const only = option('--only');
    const specFiles = only ? manifest.tests.filter(n => n === only || n.split('/').at(-1) === only) : manifest.tests;
    if (!specFiles.length)
        throw Error('No canonical test matches --only');
    for (const name of specFiles) {
        const raw = JSON.parse(readFileSync(join(project, name), 'utf8'));
        const valid = validateTestSpec(raw);
        if (!valid.ok)
            throw Error(JSON.stringify(valid.errors));
        const spec = valid.spec;
        await exchange({ 'MAIN.StartPB': false, 'MAIN.StopNC': false, 'MAIN.EStopHealthy': false, 'MAIN.PartSensor': false, 'MAIN.CountReset': true, 'MAIN.BeltRunning': false, 'MAIN.Spawned': 0, 'MAIN.Delivered': 0 });
        await sleep(250);
        let reset = await exchange({ 'MAIN.CountReset': true });
        await sleep(50);
        reset = await exchange({ 'MAIN.CountReset': true });
        if (reset['MAIN.Motor'] !== false || reset['MAIN.BatchCounter.CV'] !== 0)
            throw Error('Actual runtime reset did not clear motor/count: ' + JSON.stringify(reset));
        const world = new ours.SimWorld(ours.Jolt, scene, { hz: 60 });
        world.setBehaviorDrivenTags(outputs.map(n => 'MAIN.' + n));
        const evaluator = new TestEvaluator(spec), probes = new ProbeSampler(spec.checks), trace = new TraceRecorder('all');
        const injector = new FaultInjector(ours.more.runner.resolveFaults(scene.parts, spec.faults ?? [], inputs.map(n => 'MAIN.' + n)));
        const jams = (spec.faults ?? []).filter(f => f.kind === 'jam').map(fault => ({ fault, body: null, caught: false }));
        const queue = [...(spec.inputs ?? [])].sort((a, b) => a.at - b.at), overlay = {}, cargo = [];
        let frame = world.frame(), worldTags = flattenTags(frame.tags), plcOut = {}, steps = 0, worstLagMs = 0;
        const total = Math.round(spec.duration * 60), start = performance.now();
        try {
            while (steps < total) {
                const now = performance.now();
                const due = Math.min(total, Math.floor((now - start) * .06));
                worstLagMs = Math.max(worstLagMs, now - start - steps / 60 * 1000);
                while (steps < due) {
                    const t = steps / 60;
                    while (queue.length && queue[0].at <= t + 1e-9) {
                        const x = queue.shift();
                        overlay[x.tag] = x.value;
                    }
                    const toPlc = injector.overrides('toPlc', t, { ...worldTags, ...overlay });
                    const toPart = injector.overrides('toPart', t, { ...plcOut, ...overlay });
                    plcOut = await exchange({ ...worldTags, ...overlay, ...toPlc });
                    for (const j of jams) {
                        const on = faultActive(j.fault, t);
                        if (on && !j.caught) {
                            for (const id of cargoInZone(j.fault.zone, frame)) {
                                if (world.pinBody(id, true)) {
                                    j.body = id;
                                    j.caught = true;
                                    break;
                                }
                            }
                        }
                        else if (!on && j.body !== null) {
                            world.pinBody(j.body, false);
                            j.body = null;
                        }
                    }
                    world.setBehaviorInputTags({ ...plcOut, ...overlay, ...toPart });
                    world.step();
                    frame = world.frame();
                    worldTags = flattenTags(frame.tags);
                    steps++;
                    const sample = { ...worldTags, ...plcOut, ...overlay, ...toPlc, ...probes.values(frame, probes.needsMarks ? world.cargoMarks() : undefined) };
                    evaluator.sample(frame.simTime, sample);
                    trace.sample(frame.simTime, sample);
                    if (steps % 6 === 0) {
                        const i = frame.partIds.indexOf('pt_11');
                        cargo.push({ t: frame.simTime, witness_x: i < 0 ? null : frame.positions[i * 3], live_bodies: frame.count });
                    }
                }
                await sleep(2);
            }
            if (jams.some(j => !j.caught))
                throw Error('Jam caught no body');
            const result = { file: name, ...evaluator.finalize(), worst_lag_ms: worstLagMs, facts: [...world.flowFactsOf({ finish: true }).facts], trace: trace.result(), cargo };
            results.push(result);
            writeFileSync(join(out, name.replace(/[^a-zA-Z0-9_.-]/g, '_') + '.result.json'), JSON.stringify(result, null, 2));
            console.log(JSON.stringify({ file: name, ok: result.ok, checks: result.checks.length, failed: result.checks.filter(c => !c.ok).map(c => c.detail), worst_lag_ms: worstLagMs }));
        }
        finally {
            world.dispose();
        }
    }
    const proof = { mode, programIdentity, clock: 'external PLC wall clock; physics paced at 60Hz; actual transport I/O; no in-process PLC evaluator', shared_spec_files: specFiles, io_fault_scope: 'commsLoss is the saved safe-off I/O injection, not transport disconnection', transport: stats(), ok: results.every(r => r.ok), tests: results.map(({ trace, cargo, ...r }) => r) };
    writeFileSync(join(out, 'proof.json'), JSON.stringify(proof, null, 2));
    process.exitCode = proof.ok ? 0 : 1;
}
finally {
    if (client)
        await client.stop().catch(() => { });
    await server?.close();
    try {
        if (adsReady) {
            const stopped = tags => tags['MAIN.Motor'] === false && tags['MAIN.Horn'] === false
                && tags['MAIN.RunReq'] === false && tags['MAIN.BatchCounter.CV'] === 0;
            let tags = await exchange({ 'MAIN.StartPB': false, 'MAIN.StopNC': false,
                'MAIN.EStopHealthy': false, 'MAIN.PartSensor': false,
                'MAIN.CountReset': true, 'MAIN.BeltRunning': false });
            const deadline = performance.now() + 1000;
            while (!stopped(tags) && performance.now() < deadline) {
                await sleep(10);
                tags = await exchange({});
            }
            if (!stopped(tags))
                throw Error('Native ADS safe-off postcondition failed: ' + JSON.stringify(tags));
            console.log(JSON.stringify({ native_ads_safe_off_verified: true, tags }));
        }
    }
    finally {
        await ads?.close();
    }
}
