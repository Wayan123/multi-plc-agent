// Despawner - a cargo sink, and the line's measuring point. Demonstrates ctx.zone / ctx.zoneAge /
// ctx.despawn: each tick it counts the cargo in its 'mouth' zone (all of it, or one product), adds up how long that
// cargo has existed, and removes it. From those two running sums it reports what this exit has done: the count, the rate, and
// the average cycle time (spawn to here). A PLC block tag pauses removal, so cargo accumulates at the gate.
//
// The numbers are published as displays, so they need no wiring to see, and can be shown on the part itself (the
// 'readout' plate, off by default); the tags are for a program or a project test that wants to act on them.

let total = 0
let ageSum = 0 // summed age of everything removed, sim seconds

definePart({
  params: {
    length: { type: 'number', default: 2, min: 0.2, max: 4, step: 0.1, label: 'Length (m)', desc: 'Local X extent of the volume that removes cargo. Cargo vanishes as soon as it is inside, so cover the full lane width or things slip past the edge.' },
    width: { type: 'number', default: 2, min: 0.2, max: 4, step: 0.1, label: 'Width (m)', desc: 'Local Z extent of the volume that removes cargo.' },
    height: { type: 'number', default: 1, min: 0.2, max: 4, step: 0.1, label: 'Height (m)', desc: 'Local Y extent of the volume that removes cargo.' },
    countOnly: { type: 'string', product: true, default: '', label: 'Count only', desc: 'Count just this product, so a tote carrying a case counts once. Everything in the mouth is still removed. (none) counts every body that goes in.' },
    showReadout: { type: 'boolean', default: false, label: 'Show readout', desc: 'Show the count, rate and cycle time on a plate above the volume. A viewing aid only: the displays and tags publish the same numbers either way.' },
    countTag: { type: 'tag', dir: 'out', stType: 'INT', default: '', label: 'Throughput count tag', group: 'Comms', desc: 'Running total of everything this despawner has removed, published for the program to read. It only ever climbs, so take differences over time to get a rate.' },
    rateTag: { type: 'tag', dir: 'out', stType: 'REAL', default: '', label: 'Throughput rate tag', unit: '/min', group: 'Comms', desc: 'Items removed per minute of simulated time, averaged over the whole run so far.' },
    cycleTag: { type: 'tag', dir: 'out', stType: 'REAL', default: '', label: 'Average cycle time tag', unit: 's', group: 'Comms', desc: 'Average time, in simulated seconds, from an item coming into being (spawned, or already in the scene when the run started) to its removal here. 0 until the first item arrives.' },
    blockTag: { type: 'tag', dir: 'in', stType: 'BOOL', default: '', label: 'Block tag (pause removal while true)', group: 'Comms', desc: 'While the program holds this true, nothing is removed and cargo backs up into the mouth - the way to model a downstream line that has stopped taking product.' },
  },
  step(ctx) {
    const p = ctx.params
    const blocked = p.blockTag ? ctx.readTag(p.blockTag) : false
    const n = ctx.zone('mouth')
    if (n > 0 && !blocked) {
      const only = p.countOnly ? { part: p.countOnly } : undefined
      total += only ? ctx.zone('mouth', only) : n
      ageSum += ctx.zoneAge('mouth', only)
      ctx.despawn('mouth')
    }
    const t = ctx.simTime + ctx.dt // sim time at the END of this tick, the one this tick's removals happened in
    const rate = (total / t) * 60
    const cycle = total > 0 ? ageSum / total : 0
    ctx.display('count', total)
    ctx.display('rate', rate)
    ctx.display('cycle', cycle)
    ctx.display('readout', total + ' done  ' + rate.toFixed(1) + '/min  ' + (total > 0 ? cycle.toFixed(1) + ' s' : '-'))
    if (p.countTag) ctx.writeNumber(p.countTag, total)
    if (p.rateTag) ctx.writeNumber(p.rateTag, rate)
    if (p.cycleTag) ctx.writeNumber(p.cycleTag, cycle)
  },
})
