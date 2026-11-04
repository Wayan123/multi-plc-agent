// Push Button — an illuminated, depressable pushbutton. It reacts to a user "use"/click (ctx.used()),
// depresses the cap into the housing (ctx.setSubPose — a −Z travel, the button front is +Z), lights the cap's
// emissive face (ctx.lamps), and drives a PLC tag. Two modes: momentary (default) holds pressed for a 0.3 s
// pulse of SIM time (not wall-clock); maintained latches on each use. The written output is 'pressed XOR
// normallyClosed' (a normally-closed contact reads true at rest).
//
// The LAMP is its own circuit, not a side effect of the press. On real 22 mm gear the light block is a
// separate module stacked behind the operator with its own terminals and often its own voltage, wired
// independently of the contact blocks - making the lamp echo the press is something you do deliberately by
// strapping a contact to it, not what the device does by itself. So the source is DECLARED ('lampSource'),
// never inferred from whether a tag happens to be bound: follows-press (kept as the default, so a freshly
// placed button still visibly lights), a PLC tag (the acknowledge wiring a real panel uses), always-on (a
// power-on indicator), or unlit (no light block fitted). Inferring it from the binding would make echo the
// fallback, the wiring you would least often choose, and could not express a plain unlit button or a lamp lit by
// anything other than this button's own press.
//
// An EMERGENCY STOP is this device with a different operator, not a different part: 'emergencyStop' swaps the
// cap for a red mushroom head in a yellow shroud on a yellow lid, and FIXES the two things an E-stop may not be set to -
// it latches when struck and stays in until released, and its contact is normally closed, so a broken wire stops the line the same way a press does. The Inspector hides the settings
// it overrides (visibleWhen) rather than showing switches that do nothing.
//
// The release is a TWIST, and is drawn as one: the next Use turns the struck head clockwise (the way the arrow on
// its face points) while it is still held in, then the head springs out and turns back. The contact recloses at
// the spring-out, not at the Use - the line cannot see an E-stop released before the head is.
//
// Built in code (geometry()): the housing, mounting tabs, bezel, legend plate and slotted bolt heads on the part
// root, and the cap on the `cap` link - which the press moves (ctx.setSubPose) - as a LAMP submesh
// (MeshPart.lamp), tinted by the `buttonColor` param and lit via ctx.lamps. The shapes are kept in NATIVE units:
// geometry() scales them uniformly to
// PUSH_BUTTON_HEIGHT tall (x/z centred on the whole model, base at y 0), so the face label, the mount and the
// demo's back-plate offset are all that scale's numbers.
//
// This is the part's source. `npm run build-parts` writes behavior.ts (this script as the app ships it, with the
// _shared/ modules it imports joined in and `manifest` / `rig()` left out) and rig.json (the manifest, with the
// rig compiled from rig()).

// The station box's height, which sets the size of everything: 0.09 m makes the box ~90 mm square, the round
// cap ~28 mm across (a 22 mm operator's) and the E-stop head 40 mm, the sizes of real gear.
const PUSH_BUTTON_HEIGHT = 0.09
const RED_LIT = [1, 0.15, 0.12] // pre-refresh seed for the lit colour (the param takes over on first refresh)
const BUTTON_COLOR_DEFAULT = '#b3140f' // the classic matte red cap

const PRESS_DEPTH = 0.01 // m, cap travel into the housing
// A mushroom head's travel. A real 40 mm head moves a few millimetres; this is more, because a press has to be SEEN
// going in and coming out from station distance - at 8 mm on a 0.1 m head it read as never retracting at all.
const ESTOP_PRESS_DEPTH = 0.007 // m
const ESTOP_MOVE_S = 0.1 // s the head takes to go in or come out: quick, but a motion rather than a one-tick jump
// Timed like a hand on a spring-loaded head, and tuned by eye in both places it plays: the running sim, where the
// head must come out promptly after a Use (0.8 s read as sluggish), and a stopped scene's Use, where a twist has
// to last long enough to be seen at all (0.35 s, linear, is over before anyone notices it turn).
const TWIST_S = 0.5 // s of sim time the release twist takes, the head still held in
const SPRING_S = 0.2 // s for the released head to turn back to rest
const TWIST_RAD = 0.75 // how far the head turns to release, ~43 degrees
// The cap link's origin is the part's, at the back plate's foot, while the head turns about its OWN axis, which
// stands this high above it - so a turn is paired with the offset that keeps that axis where it is.
const HEAD_AXIS_Y = PUSH_BUTTON_HEIGHT / 2
const PULSE_S = 0.3 // momentary hold window, seconds of sim time

let pressed = false
let pulseTicks = 0 // remaining momentary window, in whole sim ticks (exact — no float drift)
let twistTicks = 0 // remaining release twist, in sim ticks; while it runs the head is turning and still in
let springTicks = 0 // remaining spring-back after the head is out
let headDepth = 0 // the E-stop head's drawn depth, eased toward in/out; the CONTACT follows pressed at once

definePart({
  interactive: true, // makes the part show a "Use" prompt + routes the click to ctx.used()
  lamps: ['cap'],
  params: {
    emergencyStop: { type: 'boolean', default: false, label: 'Emergency stop (mushroom head)', desc: 'A red mushroom head on a yellow station that latches when struck and stays in until it is used again, like twisting a real E-stop out. Its contact is always normally closed, so the tag reads true while the stop is released and false while it is in.' },
    text: { type: 'string', default: 'STOP', label: 'Face label', group: 'Face', desc: 'The legend plate above the button, the way a lamacoid is mounted. Keep it short enough to read at station distance.' },
    buttonColor: { type: 'color', default: BUTTON_COLOR_DEFAULT, visibleWhen: { param: 'emergencyStop', is: false }, label: 'Button color', group: 'Face', desc: 'Tint of the cap, and of the lamp when it lights.' },
    momentary: { type: 'boolean', default: true, visibleWhen: { param: 'emergencyStop', is: false }, label: 'Momentary (else maintained latch)', desc: 'On, each press is a fixed 0.3 s pulse of sim time, like a spring-return start button - so a paused sim holds the pulse rather than letting it expire. Off, the button latches on one press and releases on the next, like a maintained selector.' },
    startPressed: { type: 'boolean', default: false, visibleWhen: { param: 'emergencyStop', is: false }, label: 'Starts pressed (maintained only)', group: 'Start state', desc: 'A maintained button starts latched in, so a run begins with it pressed. A momentary button springs back on its own, so it ignores this.' },
    startStruck: { type: 'boolean', default: false, visibleWhen: { param: 'emergencyStop', is: true }, label: 'Starts struck', group: 'Start state', desc: 'The emergency stop starts latched in, so a run begins with the stop open - the way to check that a line refuses to start until it is twisted out.' },
    normallyClosed: { type: 'boolean', default: false, visibleWhen: { param: 'emergencyStop', is: false }, label: 'Normally closed (inverts the signal)', desc: 'Invert the output, so the tag reads true while the button is NOT pressed - the safety convention for a stop button, where a broken wire reads the same as a press.' },
    lampSource: {
      type: 'enum', default: 'press', label: 'Lamp source',
      desc: 'What lights the cap. Follows press echoes this button, the way a contact strapped to the light block would. PLC tag hands the lamp to the program through Lamp tag below - the acknowledge wiring a real panel uses. Always on is a power-on indicator. Unlit is a button with no light block fitted.',
      options: [
        { value: 'press', label: 'Follows press' },
        { value: 'tag', label: 'PLC tag' },
        { value: 'on', label: 'Always on' },
        { value: 'off', label: 'Unlit' },
      ],
    },
    tag: { type: 'tag', dir: 'out', stType: 'BOOL', default: '', label: 'Button output tag', group: 'Comms', desc: 'Where the button publishes its press for the program to read. Whether true means pressed or at-rest is set by Normally closed above.' },
    lampTag: { type: 'tag', dir: 'in', stType: 'BOOL', default: '', label: 'Lamp tag (PLC lights the cap)', group: 'Comms', desc: 'Which PLC bool lights the cap, so the program can acknowledge a press rather than just echo it. Read only when Lamp source above is set to PLC tag; left unbound there, the lamp stays dark like an unwired light block.' },
  },
  // The button, drawn. Shapes are in NATIVE units (the face is the x-y plane, +z out of the panel) and mapped to
  // metres by a uniform scale to PUSH_BUTTON_HEIGHT tall, x/z centred on the whole model, base at y 0.
  geometry(g, p) {
    var S = PUSH_BUTTON_HEIGHT / 0.4248, CZ = 0.14225, Y0 = -0.2124
    // native → metres: the fitHeight normalisation (uniform scale, x/z centred on the whole model, base at y 0)
    var fit = function (parts) { return g.transform(g.merge.apply(g, parts), { scale: S, translate: [0, -Y0 * S, -CZ * S] }) }
    var estop = !!p.emergencyStop
    var gray = [], dark = [], light = [], bolt = [], yellow = []
    // housing: the body, and the slightly larger front frame the face sits in. An emergency stop station is the
    // same box with a YELLOW lid on the grey base (the usual emergency-stop station shape), so the frame changes colour
    gray.push(g.bevelBox([0.4028, 0.4028, 0.1759], [0, 0, 0.08795], 0.0036))
    ;(estop ? yellow : gray).push(g.bevelBox([0.4248, 0.4248, 0.0477], [0, 0, 0.19975], 0.0035))
    // the mounting tabs behind it: round-cornered plates, two round holes each
    var arc = function (cy, a0) {
      var pts = []
      for (var k = 0; k <= 2; k++) { var a = a0 + (k * Math.PI) / 4; pts.push([0.2323 + 0.0088 * Math.cos(a), cy + 0.0088 * Math.sin(a)]) }
      return pts
    }
    var tab = [[0.1832, -0.1898]].concat(arc(-0.181, -Math.PI / 2), arc(0.181, 0), [[0.1832, 0.1898]])
    var hole = function (cy) {
      var pts = []
      for (var k = 0; k < 8; k++) pts.push([0.2246 + 0.0114 * Math.cos((k * Math.PI) / 4), cy + 0.0114 * Math.sin((k * Math.PI) / 4)])
      return pts
    }
    for (var sx = -1; sx <= 1; sx += 2) {
      var mx = function (pts) { return pts.map(function (q) { return [sx * q[0], q[1]] }) }
      gray.push(g.extrude(mx(tab), -0.0073, 0, { holes: [mx(hole(0.1632)), mx(hole(-0.1632))] }))
    }
    // the dark bezel round the cap: a lip, a step, a raised collar and the socket the cap sits in
    dark.push(g.lathe([[0.0985, 0.2236], [0.0985, 0.2344], [0.0822, 0.2344], [0.0822, 0.2494], [0.072, 0.2494], [0.072, 0.1537], [0, 0.1537]], { axis: 'z' }))
    // the light legend plate across the upper face, arched round the bezel. An E-stop has none: its yellow lid is
    // the background, and the caption stands on the lid itself
    var arch = [[-0.1052, -0.0008], [-0.0939, 0.0404], [-0.0744, 0.075], [-0.0413, 0.0973], [0, 0.1051], [0.0413, 0.0973], [0.0744, 0.075], [0.0939, 0.0404], [0.1052, -0.0008]]
    if (!estop) light.push(g.extrude([[-0.1391, -0.0008], [-0.1391, 0.1627], [0.1391, 0.1627], [0.1391, -0.0008]].concat(arch.slice().reverse()), 0.2236, 0.2285))
    // the four slotted bolt heads: an octagon split by a screwdriver slot, each turned its own way
    var heads = [[0.1756, 0.175, 26.2], [-0.1756, 0.175, -17.2], [-0.1756, -0.175, 65.3], [0.1756, -0.175, -39.2]]
    for (var bi = 0; bi < heads.length; bi++) {
      var hc = heads[bi], th = (hc[2] * Math.PI) / 180, R = 0.0177, GAP = 0.00074
      var oct = []
      for (var ok = 0; ok < 8; ok++) oct.push([R * Math.cos((ok * Math.PI) / 4), R * Math.sin((ok * Math.PI) / 4)])
      for (var half = -1; half <= 1; half += 2) {
        // the octagon clipped to one side of the slot (local x = ±GAP), then turned and placed
        var clip = []
        for (var ci = 0; ci < 8; ci++) {
          var P = oct[ci], Q = oct[(ci + 1) % 8], pin = half * P[0] >= GAP, qin = half * Q[0] >= GAP
          if (pin) clip.push(P)
          if (pin !== qin) { var tt = (half * GAP - P[0]) / (Q[0] - P[0]); clip.push([half * GAP, P[1] + tt * (Q[1] - P[1])]) }
        }
        var placed = clip.map(function (q) { return [hc[0] + q[0] * Math.cos(th) - q[1] * Math.sin(th), hc[1] + q[0] * Math.sin(th) + q[1] * Math.cos(th)] })
        bolt.push(g.extrude(placed, 0.2171, 0.2301))
      }
    }
    // the cap: a short round plunger with a chamfered edge, on the link the press moves
    var cap, arrow = []
    if (!estop) {
      cap = [g.lathe([[0.0673, 0.2032], [0.0673, 0.2883], [0.0638, 0.2918], [0, 0.2918]], { axis: 'z' })]
    } else {
      // An E-stop operator: a 40 mm turn-to-release head on its station (radius 0.0944 in these native units), a
      // yellow SHROUD standing out of the bezel (static - it is the operator's body), a red NECK out of the shroud,
      // and a flat-faced head about twice the neck across with a rounded front edge. The head's back stands 0.05
      // off the shroud (the red neck showing between them, as on the real thing), so its 0.033 of travel -
      // ESTOP_PRESS_DEPTH, in these native units - never meets it. Turned smooth and in more segments than the
      // plunger, because a disc facing the camera shows every facet.
      yellow.push(g.lathe([[0.075, 0.2236], [0.075, 0.272], [0.071, 0.28], [0.052, 0.28], [0.052, 0.2236]], { axis: 'z', segments: 40 }))
      cap = [
        g.lathe([[0.05, 0.2032], [0.05, 0.33], [0, 0.33]], { axis: 'z', segments: 32 }),
        g.lathe([[0.05, 0.33], [0.085, 0.33], [0.0928, 0.336], [0.0944, 0.346], [0.0944, 0.376], [0.0913, 0.385], [0.0842, 0.39], [0, 0.39]], { axis: 'z', segments: 48 }),
      ]
      // the TWIST-TO-RELEASE arrow printed on the face: a band round most of a circle, open at the top, and an
      // arrowhead at its upper-left end pointing the way the head turns out (clockwise, seen from the front). It is
      // WHITE rather than embossed red: on a plain round head it is the only thing that shows the head turning
      var AR = 0.0456, AW = 0.0055, A0 = (70 * Math.PI) / 180, A1 = (-250 * Math.PI) / 180, band = [], n = 28
      for (var ai = 0; ai <= n; ai++) { var aa = A0 + ((A1 - A0) * ai) / n; band.push([(AR + AW) * Math.cos(aa), (AR + AW) * Math.sin(aa)]) }
      for (var aj = n; aj >= 0; aj--) { var ab = A0 + ((A1 - A0) * aj) / n; band.push([(AR - AW) * Math.cos(ab), (AR - AW) * Math.sin(ab)]) }
      arrow.push(g.extrude(band, 0.3895, 0.396))
      var tipA = A1 - (22 * Math.PI) / 180, HW = AW * 2.6
      arrow.push(g.extrude([
        [(AR + HW) * Math.cos(A1), (AR + HW) * Math.sin(A1)],
        [AR * Math.cos(tipA), AR * Math.sin(tipA)],
        [(AR - HW) * Math.cos(A1), (AR - HW) * Math.sin(A1)],
      ], 0.3895, 0.396))
    }

    var both = { doubleSided: true }
    return [
      Object.assign({ desc: fit(gray), material: 'gray' }, both),
      Object.assign({ desc: fit(dark), material: 'dark' }, both),
      Object.assign({ desc: fit(light), material: 'light' }, both),
      Object.assign({ desc: fit(bolt), material: 'bolt' }, both),
    ].concat(estop ? [Object.assign({ desc: fit(yellow), material: 'yellow' }, both), { desc: fit(arrow), link: 'cap', material: 'light' }] : []).concat([
      // an E-stop head is red whatever Button color says, so it carries no colorParam
      estop
        ? { desc: fit(cap), link: 'cap', material: 'cap', lamps: [{ name: 'cap', emissive: RED_LIT }] }
        : { desc: fit(cap), link: 'cap', material: 'cap', lamps: [{ name: 'cap', emissive: RED_LIT }], colorParam: 'buttonColor' },
    ])
  },
  // The authored starting state, set before the first step: a maintained button may start latched in, an E-stop
  // struck. A press changes it from there; only these params say where a run (or a stopped Use) starts.
  init(ctx) {
    const estop = !!ctx.params.emergencyStop
    pressed = estop ? !!ctx.params.startStruck : !ctx.params.momentary && !!ctx.params.startPressed
    headDepth = estop && pressed ? -ESTOP_PRESS_DEPTH : 0
  },
  step(ctx) {
    const estop = ctx.params.emergencyStop
    let turn = 0 // the head's twist, radians about its own axis (clockwise seen from the front is negative)
    if (estop) {
      pulseTicks = 0
      const twistN = Math.ceil(TWIST_S / ctx.dt), springN = Math.ceil(SPRING_S / ctx.dt)
      if (ctx.used() && twistTicks === 0) {
        if (!pressed) { pressed = true; springTicks = 0 } // struck: in, and latched
        else twistTicks = twistN // twisted to release: the head turns first, still in
      }
      if (twistTicks > 0) {
        twistTicks--
        const u = 1 - twistTicks / twistN
        turn = -TWIST_RAD * u * (2 - u) // eased out: it answers the Use at once and slows into the release
        if (twistTicks === 0) { pressed = false; springTicks = springN } // turned far enough: out it springs
      } else if (springTicks > 0) {
        springTicks--
        const v = springTicks / springN
        turn = -TWIST_RAD * v * v // eased out: the spring is quick off the mark and settles into rest
      }
    } else if (ctx.params.momentary) {
      if (ctx.used()) pulseTicks = Math.ceil(PULSE_S / ctx.dt)
      pressed = pulseTicks > 0
      if (pulseTicks > 0) pulseTicks--
      twistTicks = springTicks = 0
    } else {
      if (ctx.used()) pressed = !pressed
      pulseTicks = twistTicks = springTicks = 0
    }
    // The lamp runs off its DECLARED source (see the header) - the press is only one of the four wirings,
    // not the fallback. A 'tag' source with no Lamp tag named reads dark, like a light block nobody wired.
    // The cap depress follows pressed under every source.
    const src = ctx.params.lampSource
    const litByTag = !!ctx.params.lampTag && ctx.readTag(ctx.params.lampTag)
    // a PLC that drives this tag is watching a real button (Watch only): show it as that button reads
    const shown = ctx.params.tag && ctx.tagDriven(ctx.params.tag) ? ctx.readTag(ctx.params.tag) !== (estop || ctx.params.normallyClosed) : pressed
    ctx.lamps.cap = src === 'on' ? true : src === 'off' ? false : src === 'tag' ? litByTag : shown
    let depth = shown ? -PRESS_DEPTH : 0
    if (estop) {
      const target = shown ? -ESTOP_PRESS_DEPTH : 0
      const stepM = (ESTOP_PRESS_DEPTH * ctx.dt) / ESTOP_MOVE_S
      headDepth = Math.abs(target - headDepth) <= stepM ? target : headDepth + Math.sign(target - headDepth) * stepM
      depth = headDepth
    } else headDepth = 0
    ctx.setSubPose('cap', turn === 0
      ? { position: [0, 0, depth] }
      : { position: [HEAD_AXIS_Y * Math.sin(turn), HEAD_AXIS_Y * (1 - Math.cos(turn)), depth], rotation: [0, 0, turn] })
    if (ctx.params.tag) ctx.writeTag(ctx.params.tag, pressed !== (estop || ctx.params.normallyClosed))
  },
})
