#!/usr/bin/env node
// Recreate and test this example through the actual OIP desktop MCP. No PLC online operations.
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const here = dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const option = (name) => args.includes(name) ? args[args.indexOf(name) + 1] : undefined
const createName = option('--create')
const project = option('--project')
if ((!createName && !project) || (createName && project)) {
  throw new Error('Use --create NEW_NAME or --project EXISTING_PROJECT_PATH; optionally --url URL --out DIRECTORY --negative')
}
const endpoint = new URL(option('--url') ?? 'http://127.0.0.1:5189/mcp')
if (endpoint.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(endpoint.hostname)) {
  throw new Error('This lab runner accepts only a local loopback HTTP MCP endpoint')
}
const out = resolve(option('--out') ?? join(here, `proof-${Date.now()}`))
await mkdir(out, { recursive: true })
let sequence = 0
async function rpc(method, params = {}) {
  const id = ++sequence
  const request = { jsonrpc: '2.0', id, method, params }
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(180000),
  })
  const body = await response.json()
  await writeFile(join(out, `${String(id).padStart(3, '0')}-${method.replaceAll('/', '-')}.json`), JSON.stringify({ request, response: body }, null, 2) + '\n')
  if (!response.ok || body.error) throw new Error(`${method}: ${JSON.stringify(body)}`)
  return body.result
}
async function call(name, arguments_ = {}) {
  const result = await rpc('tools/call', { name, arguments: arguments_ })
  const text = result.content.filter((c) => c.type === 'text').map((c) => c.text).join('\n')
  if (result.isError) throw new Error(`${name}: ${text}`)
  try { return JSON.parse(text) } catch { return text }
}
const json = async (path) => JSON.parse(await readFile(path, 'utf8'))
const recipe = await json(join(here, 'recipe.json'))
const manifest = await json(join(here, 'simulation/project.json'))
const source = (await Promise.all(manifest.program.map((p) => readFile(join(here, 'simulation', p), 'utf8')))).join('\n')
const templates = await Promise.all(manifest.tests.map((p) => json(join(here, 'simulation', p))))

async function recreate(name) {
  const created = await call('new_project', { name })
  const ids = {}
  for (const part of recipe.parts) {
    const { key, ...definition } = part
    const placed = await call('add_part', definition)
    ids[key] = placed.id
  }
  await call('update_part', { id: ids.spawner, params: { conveyorId: ids.belt } })
  for (const mount of recipe.mounts) {
    await call('snap_part', { id: ids[mount.part], onto: ids[mount.onto], near: mount.near })
  }
  const compiled = await call('set_program', { source })
  if (compiled.problems.some((p) => p.severity === 'error')) throw new Error(JSON.stringify(compiled.problems))
  const translation = new Map(Object.entries(recipe.templateIds).map(([key, id]) => [id, ids[key]]))
  const remap = (value) => {
    if (typeof value === 'string') return translation.get(value) ?? value
    if (Array.isArray(value)) return value.map(remap)
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, remap(v)]))
    return value
  }
  const specs = templates.map(remap)
  for (const spec of specs) await call('save_test', { spec })
  const problems = await call('get_problems')
  if (problems.errors || problems.warnings) throw new Error(`Project diagnostics: ${JSON.stringify(problems)}`)
  return { project: created.path, specs, ids }
}

const identity = await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'multi-plc-conveyor-proof', version: '1' } })
if (identity.serverInfo?.name !== 'open-industry-project') throw new Error('The endpoint is not the expected OIP server')
const discovery = await rpc('tools/list')
await call('get_guide')
let target
if (createName) target = await recreate(createName)
else {
  const opened = await call('open_project', { project })
  target = { project: opened.path, specs: templates }
}
const actualProgram = await call('get_program')
const actualScene = await call('get_scene')
const positive = await call('run_test', { trace: recipe.traceTags })
if (!positive.tests?.length || positive.ok !== true) throw new Error(`Acceptance did not pass: ${JSON.stringify(positive)}`)
const proof = {
  engine: 'OIP internal IEC and Jolt physics; not vendor runtime execution',
  server: identity.serverInfo,
  expected_oip_source: recipe.oipSource,
  source_revision_verified_by_this_client: false,
  tools_discovered: discovery.tools.length,
  project: target.project,
  program_sha256: createHash('sha256').update(actualProgram.source).digest('hex'),
  scene: actualScene,
  positive,
  negative: null,
}
if (args.includes('--negative')) {
  try {
    const copy = await recreate(`conveyor-negative-${Date.now()}`)
    const marker = ' AND EStopHealthy'
    if (source.split(marker).length !== 2) throw new Error('Expected exactly one E-stop permissive to mutate')
    const compiled = await call('set_program', { source: source.replace(marker, '') })
    if (compiled.problems.some((p) => p.severity === 'error')) throw new Error('The mutant must compile before testing')
    const spec = copy.specs.find((s) => s.name === '03-estop-recovery')
    if (!spec) throw new Error('The E-stop acceptance specification is absent')
    const negative = await call('run_test', { spec, trace: recipe.traceTags })
    if (negative.ok !== false || negative.error || !negative.checks?.some((c) => !c.ok && typeof c.failedAt === 'number')) {
      throw new Error(`The unsafe mutant was not rejected by a behavioral assertion: ${JSON.stringify(negative)}`)
    }
    proof.negative = { mutation: 'remove EStopHealthy from the seal-in permissive, in a separate project', result: negative }
  } finally {
    await call('open_project', { project: target.project })
  }
}
await writeFile(join(out, 'proof.json'), JSON.stringify(proof, null, 2) + '\n')
console.log(JSON.stringify({ engine: proof.engine, project: target.project, positive: positive.summary, negative_rejected: proof.negative?.result.ok === false, proof: join(out, 'proof.json') }, null, 2))
