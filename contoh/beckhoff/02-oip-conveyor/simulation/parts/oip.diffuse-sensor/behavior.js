// Photo Eye - a photoelectric presence sensor, diffuse or retro-reflective (the package id still says diffuse:
// stored scenes and rooms name it). Demonstrates sensing (ctx.sense), an emissive detection LED (ctx.lamps), and
// a PLC presence tag. The lens emits a beam along local +Z; the host casts it against cargo each tick and
// hands back the nearest hit. Both modes come down to that one cast: the first target in the beam before Max range.
//
// The housing is the shared photoeye (_shared/sensorPhotoeye.js), drawn by geometry().
//
// This is the part's source. `npm run build-parts` writes behavior.ts (this script as the app ships it, with the
// _shared/ modules it imports joined in and `manifest` / `rig()` left out) and rig.json (the manifest, with the
// rig compiled from rig()).

// ---- from examples/parts/_shared/sensorOutlines.js ----
// a rounded-corner rectangle, for windows and panels
function rrect(x0, y0, x1, y1, r) {
  const pts = []
  for (const [cx, cy, a0] of [[x1 - r, y0 + r, -Math.PI / 2], [x1 - r, y1 - r, 0], [x0 + r, y1 - r, Math.PI / 2], [x0 + r, y0 + r, Math.PI]])
    for (let k = 0; k <= 3; k++) { const a = a0 + (k * Math.PI) / 6; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]) }
  return pts
}

// a 16-sided circle, for mounting holes
function circle(cy, cz, r) {
  const pts = []
  for (let k = 0; k < 16; k++) { const a = (k * Math.PI) / 8; pts.push([cy + r * Math.cos(a), cz + r * Math.sin(a)]) }
  return pts
}

// ---- from examples/parts/_shared/sensorPhotoeye.js ----
const PHOTOEYE = {
  halfX: 0.0225, // 45 mm wide
  back: -0.036,
  front: 0.037, // the lens face: SENSOR_EMIT_Z, the beam origin and the guard contact
  bodyY0: 0.036, // the housing's underside; the M8 plug hangs below it
  bodyY1: 0.15,
  height: 0.16, // SENSOR_HEIGHT: the pot on the top cap reaches it
  emitY: 0.1, // SENSOR_EMIT_Y, inside the lens window
  led: [0, 0.124, 0.034], // the detection LED, on the face above the window
}

// The photoeye's MOUNTING BRACKET, which bolts it to a conveyor's SIDE FRAME - with a guard or without one, and
// touching neither anywhere but where it is bolted.
//
// The guard mount seats the eye with its origin 20 mm below the deck and its lens face 20 mm out from the bed edge,
// over the frame's L-rail (examples/parts/belt-conveyor's rail template; the roller bed's is the same): a WALL whose
// face is 10 mm out from the bed edge, running down from 5 mm under the deck, a 5 mm top LIP reaching out to 30 mm at
// deck height, and - where the bed has one - a GUARD sheet standing on the rail 10..15 mm out (GUARD_THICKNESS).
// Measured outward from the bed edge (u, which is FRONT + 0.02 - z in part-local z), the bracket is:
//   - a SIDE PLATE on the housing's +X flank, bolted through its two holes. Its profile steps round the steel: from
//     the housing down to 3 mm over the lip it stays out past u 23 mm (clear of a guard's 15), past the lip it stays
//     out past the lip's 30 mm tip, and only well under the lip - below the axle heads studding the wall just under
//     it - does it step in to the wall;
//   - a TOE there, square across the beam, flat on the wall face (u 10..13 mm) and bolted to it.
// A floor stand bolts to the toe's face the same way (src/editor/demoScenes.ts EYE_STAND_*), so its numbers are
// transcribed there.
//
// A STOPGAP, and a deliberate copy: the rail's numbers above belong to the conveyor, and are repeated here only
// because a host cannot yet say what steel it offers. Retire this (and EYE_STAND_*) when conveyors publish their
// rail profile on their snap surface and the SDK's bracket helper draws from the seat a mount stores.
const PHOTOEYE_BRACKET = {
  gauge: 0.003, // the sheet
  width: 0.052, // the toe across the beam, from the plate: clear of the lens window by 7.5 mm
  wall: 0.01, // u of the wall's face, which the toe's back lies on
  clearGuard: 0.023, // u the plate keeps out past above the lip (the guard's face 0.015, the lens face 0.02)
  clearLip: 0.033, // ...and past at the lip (its tip 0.03)
  lipY: [0.015, 0.02], // the lip's underside and top, in part-local y (the deck is at 0.02)
  toeTop: -0.025, // where the plate steps in to the toe: clear below the axle heads (part-local y)
  bottom: -0.07, // the toe's foot
  bolts: [-0.06, -0.035], // its two bolts into the wall
  back: 0.046, // u of the plate's back edge, behind the housing's holes (0.031)
}

// The bracket's pieces. Each takes u2z, which maps u (outward from the bed edge) to part-local z on the side the
// piece is drawn on, so a reflector across the bed can draw the same bracket mirrored.

// a hex bolt head along `axis`
function photoeyeHex(g, axis, center) {
  return g.lathe([[0, 0], [0.0065, 0], [0.0065, 0.004], [0, 0.004]], { axis, center, segments: 6, smooth: false })
}

// the side plate in the x plane [x0, x0 + gauge], from yTop down; its face nearest the bed at uIn above the lip
function photoeyeSidePlate(g, x0, yTop, uIn, u2z) {
  const B = PHOTOEYE_BRACKET
  return g.extrude([
    [yTop, uIn], [yTop, B.back], [B.bottom, B.back], [B.bottom, B.wall + B.gauge], [B.toeTop, B.wall + B.gauge], [B.toeTop, B.clearLip],
    [B.lipY[1] + 0.003, B.clearLip], [B.lipY[1] + 0.003, uIn],
  ].map(([y, u]) => [y, u2z(u)]), x0, x0 + B.gauge, { axis: 'x' })
}

// the toe across [x0, x0 + width], its back on the wall
function photoeyeToe(g, x0, u2z) {
  const B = PHOTOEYE_BRACKET
  return g.box([B.width, B.toeTop - B.bottom, B.gauge], [x0 + B.width / 2, (B.bottom + B.toeTop) / 2, (u2z(B.wall) + u2z(B.wall + B.gauge)) / 2])
}

// the toe's two bolts into the wall, at x
function photoeyeToeBolts(g, x, u2z) {
  const B = PHOTOEYE_BRACKET
  return B.bolts.map((y) => g.lathe([[0, 0], [0.0065, 0], [0.0065, 0.004], [0, 0.004]], {
    axis: 'z', center: [x, y, Math.min(u2z(B.wall + B.gauge), u2z(B.wall + B.gauge + 0.004))], segments: 6, smooth: false,
  }))
}

// The housing and its bracket, as geometry() returns them. Materials: body, black (plug, cap), lens (window),
// pot, steel (the bracket).
function photoeyeHousing(g) {
  const X = PHOTOEYE.halfX, BACK = PHOTOEYE.back, FRONT = PHOTOEYE.front, Y0 = PHOTOEYE.bodyY0, Y1 = PHOTOEYE.bodyY1
  const CH = 0.024 // the chamfer across the lower back corner
  // the housing: its side profile (y, z) run across the width, with two mounting holes through it
  const body = g.extrude(
    [[Y0, BACK + CH], [Y0, FRONT], [Y1, FRONT], [Y1, BACK], [Y0 + CH, BACK]],
    -X, X,
    { axis: 'x', bevel: 0.0015, holes: [circle(Y0 + 0.012, FRONT - 0.011, 0.0042), circle(Y1 - 0.012, FRONT - 0.011, 0.0042)] },
  )
  // the lens window on the face, the beam height inside it
  const lens = g.extrude(rrect(-0.017, 0.062, 0.017, 0.114, 0.004), FRONT, FRONT + 0.0008, { bevel: 0.0003 })
  // the top cap, stopping short of the face, and the sensitivity pot in it
  const cap = g.bevelBox([2 * X, 0.005, FRONT - 0.004 - BACK], [0, Y1 + 0.0025, (BACK + FRONT - 0.004) / 2], 0.001, ['y-'])
  const pot = g.lathe([[0, 0], [0.0055, 0], [0.0055, 0.0038], [0.0047, 0.0045], [0, 0.0045]], { axis: 'y', center: [0, Y1 + 0.005, -0.012], segments: 20 })
  const slot = g.box([0.008, 0.0008, 0.0012], [0, Y1 + 0.0096, -0.012])
  // the M8 plug under the housing: a turned body and a hex coupling nut
  const PZ = (BACK + CH + FRONT) / 2
  const plug = g.lathe([[0, 0], [0.0048, 0], [0.0052, 0.0005], [0.0052, 0.009], [0.0056, 0.009], [0.0056, 0.019], [0.0068, 0.022], [0.0068, Y0], [0, Y0]], { axis: 'y', center: [0, 0, PZ], segments: 20 })
  const nut = g.lathe([[0, 0.009], [0.0072, 0.009], [0.0072, 0.018], [0, 0.018]], { axis: 'y', center: [0, 0, PZ], segments: 6, smooth: false })
  // the bracket (PHOTOEYE_BRACKET): a side plate profiled round the rail's guard and lip, a toe bolted to its wall,
  // and a hex bolt head through each of the housing's holes
  const BT = PHOTOEYE_BRACKET.gauge, BW = PHOTOEYE_BRACKET.width
  const U2Z = (u) => FRONT + 0.02 - u // this side: z falls as u grows
  const HZ = FRONT - 0.011 // the housing's holes
  const bracket = g.merge(
    photoeyeSidePlate(g, X, Y1 - 0.002, PHOTOEYE_BRACKET.clearGuard, U2Z), photoeyeToe(g, X, U2Z), ...photoeyeToeBolts(g, X + BW * 0.62, U2Z),
    photoeyeHex(g, 'x', [X + BT, Y0 + 0.012, HZ]), photoeyeHex(g, 'x', [X + BT, Y1 - 0.012, HZ]),
  )
  const both = { doubleSided: true }
  return [
    Object.assign({ desc: body, material: 'body' }, both),
    Object.assign({ desc: lens, material: 'lens' }, both),
    Object.assign({ desc: g.merge(cap, slot, plug, nut), material: 'black' }, both),
    Object.assign({ desc: pot, material: 'pot' }, both),
    Object.assign({ desc: bracket, material: 'steel' }, both),
  ]
}

definePart({
  lamps: ['led'],
  params: {
    maxRange: { type: 'number', default: 2, min: 0.1, max: 10, step: 0.05, label: 'Max range (m)', desc: 'How far down the beam a target still counts as present. The beam is cast along local +Z, so aim the sensor by rotating it; snapping it onto a conveyor guard fits this range across the lane for you.' },
    mode: {
      type: 'enum', default: 'diffuse', label: 'Sensing mode',
      desc: 'How the eye is installed. Diffuse: the target itself reflects the light back to the eye, so nothing stands opposite it. Retro-reflective: the eye looks at a reflector on the far side of the lane and a target breaking that beam is detected; the reflector is drawn at Max range, so snapping the eye onto a conveyor guard puts it on the far guard. In the sim both detect the same way: a target in the beam before Max range.',
      options: [
        { value: 'diffuse', label: 'Diffuse' },
        { value: 'retro', label: 'Retro-reflective' },
      ],
    },
    showBeam: { type: 'boolean', default: true, label: 'Show beam', desc: 'Draw the beam line in the viewport. A viewing aid only - hiding it does not change what the sensor detects.' },
    normallyClosed: { type: 'boolean', default: false, label: 'Normally closed (inverts the signal)', desc: 'Invert the output, so the tag reads true when NOTHING is detected. The beam colour still follows the real detection, not the inverted signal.' },
    mark: { type: 'string', suggest: 'marks', default: '', label: 'Only marked targets', desc: 'Count a target only if a machine upstream left this mark on it (wrapped, or a label a labeller wrote). Empty: anything in the beam counts. This is how a program checks a product, not just its presence - a load that was never wrapped reads as clear.' },
    tag: { type: 'tag', dir: 'out', stType: 'BOOL', default: '', label: 'Presence tag', group: 'Comms', desc: 'Where the photoeye publishes presence for the program to read. Whether true means blocked or clear is set by Normally closed above.' },
  },
  // The housing, drawn: a body with a chamfered lower back and two mounting holes, the lens window on the face,
  // a top cap with a sensitivity pot, and an M8 plug underneath. Part-local metres, front (+Z) = the beam.
  geometry(g, p) {
    const out = photoeyeHousing(g)
    // RETRO-REFLECTOR at the beam's far end, the eye's mirror image across the bed. A guard mount fits maxRange to
    // the bed's width plus the lens's 20 mm stand-off at BOTH edges, so the reflector's face lands 20 mm out from the
    // far bed edge, outside that guard as the eye is outside its own, and its bracket is the eye's, mirrored: the same
    // side plate round that rail's guard and lip, the same toe on its wall. Its own submeshes, so the housing's still
    // pool across every copy whatever their ranges.
    if (p.mode === 'retro') {
      const BT = PHOTOEYE_BRACKET.gauge, BW = PHOTOEYE_BRACKET.width
      const F = PHOTOEYE.front + (typeof p.maxRange === 'number' && p.maxRange > 0 ? p.maxRange : 2) // the face, at far u 0.02
      const FU2Z = (u) => F - 0.02 + u // far side: z grows with u
      const E = PHOTOEYE.emitY, RR = 0.025, RT = 0.008 // the beam height, the disc's radius and thickness
      const disc = g.lathe([[0, 0], [RR - 0.002, 0], [RR, 0.002], [RR, RT], [0, RT]], { axis: 'z', center: [0, E, F], segments: 24 })
      const rim = g.lathe([[RR, 0.001], [RR + 0.003, 0.001], [RR + 0.003, RT + 0.001], [RR, RT + 0.001]], { axis: 'z', center: [0, E, F], segments: 24 })
      // the plate behind the disc, and the side plate it is bent from at its +X edge
      const PX0 = -0.032, PX1 = 0.058, PH = 0.032, UP = 0.02 + RT // u of the plate's face
      const plate = g.box([PX1 - PX0, 2 * PH, BT], [(PX0 + PX1) / 2, E, FU2Z(UP + BT / 2)])
      const rbracket = g.merge(
        rim, plate, photoeyeSidePlate(g, PX1 - BT, E + PH, UP, FU2Z), photoeyeToe(g, PX1 - BW, FU2Z), ...photoeyeToeBolts(g, PX1 - BW * 0.62, FU2Z),
        photoeyeHex(g, 'z', [0, E, FU2Z(UP + BT)]),
      )
      const both = { doubleSided: true }
      out.push(Object.assign({ desc: disc, material: 'reflector' }, both))
      out.push(Object.assign({ desc: rbracket, material: 'steel' }, both))
    }
    return out
  },
  step(ctx) {
    // the host casts the beam out to the maxRange param (its rangeParam); the gate below keeps that explicit
    const s = ctx.sense('lens')
    const want = ctx.params.mark
    const present = s.hit && s.distance <= ctx.params.maxRange && (!want || (!!s.marks && !!s.marks[want]))
    // a PLC that drives this tag is watching a real eye (Watch only): the LED shows what that eye reports
    if (ctx.params.tag && ctx.tagDriven(ctx.params.tag)) {
      ctx.lamps.led = ctx.readTag(ctx.params.tag) !== !!ctx.params.normallyClosed
      return
    }
    ctx.lamps.led = present // raw presence, not the NC-inverted output
    let out = present
    if (ctx.params.normallyClosed) out = !out // NC: de-energized (no cargo) reads true
    if (ctx.params.tag) ctx.writeTag(ctx.params.tag, out)
  },
})
