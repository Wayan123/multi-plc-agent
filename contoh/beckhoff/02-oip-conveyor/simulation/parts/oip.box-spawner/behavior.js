// Spawner — a hopper that emits a product: boxes by default, or any cargo part in the project. Demonstrates ctx.spawn
// by product: the behavior runs its own rate timer and emits an item every 60/boxesPerMinute seconds via
// ctx.spawn({ part, params }); the host creates that part's body at the part's pose + the given local offset, as if
// placed. A Box takes this part's own size, colour and mass settings (the part's id is still oip.box-spawner). Cargo
// drops at the exact spawn point (no positional scatter), so downstream handling (picks, aligned queues) sees a
// repeatable pose. A pilot "Use" toggles the feed (a runtime latch, so it resets on stop/reload). Optionally gated by
// a conveyor interlock (conveyorId → ctx.conveyorRunning) or a PLC run tag.
//
// A mixed stream: `mixAttribute` names a product attribute and `mixValues` the values handed out one per item, in
// order (or at random with Random order). They start as the item's marks (ctx.spawn `marks`), the way a label printed
// upstream does, so a scanner reads them and a program routes by them. The value list and the colour list advance
// together: item n takes value n and colour n, so a code can be seen by its colour.
//
// Release says what reopening the gate does.
// - Steady interval: a hopper, PACED. What the author sets is the INTERVAL BETWEEN items, so that is what a hold
//   preserves. The countdown keeps running while the gate is shut but floors at zero: a hold neither costs a period
//   nor banks one. Freeze it instead and every release pays out the remainder of an interval the hopper spent
//   standing still (in the PLC demo: ~2.7 s of empty lane at the top of every row); let it run unfloored and a long
//   hold banks a burst that all lands in one tick.
// - On each enable: a magazine, COMMANDED. Every enable re-arms it and it drops at once, then paces while the gate
//   stays open. That is what makes a command pulse shorter than one period dispense exactly one item, every time.
//   Carry the countdown across the hold instead and only the first pulse ever dispenses.

// random-size range, full box dimensions (m)
const SIZE_MIN = [0.4, 0.3, 0.3]
const SIZE_MAX = [0.8, 0.5, 0.5]

let countdown = 0 // seconds until the next spawn
let started = false // steady interval: arm the first item on the first eligible tick
let armed = false // on each enable: drop on the first eligible tick after every enable, not a period later
let colorIndex = 0
let usedOff = false
let spawned = 0

// Publish what this feed has dispensed, every tick (a display not republished goes blank): the infeed half
// of the line's numbers, which a despawner's count is the other half of - the two differ by the work in
// progress. It counts REQUESTS: past the physics engine's 10,240-body table a spawn is skipped, uncounted
// by the host but still counted here.
function publish(ctx) {
  ctx.display('spawned', spawned)
  if (ctx.params.countTag) ctx.writeNumber(ctx.params.countTag, spawned)
}

// parse "#rrggbb" → [r, g, b] in 0..1
function hexRgb(hex) {
  const h = (hex || '').replace('#', '')
  if (h.length < 6) return [1, 1, 1]
  const v = (i) => { const n = parseInt(h.slice(i, i + 2), 16); return Number.isFinite(n) ? n / 255 : 1 }
  return [v(0), v(2), v(4)]
}
// the product settings param's JSON object (`{"size":"400x300x220"}`), or {} when it is empty or malformed
function settingsOf(json) {
  try {
    const o = JSON.parse(json || '{}')
    return o && typeof o === 'object' && !Array.isArray(o) ? o : {}
  } catch {
    return {}
  }
}
// parse a comma-separated hex list → [[r,g,b], …]
function palette(csv) {
  return (csv || '').split(',').map((c) => c.trim()).filter((c) => c.length >= 6).map(hexRgb)
}
// parse a comma-separated value list: numbers as numbers, true / false as booleans, anything else as text
function valueList(csv) {
  return (csv || '').split(',').map((c) => c.trim()).filter((c) => c !== '').map((c) => {
    if (c === 'true' || c === 'false') return c === 'true'
    const n = Number(c)
    return Number.isFinite(n) ? n : c
  })
}

definePart({
  interactive: true, // a pilot "Use" toggles the feed
  params: {
    boxesPerMinute: { type: 'number', unit: '/min', default: 45, min: 0, max: 1000, step: 1, label: 'Feed rate', desc: 'Items per minute. 0 halts the feed without pausing the part, so the timer restarts cleanly when you raise it again.' },
    fixedRate: { type: 'boolean', default: true, label: 'Fixed rate (off = ±50% jitter)', desc: 'On, items arrive on an exact metronome. Off, each gap is randomised between half and one-and-a-half times the nominal period, which is what an untidy real feed looks like downstream.' },
    product: { type: 'string', product: true, settings: 'productSettings', default: 'oip.box', label: 'Product', desc: 'The cargo part every item is, from the parts in the project: dropped as if placed, with its own size, colour, mass and product attributes. Its settings show below it. A Box takes the size, colour and mass under Box instead.' },
    productSettings: { type: 'string', hidden: true, default: '', label: 'Product settings', desc: 'Settings of the chosen product, as JSON. Edited under Product.' },
    boxColor: { type: 'color', default: '#ffffff', label: 'Box color', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Tint for every spawned box. Ignored once the cycle list below is non-empty.' },
    boxColors: { type: 'color', list: true, default: '', label: 'Colors (cycle)', desc: 'Colors handed out one per item, in order, overriding the colour of the product (or the Box color). Useful for telling sorted lanes apart at a glance. Leave empty to use the single colour.' },
    mixAttribute: { type: 'string', default: '', label: 'Vary attribute', desc: 'A product attribute each item starts with, from the values below: a label code, a destination. A scanner reads it, and a program routes by it. Empty for none.' },
    mixValues: { type: 'string', default: '', label: 'Values (cycle)', desc: 'The values handed out one per item, comma-separated, in order: "1, 2, 2, 3". Numbers stay numbers, true and false are booleans, anything else is text. They advance with the colour cycle, so item n takes value n and colour n.' },
    randomColors: { type: 'boolean', default: false, label: 'Random order', desc: 'Give each item a colour and a value drawn at random from the cycle lists instead of walking them in order.' },
    length: { type: 'number', default: 0.6, min: 0.1, step: 0.05, label: 'Box length (m)', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Extent along local X of each spawned box. Ignored while Random size is on.' },
    width: { type: 'number', default: 0.4, min: 0.1, step: 0.05, label: 'Box width (m)', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Extent along local Z of each spawned box. Ignored while Random size is on.' },
    height: { type: 'number', default: 0.4, min: 0.1, step: 0.05, label: 'Box height (m)', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Extent along local Y of each spawned box. Ignored while Random size is on.' },
    randomSize: { type: 'boolean', default: false, label: 'Random size', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Give each box a random size and IGNORE the three dimensions above. The random range is fixed by the part (0.4-0.8 long, 0.3-0.5 high, 0.3-0.5 wide), not derived from them.' },
    mass: { type: 'number', default: 10, min: 0.5, max: 100, step: 0.5, label: 'Mass (kg)', group: 'Box', visibleWhen: { param: 'product', is: 'oip.box' }, desc: 'Mass given to every spawned box, whatever its size.' },
    disable: { type: 'boolean', default: false, label: 'Paused', desc: 'Stop spawning entirely. Use (C, or E while walking) is a separate hand stop: it pauses and resumes the feed during a run without changing this setting, and is cleared when the run stops.' },
    release: {
      type: 'enum', default: 'interval', label: 'Release',
      options: [{ value: 'interval', label: 'Steady interval' }, { value: 'enable', label: 'On each enable' }],
      desc: 'What reopening the gate (Paused, Use, the conveyor interlock, the run tag) does. Steady interval: items come at the feed rate and the gap since the last one is always kept, so a short pulse may drop nothing. On each enable: an item drops the moment the gate opens, then more at the feed rate while it stays open, so each pulse of the run tag dispenses one.',
    },
    keepSpacing: { type: 'boolean', default: false, visibleWhen: { param: 'release', is: 'interval' }, label: 'Keep spacing while held', desc: 'Hold the interval while the feed is held instead of letting it run down, so boxes dropped onto a conveyor that stops with this spawner (give both the same run tag) stay one pitch apart however often the pair stops.' },
    conveyorId: { type: 'partRef', default: '', label: 'Pause when conveyor stopped', desc: 'Interlock: while the named conveyor is stopped, this spawner holds. Wire that conveyor to the PLC and the feed gates itself, with no tag of its own.' },
    runTag: { type: 'tag', dir: 'in', stType: 'BOOL', onlyWhenDriven: true, default: '', label: 'Run tag (spawn only while true)', group: 'Comms', desc: 'Gate the feed from the program. Note this only takes over once a program actually DRIVES the tag - until then the spawner keeps running, so a merely-declared tag is not a stopped feed.' },
    countTag: { type: 'tag', dir: 'out', stType: 'DINT', default: '', label: 'Spawned count tag', group: 'Comms', desc: 'Running total of boxes this spawner has dispensed. Subtract the despawner counts to get the work in progress.' },
  },
  step(ctx) {
    const p = ctx.params
    if (ctx.used()) usedOff = !usedOff
    // hold while a linked conveyor is stopped, or while a controller DRIVES the run tag de-energized
    // (ctx.tagDriven = output ownership; gating on the tag NAME alone would stop the spawner the moment one
    // was typed).
    const stopped = !ctx.conveyorRunning(p.conveyorId) || (ctx.tagDriven(p.runTag) && !ctx.readTag(p.runTag))
    const onEnable = p.release === 'enable'
    if (p.disable || usedOff || stopped || p.boxesPerMinute <= 0) {
      // on each enable: held off = disarmed, so the next open is a fresh command
      if (onEnable) armed = false
      // steady interval: the interval runs on, floored at zero (see the note at the top). Floored is what makes this
      // safe for an interlock that STUTTERS: at most one item is ever due when the gate reopens, never a burst.
      // Keep spacing: a feed onto a conveyor that stops WITH it (the same gate) must not run its interval down, or
      // the first item after a hold lands on the one the stopped belt is still holding under the drop
      else if (!p.keepSpacing) countdown = Math.max(0, countdown - ctx.dt)
      publish(ctx)
      return
    }
    const period = 60 / p.boxesPerMinute
    // the first item drops on the first eligible tick, not after a full period: once per run for a steady interval,
    // after every enable for on each enable
    if (onEnable) {
      if (!armed) { armed = true; countdown = 0 }
    } else if (!started) { started = true; countdown = 0 }
    countdown -= ctx.dt
    const pal = palette(p.boxColors)
    const values = p.mixAttribute ? valueList(p.mixValues) : []
    let n = 0
    while (countdown <= 0 && n < 8) {
      countdown += p.fixedRate ? period : Math.max(ctx.dt, period * (0.5 + ctx.rng()))
      n++
      // one step or one draw per item for both lists, so item n takes colour n and value n (a stream with no values
      // draws exactly as it did before values existed)
      let ci = 0
      let vi = 0
      if (pal.length > 0 || values.length > 0) {
        if (p.randomColors) {
          const r = ctx.rng()
          ci = Math.floor(r * pal.length)
          vi = Math.floor(r * values.length)
        } else {
          ci = colorIndex % Math.max(1, pal.length)
          vi = colorIndex % Math.max(1, values.length)
          colorIndex++
        }
      }
      const color = pal.length > 0 ? pal[ci] : p.product === 'oip.box' ? hexRgb(p.boxColor) : undefined
      const marks = values.length > 0 ? { [p.mixAttribute]: values[vi] } : undefined
      if (p.product === 'oip.box') {
        const rnd = (i) => SIZE_MIN[i] + ctx.rng() * (SIZE_MAX[i] - SIZE_MIN[i])
        const size = p.randomSize ? [rnd(0), rnd(1), rnd(2)] : [p.length, p.height, p.width]
        ctx.spawn({ part: 'oip.box', params: { length: size[0], height: size[1], width: size[2] }, color: color, mass: p.mass, offset: [0, -0.2, 0], ...(marks ? { marks } : {}) })
      } else if (p.product) {
        // any other product drops as itself, with its settings from the Inspector; a colour only from the cycle list
        ctx.spawn({ part: p.product, params: settingsOf(p.productSettings), ...(color ? { color } : {}), offset: [0, -0.2, 0], ...(marks ? { marks } : {}) })
      } else {
        continue // no product: the feed paces on and drops nothing
      }
      spawned++
    }
    publish(ctx)
  },
})
