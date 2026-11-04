// Belt Conveyor — a powered belt conveyor authored as procedural geometry + behavior in one script.
// Demonstrates geometry(g, p): the belt cross-section is lofted along a bent multi-segment path. step(ctx)
// conveys cargo along the flow axis at the configured speed (negative reverses; a PLC run tag start/stops it).
//
// geometry.kind 'drawn': the deck + side-guard cross-section is lofted along the `segments` belt path; the same
// description feeds render + collision, reflowing on a param change (never per tick).
//
// This is the part's source. `npm run build-parts` writes behavior.ts (this script as the app ships it, with the
// _shared/ modules it imports joined in and `manifest` left out) and rig.json (the manifest).

// ---- from examples/parts/_shared/conveyorUnits.js ----
/** metres per second in one foot per minute */
const FPM_MS = 0.00508

/** `{ group }` to spread into a param, or nothing when there is no group */
const paramGroup = (group) => (group ? { group } : {})

/** Spread into the part's own m/s `speed` and `speedTag` params: shown only while the PLC speaks metres per second. */
const METRIC_ONLY = { visibleWhen: { param: 'fpmUnits', is: false } }

/** Params to stand BEFORE the part's own `speed`: the unit switch, and the speed in the other unit. */
function speedUnitParams(speedMs) {
  return {
    fpmUnits: { type: 'boolean', default: true, whenAbsent: false, imperialUnits: true, label: 'PLC speed in FPM', desc: 'The unit the PLC commands this conveyor in. On: feet per minute. Off: metres per second. The speed tag is a REAL either way, so switching changes what its value means and never how the program declares it. Set by the scene Units (Scene Properties), which switch every conveyor together, so the Inspector does not show it. A conveyor saved before this switch existed is in metres per second.' },
    speedFpm: { type: 'number', default: Math.round(speedMs / FPM_MS), min: -600, max: 600, step: 1, unit: 'FPM', label: 'Speed', visibleWhen: { param: 'fpmUnits', is: true }, desc: 'Surface speed in feet per minute. Negative runs it backwards. A program can command this through the FPM speed tag below.' },
  }
}

/** The param to stand right AFTER the part's own `speedTag`: the same setpoint, in FPM. */
function speedFpmTagParam(group) {
  return {
    speedFpmTag: { type: 'tag', dir: 'in', stType: 'REAL', setpointFor: 'speedFpm', default: '', label: 'Speed tag', ...paramGroup(group), visibleWhen: { param: 'fpmUnits', is: true }, desc: 'The program commands surface speed here in feet per minute, replacing the Speed field above, which then shows the live value read-only. Once BOUND this takes over even if no program writes it, so an unwritten tag holds the conveyor at 0.' },
  }
}

/** In step(): the Inspector readout of whichever speed field is in use. `v` is the effective m/s. */
function reportSpeed(ctx, fpm, v) {
  if (fpm) ctx.report('speedFpm', Math.round(v / FPM_MS)); else ctx.report('speed', v)
}

// ---- from examples/parts/_shared/conveyorDrive.js ----
/** Params to stand right AFTER the part's own `speed`: the drive's ramp, in seconds from stopped to rated. */
function driveRampParams(accelTime, decelTime) {
  return {
    accelTime: { type: 'number', unit: 's', default: accelTime, min: 0, max: 30, step: 0.1, label: 'Accel time', desc: 'How long the drive takes to bring the conveyor from stopped up to its rated speed (the speed that reads 30, under Comms > Feedback), like the acceleration time set on a VFD. A smaller change takes proportionally less. 0 starts instantly.' },
    decelTime: { type: 'number', unit: 's', default: decelTime, min: 0, max: 30, step: 0.1, label: 'Decel time', desc: 'How long the drive takes to bring the conveyor from rated speed down to a stop. Cargo keeps travelling while it does, so a box stopped at a photo-eye ends up past it. 0 stops instantly.' },
  }
}

/** Params to stand after the part's `runningTag`: the velocity feedback, the pulse and the encoder, in a
 *  `Feedback` section under `group`. */
function driveFeedbackParams(speedMs, group) {
  const fpm = Math.round(speedMs / FPM_MS)
  const g = paramGroup(group ? `${group}/Feedback` : 'Feedback')
  return {
    speedAt30: { type: 'number', default: speedMs, min: 0.01, max: 10, step: 0.01, label: 'Speed that reads 30 (m/s)', ...g, visibleWhen: { param: 'fpmUnits', is: false }, desc: 'The surface speed this conveyor reaches when its drive turns at 30. It scales the velocity tag: running at exactly this speed reads 30.' },
    speedAt30Fpm: { type: 'number', default: fpm, min: 1, max: 2000, step: 1, label: 'Speed that reads 30 (FPM)', ...g, visibleWhen: { param: 'fpmUnits', is: true }, desc: 'The surface speed, in feet per minute, this conveyor reaches when its drive turns at 30. It scales the velocity tag: running at exactly this speed reads 30.' },
    velocityTag: { type: 'tag', dir: 'out', stType: 'REAL', default: '', label: 'Velocity tag (30 at the speed above)', ...g, desc: 'Drive feedback the program reads: the effective speed as a share of the speed at 30 revolutions, times 30. Stopped reads 0, and a run tag holding the conveyor still counts as stopped.' },
    inchesPerPulse: { type: 'number', default: 1, min: 0.05, max: 100, step: 0.05, label: 'Travel per pulse (in)', ...g, desc: 'How far the surface travels between pulses on the pulse tag. A pulse cannot be finer than one simulation step, so a fast conveyor at a fine pitch needs a higher project simHz.' },
    pulseTag: { type: 'tag', dir: 'out', stType: 'BOOL', default: '', label: 'Pulse tag (one per pitch)', ...g, desc: 'An encoder for the program to count: TRUE for one simulation step each time the surface has travelled the inches above, in either direction, and FALSE otherwise.' },
    encoderTag: { type: 'tag', dir: 'out', stType: 'REAL', default: '', label: 'Encoder tag (travel)', unit: 'm', ...g, desc: 'Odometer of surface travel in metres, integrated on sim time: it climbs while the conveyor runs forward and counts back while it reverses. Latch it when a photo-eye sees a box, then act once it has advanced a known distance - the standard way to track product without a sensor at every station.' },
  }
}

/** What a conveyor remembers between steps for its ramp, its pulse and its encoder. Make one at the top level. */
function conveyorDrive() {
  return {
    pulseTravel: 0, // surface travel since the last pulse (in)
    odo: 0, // encoder odometer: surface travel (m), signed with the direction of travel
    driven: 0, // what the drive is actually doing (m/s): the command, through the accel/decel ramp
    rampStarted: false, // past the first step, from which every change of command ramps
  }
}

/** In step(): the unit the conveyor is set up in and the commanded speed, `{ fpm, setpointTag, commanded }`.
 *  `commanded` is always m/s, so everything after this call is m/s. */
function commandedSpeed(ctx) {
  const fpm = ctx.params.fpmUnits === true
  const setpointTag = fpm ? ctx.params.speedFpmTag : ctx.params.speedTag
  const unit = fpm ? FPM_MS : 1
  const commanded = (setpointTag ? ctx.readNumber(setpointTag) : fpm ? ctx.params.speedFpm : ctx.params.speed) * unit
  return { fpm, setpointTag, commanded }
}

/** In step(), after commandedSpeed(): the speed the surface actually runs at (m/s), `target` (the command, gates
 *  applied) through the drive's ramp. Away from 0 it accelerates at rated / accelTime; toward 0 it decelerates at
 *  rated / decelTime; a reversal runs down to 0 before it turns round.
 *  THE FIRST STEP: a conveyor whose speed or run gate a program owns starts from rest, because the program is
 *  starting the line; one running on its authored speed is already running at it, since nothing started it. */
function rampedSpeed(ctx, drive, cmd, target) {
  // rates are rated speed over the accel / decel time
  const rated = cmd.fpm ? ctx.params.speedAt30Fpm * FPM_MS : ctx.params.speedAt30
  let want = target
  if (!drive.rampStarted) {
    drive.rampStarted = true
    // no program commands this conveyor: its authored speed is a belt that is running, not one being started
    if (!(cmd.setpointTag || (ctx.params.runTag && ctx.tagDriven(ctx.params.runTag)))) drive.driven = want
  }
  if (want * drive.driven < 0) { if (ctx.params.decelTime > 0) want = 0; else drive.driven = 0 } // reversing: stop first
  const rampTime = Math.abs(want) > Math.abs(drive.driven) ? ctx.params.accelTime : ctx.params.decelTime
  drive.driven = rampTime > 0 && rated > 0 ? ctx.approach(drive.driven, want, (rated / rampTime) * ctx.dt) : want
  return drive.driven
}

/** In step(): the velocity feedback, the pulse and the encoder, from the effective speed `v` (m/s). */
function publishDrive(ctx, drive, cmd, v) {
  // the velocity as a share of the speed at 30
  const at30 = cmd.fpm ? ctx.params.speedAt30Fpm * FPM_MS : ctx.params.speedAt30
  if (ctx.params.velocityTag) ctx.writeNumber(ctx.params.velocityTag, at30 > 0 ? (v / at30) * 30 : 0)
  // the encoder pulse
  const pitch = ctx.params.inchesPerPulse > 0 ? ctx.params.inchesPerPulse : 1
  drive.pulseTravel += (Math.abs(v) * ctx.dt) / 0.0254
  const pulse = drive.pulseTravel >= pitch - 1e-9 // (a hair of tolerance: twelve twelfths of an inch do not sum to exactly one)
  if (pulse) drive.pulseTravel = Math.max(0, drive.pulseTravel - pitch * Math.max(1, Math.floor(drive.pulseTravel / pitch + 1e-9)))
  if (ctx.params.pulseTag) ctx.writeTag(ctx.params.pulseTag, pulse)
  drive.odo += v * ctx.dt
  if (ctx.params.encoderTag) ctx.writeNumber(ctx.params.encoderTag, drive.odo)
}

// ---- from examples/parts/_shared/conveyorFriction.js ----
/** The `friction` param, with the surface's default grip against a carton. */
function frictionParam(carton) {
  return {
    friction: { type: 'number', default: carton, min: 0, step: 0.01, label: 'Friction', desc: 'Grip between the running surface and a standard carton, the figure a belt datasheet quotes. A smooth PVC belt is about 0.4, a rough-top incline belt about 0.9 and a low-friction plastic modular belt about 0.2, made for product to slide while it accumulates. Bare steel rollers are about 0.4. Other cargo grips by its own friction against the same surface.' },
  }
}

// ---- from examples/parts/_shared/guardHolePanel.js ----
// A side guard's sensor-beam hole panel, drawn once for every function conveyor whose guard is a formed sheet
// (belt, spur, spur roller, curved, curved roller). The rig roller draws the same plate from core (guardHoles.ts
// guardHolePanelDescription), without the top return, which is its own link there.
//
// Where a beam crosses a guard, the host works out the hole (core/guardHoles.ts: the beams are facts of the scene,
// not of a frame) and hands it to the conveyor as a `guardHoles` row [x, y, side]; its geometry() splits the guard
// sheet around a HOLE_PANEL gap there and fills it with this panel.
//
// The panel is in the guard's own frame, the one its sheet is built in: x centred on the hole, y up from the running
// surface, z from the sheet's inner face OUTWARD (0 .. the sheet, then the top return out to LIP). The sheet runs
// from just under the surface (-0.005) to the guard top with a round hole at `holeY`; the top return runs over it
// unbroken, so a guard with a hole in it still shows one continuous top edge. Mirror it onto the other side with a
// 180 degree yaw, never a negative scale (a mirror turns the faces inside out).
//
// The numbers are the guard's own (GUARD_HEIGHT, GUARD_THICKNESS, the 20 mm return, GUARD_HOLE_RADIUS and
// GUARD_HOLE_PANEL in core/types): keep them in sync.
//
// `lip`: draw the top return over the panel. A family whose guard SHEET carries its return (the belt's swept L
// section, split around the hole with it) needs it; one whose return is its own continuous part (the spurs' lip
// boxes) must not, or the two coincide face to face and z-fight.
function holePanel(g, holeY, lip) {
  var H = 0.15, T = 0.005, LIP = 0.025, LIP_T = 0.005, R = 0.02, PW = 0.1
  var hole = []
  for (var k = 0; k < 16; k++) { var a = (k * Math.PI) / 8; hole.push([R * Math.cos(a), holeY + R * Math.sin(a)]) }
  var sheet = g.extrude([[-PW / 2, -0.005], [PW / 2, -0.005], [PW / 2, H], [-PW / 2, H]], 0, T, { axis: 'z', holes: [hole] })
  if (!lip) return sheet
  return g.merge(sheet, g.box([PW, LIP_T, LIP - T], [0, H - LIP_T / 2, T + (LIP - T) / 2]))
}

/** the panel's length along the guard (core GUARD_HOLE_PANEL) */
const HOLE_PANEL = 0.1

// ---- from examples/parts/_shared/guardMitre.js ----
/** the param, host-fed and hidden like guardHoles, in the part's guard group */
function guardMitresParam(group) {
  return { guardMitres: { type: 'numberList', arity: 3, default: [], hidden: true, label: 'Guard mitres [x m, c, side ±1]', group, desc: 'Where a guard end is cut at an angle to meet the guard of the conveyor this one merges with. Worked out by the host from the scene; not for editing.' } }
}

/** `mitreAt(sign, x)` for these params: the cut at a piece end (0 = square). */
function mitreLookup(p) {
  var mitreRows = Array.isArray(p.guardMitres) ? p.guardMitres : []
  return function mitreAt(sign, x) {
    for (var mr = 0; mr < mitreRows.length; mr++) if (mitreRows[mr][2] === sign && Math.abs(mitreRows[mr][0] - x) < 1e-3) return mitreRows[mr][1]
    return 0
  }
}

/** the RAIL twin of the param: [x, c, side ±1] rows (core/guardExtents.ts GuardExtents.railCuts), host-fed, hidden */
function railCutsParam(group) {
  return { railCuts: { type: 'numberList', arity: 3, default: [], hidden: true, label: 'Rail cuts [x m, c, side ±1]', group, desc: 'Where a frame rail end is cut to fit against the frame of the conveyor this one merges onto. Worked out by the host from the scene; not for editing.' } }
}

/**
 * Fitting a frame RAIL end against the host's frame, which stays whole. `railCutLookup(p)` gives
 * `railCutAt(sign, x)`, the row's c at a rail end, or null (no cut). `railEndBands(x, into, c, yBot)` = where the rail
 * stops and what fills out to the cut: `{ sq, bands }`, `sq` the X the square (instanced) rail stops at and each band
 * `{ pts, y0, y1 }` a plan outline in (x, d) to extrude upright, d measured OUT from the guard line (the rail's wall is
 * d -0.01..0 under it, its top flange 0..0.02). `into` is +1 when the piece lies at larger x. The wall ends on the
 * host's outer wall face (c * d back), the flange on the host flange's outer edge, one flange width further out, so
 * sqrt(1 + c^2) * 0.02 further back.
 */
function railCutLookup(p) {
  var railCutRows = Array.isArray(p.railCuts) ? p.railCuts : []
  return function railCutAt(sign, x) {
    for (var rc = 0; rc < railCutRows.length; rc++) if (railCutRows[rc][2] === sign && Math.abs(railCutRows[rc][0] - x) < 1e-3) return railCutRows[rc][1]
    return null
  }
}
function railEndBands(x, into, c, yBot) {
  var F = 0.02 * Math.sqrt(1 + c * c)
  function at(d, f) { return x + into * (c * d + f) }
  var uMax = Math.max(-0.01 * c, 0, F, 0.02 * c + F)
  var sq = x + into * uMax
  function band(d0, d1, f, y0, y1) {
    var raw = [[sq, d0], [at(d0, f), d0], [at(d1, f), d1], [sq, d1]], pts = []
    for (var i = 0; i < raw.length; i++) {
      var q = raw[i], prev = pts.length ? pts[pts.length - 1] : raw[raw.length - 1]
      if (Math.abs(q[0] - prev[0]) > 1e-6 || Math.abs(q[1] - prev[1]) > 1e-6) pts.push(q)
    }
    return pts.length >= 3 ? { pts: pts, y0: y0, y1: y1 } : null
  }
  var bands = [band(-0.01, 0, 0, yBot, -0.005), band(0, 0.02, F, -0.005, 0)].filter(function (b) { return b })
  return { sq: sq, bands: bands }
}

/**
 * The SPURS' straight side rails: `spurRailCutter(g, hw, FWT, FB, railCutAt)` gives `{ railFills, cutRailInstance }`.
 * `cutRailInstance(sign, bE, fE)` = the unit-rail instance for the side-`sign` rail spanning bE..fE, with each end
 * that has a rail cut stopped square at the cut's deepest point, and that end's fill pushed onto `railFills` (emit
 * them as one 'frame' part). The -Z rail is the template yawed 180 degrees, never mirrored.
 */

/**
 * A STRAIGHT guard built along bed-local X with its inner face at |z| = zIn:
 * `guardBand(g, x0, x1, c0, c1, d0, d1, y0, y1, sign, zIn)` = one band of the guard section, x0..x1, d0..d1 outward from
 * the inner face, y0..y1 tall, its ends cut by c0 / c1. Square ends stay a plain box; a mitred end is the band's plan
 * outline extruded upright. A piece too short to hold both cuts stays square.
 */

// ---- from examples/parts/_shared/legs.js ----
// The conveyor floor support, drawn once for every legged conveyor (belt, curved, curved roller, spur, spur roller),
// and mirrored in TS by legPieces() in src/render/parts/common.ts for the rig roller's kind:'leg' link
// (conveyorLegs.test.ts holds the two to the same pieces).
//
// It is sized to a typical unit-handling conveyor floor stand, not a
// trestle whose posts were a 7.8" x 5.9" box: formed-channel uprights 4" x 1-3/4" standing under the side frames, a support
// channel across under the bed, a 1-1/2" x 8" mounting bracket bolted to each frame web, a 6" x 4" x 1/4" foot
// plate with two anchor bolts, a telescoping inner leg with its adjustment bolts, horizontal cross braces, and knee
// braces once the stand is tall.
//
// Leg-local metres: the floor at y 0, x along travel centred on the station, z across. `height` is the frame bottom
// above the floor, `hw` half the bed width (the side frame's wall is hw .. hw + 0.01), `dir` the way the knee
// braces lean along x (+1 / -1, toward the middle of the bed; 0 = none, e.g. on an arc, where a brace reaching
// along the tangent would miss the curving frame). `frameDepth` is the deck → frame bottom: the mounting bracket
// climbs 0.127 up the frame web, or stops 10 mm under the deck on a frame too shallow for that (a belt's Frame height
// goes down to 0.1), dropping the web bolts it no longer reaches. Omitted, it takes the full rise.
//
// Returns { boxes, bolts }: a box is [cx, cy, cz, sx, sy, sz, rz] (a unit cube scaled, then turned rz about z),
// a bolt [cx, cy, cz, r, depth, axis] (a hex head, axis 'y' standing up or 'z' across).
function legPieces(hw, height, dir, frameDepth) {
  var boxes = [], bolts = []
  function box(x0, y0, z0, x1, y1, z1) { boxes.push([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, Math.max(x1 - x0, 1e-4), Math.max(y1 - y0, 1e-4), Math.max(z1 - z0, 1e-4), 0]) }
  function bolt(x, y, z, axis) { bolts.push([x, y, z, 0.009, 0.007, axis]) }
  var FACE = hw + 0.01 //              the side frame's outer face: the uprights stand flush under it
  var LW = 0.0508, LD = Math.min(0.0445, Math.max(hw - 0.02, 0.02)) // upright: 4" along travel, 1-3/4" deep
  var PT = 0.009, CH = 0.076 //        foot plate top (1/4" plate on a 3 mm floor gap); support channel depth (3")
  var TELE = height > 0.45 ? 0.3 : 0 // the telescoping inner leg's top, on a stand tall enough to adjust
  var RISE = typeof frameDepth === 'number' ? Math.max(0, Math.min(0.127, frameDepth - 0.01)) : 0.127 // bracket rise up the web
  for (var sg = 0; sg < 2; sg++) {
    var s = sg === 0 ? 1 : -1, zo = s * FACE, zi = s * (FACE - LD), zc = s * (FACE - LD / 2)
    var lo = Math.min(zo, zi), hi = Math.max(zo, zi)
    if (TELE > 0) {
      box(-0.042, PT, lo + 0.004, 0.042, TELE, hi - 0.004) // inner leg
      box(-LW, TELE - 0.05, lo, LW, height, hi) //             outer leg, sleeved over it
      bolt(-0.025, TELE - 0.025, zo + s * 0.0035, 'z'); bolt(0.025, TELE - 0.025, zo + s * 0.0035, 'z') // adjustment bolts
    } else box(-LW, PT, lo, LW, height, hi)
    box(-0.0762, 0.003, zc - 0.0508, 0.0762, PT, zc + 0.0508) // foot plate
    bolt(-0.055, PT + 0.0035, zc, 'y'); bolt(0.055, PT + 0.0035, zc, 'y') // anchor bolts
    var bo = zo + s * 0.006
    box(-0.019, height - CH, Math.min(zo, bo), 0.019, height + RISE, Math.max(zo, bo)) // mounting bracket on the frame web
    if (0.04 + 0.009 <= RISE) bolt(0, height + 0.04, bo + s * 0.0035, 'z') // the web bolts the bracket still reaches
    if (0.1 + 0.009 <= RISE) bolt(0, height + 0.1, bo + s * 0.0035, 'z')
    bolt(0, height - CH / 2, bo + s * 0.0035, 'z')
    if (dir !== 0 && height > 1.0) { // knee brace: 1-1/4" angle from the upright up to the frame web, outside both
      var d = Math.min(0.6, 0.45 * height), ax = 0, ay = height - d, bx = dir * d, by = height + 0.04
      var L = Math.hypot(bx - ax, by - ay), ux = (bx - ax) / L, uy = (by - ay) / L, kz = s * (FACE + 0.016 + 0.006)
      boxes.push([(ax + bx) / 2, (ay + by) / 2, kz, L, 0.032, 0.032, Math.atan2(by - ay, bx - ax)])
      bolt(ax + ux * 0.03, ay + uy * 0.03, kz + s * 0.0195, 'z'); bolt(bx - ux * 0.03, by - uy * 0.03, kz + s * 0.0195, 'z')
    }
  }
  var zin = FACE - LD + 0.005 //         the uprights' inner faces, lapped 5 mm
  box(-0.0222, height - CH, -zin, 0.0222, height, zin) // support channel across under the bed
  if (height >= 0.6) { // horizontal cross braces (1-3/4" x 1-1/2" channel), clear of the telescoping joint
    var n = Math.min(Math.max(Math.floor(height / 0.9), 1), 3), y0 = TELE + 0.1, y1 = height - CH - 0.1
    for (var k = 0; k < n && y1 > y0; k++) { var y = y0 + ((k + 1) * (y1 - y0)) / (n + 1); box(-0.0222, y - 0.019, -zin, 0.0222, y + 0.019, zin) }
  }
  return { boxes: boxes, bolts: bolts }
}

// Station layout shared by the straight beds: supports stand at the ends and at bed-joint pitch between (a
// 10 ft section), the way a real run is supported. LEG_END_INSET is the station's distance in from the end: the
// upright's half-width plus clearance for the foot plate.
const LEG_END_INSET = 0.15
const LEG_SPACING = 3.05
// how far past an end station the middle cadence may start: a third of the pitch, so a middle support never lands
// within a metre of an end one (at the old 0.5 a 4 m bed stood a middle leg 0.8 m from its head leg)
const LEG_CLEARANCE = 1.0

const drive = conveyorDrive() // the ramp, the pulse and the encoder, remembered between steps

definePart({
  params: {
    // stamps:'segments' — picking an option writes its [length, tilt] rows into the 'segments' param (which
    // stays the source of truth); hand-editing segments afterwards drifts this back to 'custom'.
    shapePreset: {
      type: 'enum', default: 'straight', label: 'Shape preset', stamps: 'segments',
      desc: 'One-tap template for the segment table below. Picking an option writes its rows into Segments, which stays the source of truth - so hand-editing the table afterwards drifts this back to Custom rather than fighting you.',
      options: [
        { value: 'straight', label: 'Straight', rows: [[4, 0]] },
        { value: 'zframe', label: 'Z-Frame', rows: [[2, 0], [3, 12], [2, -12]] },
        { value: 'walkthru', label: 'Walk-Thru', rows: [[2, 0], [3, 25], [2, -25], [3, -25], [2, 25]] },
        { value: 'noseover', label: 'Nose-Over', rows: [[2, 0], [3, -8]] },
        { value: 'custom', label: 'Custom' },
      ],
    },
    // One [length m, tilt °] row per straight run; the bend between runs is filleted. The 'path' handle adds
    // viewport gizmos — a tail dot + one draggable node per run (lengthCol/tiltCol name the row's columns).
    segments: { type: 'numberList', columns: ['length m', 'tilt °'], arity: 2, default: [[4, 0]], label: 'Segments', handle: { kind: 'path', lengthCol: 0, tiltCol: 1 }, desc: 'One row per straight run: how long it is and how steeply it climbs, with the bend between runs filleted automatically. Add rows to build an incline, a Z-frame or a walk-through. The viewport shows a dot per run, so this is usually easier to drag than to type.' },
    // the 'face' handle puts a ± width dot on each Z face — drag to widen, clamped to this param's min/max.
    width: { type: 'number', default: 1.524, min: 0.2, step: 0.05, label: 'Width (m)', handle: { kind: 'face', axis: 'z' }, group: 'Size', desc: 'Belt width across the direction of travel. Drag the dot on either side face to resize in the viewport.' },
    // belt height = the fillet bend radius joining runs + the deck-to-underside depth; shared by geometry()
    // and the host's per-segment collision. The side frame is exactly this deep (FB in geometry()), so the frame's
    // inner edge meets the fillet centre at a bend instead of folding past it. Default 0.17 = a real unit-handling
    // belt (6-5/8" frame, 6-8" pulleys).
    height: { type: 'number', default: 0.17, min: 0.1, max: 0.6, step: 0.01, label: 'Frame height (m)', group: 'Size', desc: 'Depth of the bed itself: deck down to underside, which is also the fillet radius where two segments meet and the depth of the side frame. NOT the height off the floor - that is Stand height below.' },
    // deck height above the floor — drives the leg length. rest:'surfaceBelow' lets the host auto-fill it from
    // the surface beneath at drop/snap, so the legs reach the floor (or a platform) without geometry() ever
    // knowing about placement.
    standHeight: { type: 'number', default: 2.0, min: 0.1, max: 3, step: 0.01, rest: 'surfaceBelow', label: 'Stand height (m)', desc: 'Height of the deck above whatever is beneath it, which sets the leg length. The host fills this in when you drop or snap the conveyor, so the legs reach the floor - or a platform crossing underneath - without you measuring. Pin it by hand when you want a deliberate height.' },
    ...speedUnitParams(2),
    speed: { type: 'number', unit: 'm/s', ...METRIC_ONLY, default: 2, min: -3, max: 3, step: 0.1, label: 'Speed', desc: 'Surface speed carried along the bed. Negative runs the belt backwards, which is the ONLY way to reverse flow - rotating the part 180 degrees moves its ends instead. A program can command this through the speed tag below.' },
    ...driveRampParams(0.5, 0.5),
    ...frictionParam(0.59),
    // fabric tint, multiplied into the belt-surface material — white leaves the weave at full brightness, a
    // dark tint multiplies it down toward black.
    beltColor: { type: 'color', default: '#ffffff', label: 'Belt color', desc: 'Tint multiplied into the belt weave. White leaves the fabric at full brightness; a dark tint multiplies it down toward black.' },
    // 'alternate' swaps the belt-surface image to /textures/BeltFabricArrows.jpg — directional arrows that
    // scroll along travel to show flow direction.
    beltTexture: {
      type: 'enum', default: 'standard', label: 'Belt weave',
      desc: 'Which fabric the belt surface wears. Alternate carries directional arrows that scroll along travel, which is the cheapest way to make flow direction readable in a screenshot.',
      options: [
        { value: 'standard', label: 'Standard' },
        { value: 'alternate', label: 'Arrows (shows flow)' },
      ],
    },
    // the 'group' field clusters params into collapsible Inspector sections.
    frameRails: { type: 'boolean', default: true, label: 'Frame rails', group: 'Guards', desc: 'Structural rails down both sides of the bed. Cosmetic - the running surface and its collision are unaffected.' },
    leftGuard: { type: 'boolean', default: true, label: 'Left guard', group: 'Guards', desc: 'Guard wall down the left side, looking along travel. This is a real barrier, so turning it off lets cargo leave the belt sideways.' },
    rightGuard: { type: 'boolean', default: true, label: 'Right guard', group: 'Guards', desc: 'Guard wall down the right side, looking along travel. This is a real barrier, so turning it off lets cargo leave the belt sideways.' },
    // side-guard openings as [start m, end m, side] rows — arc-length from the tail; side −1 = left, +1 =
    // right, 0 = both. Cuts a gap in the guard wall's render AND collision (a sensor, a transfer).
    // Neighbour-auto openings (a guard opening itself where another conveyor butts) stay a host concern.
    guardOpenings: { type: 'numberList', columns: ['start m', 'end m', 'side ±1/0'], arity: 3, default: [], label: 'Guard openings', group: 'Guards', desc: 'Gaps cut in the guard wall, measured as distance ALONG the belt from the tail. Side -1 is left, +1 is right, 0 cuts both. Each gap opens the collision as well as the mesh, which is how a transfer or a diverter gets product off the lane.' },
    // sensor-beam holes as [s m, y m, side ±1] rows: arc-length from the tail, height above the belt, side −1 left /
    // +1 right. HOST-FED and never authored: the host works out where every beam in the scene crosses this
    // belt's guards (core/guardHoles.ts) and folds the holes in at render time, so the param is hidden.
    guardHoles: { type: 'numberList', arity: 3, default: [], hidden: true, label: 'Guard holes [s m, y m, side ±1]', group: 'Guards', desc: 'Where sensor beams cross the side guards. Worked out by the host from the scene; not for editing.' },
    // mitred guard ends as [x m, c, side ±1] rows, x in PLAN local X (_shared/guardMitre.js). HOST-FED, so hidden.
    ...guardMitresParam('Guards'),
    // frame rail end cuts as [x m, c, side ±1] rows, x in PLAN local X (_shared/guardMitre.js). HOST-FED, so hidden.
    ...railCutsParam('Guards'),
    // rail/guard end overrides as [side ±1, backX m, frontX m] rows (belt-local X, incl. the drum overhang).
    // Host-fed: on a FLUSH side-merge the host folds in the snap-derived extents so the rails + guards
    // RETRACT to the host's outer wall plane instead of running through its frame.
    guardExtents: { type: 'numberList', hidden: true, arity: 3, default: [], label: 'Rail extents [side ±1, back m, front m]', group: 'Guards', desc: 'Where the rails and guards STOP on each side, in belt-local X. Normally written by the host: when another conveyor merges flush against a side, this retracts the rails to its outer wall instead of running them through its frame. Worked out by the host from the scene; not for editing.' },
    legs: { type: 'boolean', default: true, label: 'Support legs', group: 'Legs', desc: 'Master switch for the leg set below. Off leaves the bed floating, which is what you want when it is carried by a mezzanine or bolted to another frame.' },
    // per-leg footing rows [x0 m, x1 m, dy m] (plan-X, tail-origin) — where the surface under the bed DIFFERS
    // from the part's own floor plane (−standHeight): dy > 0 = feet stand on a platform deck crossing under,
    // dy < 0 = feet drop past this part's deck to the floor. Host-fed; a leg squeezed under 5 cm is dropped.
    legRests: { type: 'numberList', hidden: true, arity: 3, default: [], label: 'Leg rests [x0 m, x1 m, dy m]', group: 'Legs', desc: 'Per-leg floor heights for stretches where the surface underneath is NOT this part own floor plane - a platform deck crossing under, or a drop past it. Host-written at placement; a leg squeezed into less than 5 cm is dropped rather than drawn stubby.' },
    // each end: its own inset from the drum + a clearance the middle-leg cadence starts beyond.
    tailLeg: { type: 'boolean', default: true, label: 'Tail leg', group: 'Legs/Tail End', desc: 'Draw a leg pair at the tail - the upstream end, where cargo arrives.' },
    tailLegOffset: { type: 'number', default: LEG_END_INSET, min: 0, max: 2, step: 0.01, label: 'Tail inset (m)', group: 'Legs/Tail End', desc: 'How far back from the tail drum the end leg stands. Increase it to clear whatever butts up against this end.' },
    tailLegClearance: { type: 'number', default: LEG_CLEARANCE, min: 0, max: 5, step: 0.05, label: 'Tail clearance (m)', group: 'Legs/Tail End', desc: 'Dead band past the tail leg before the evenly-spaced middle legs are allowed to start.' },
    headLeg: { type: 'boolean', default: true, label: 'Head leg', group: 'Legs/Head End', desc: 'Draw a leg pair at the head - the downstream end, where cargo discharges.' },
    headLegOffset: { type: 'number', default: LEG_END_INSET, min: 0, max: 2, step: 0.01, label: 'Head inset (m)', group: 'Legs/Head End', desc: 'How far back from the head drum the end leg stands. Increase it to clear whatever butts up against this end.' },
    headLegClearance: { type: 'number', default: LEG_CLEARANCE, min: 0, max: 5, step: 0.05, label: 'Head clearance (m)', group: 'Legs/Head End', desc: 'Dead band before the head leg that the evenly-spaced middle legs must stop short of.' },
    middleLegs: { type: 'boolean', default: true, label: 'Middle legs', group: 'Legs/Middle Legs', desc: 'Fill the span between the end legs with evenly-spaced intermediate ones.' },
    legSpacing: { type: 'number', default: LEG_SPACING, min: 0.5, max: 10, step: 0.05, label: 'Middle leg spacing (m)', group: 'Legs/Middle Legs', desc: 'Target gap between intermediate legs: 3.05 m is a real run supported at every 10 ft bed joint. The middle legs step on multiples of it, so the actual gap lands at or just under this.' },
    // skip any leg whose arc-length from the tail falls in [start, end]; start >= end disables the zone.
    exclusionStart: { type: 'number', default: 0, min: 0, max: 100, step: 0.1, label: 'Exclusion start (m)', group: 'Legs/Exclusion Zone', desc: 'Start of a stretch, measured along the belt from the tail, where no leg is drawn - room for a floor conveyor, a pit or a walkway crossing beneath. Leaving start and end equal disables the zone.' },
    exclusionEnd: { type: 'number', default: 0, min: 0, max: 100, step: 0.1, label: 'Exclusion end (m)', group: 'Legs/Exclusion Zone', desc: 'End of the no-leg stretch. It must be GREATER than the start, or the zone is ignored entirely.' },
    // Comms trio: speedTag = REAL setpoint in (replaces the speed param), runningTag = BOOL feedback out
    // (effective speed ≠ 0); runTag = BOOL run/stop gate (back-compat).
    speedTag: { type: 'tag', ...METRIC_ONLY, dir: 'in', stType: 'REAL', setpointFor: 'speed', default: '', label: 'Speed tag', group: 'Comms', desc: 'The program commands belt speed here, replacing the Speed field above, which then shows the live value read-only. Careful: once BOUND this takes over even if no program drives it, and an undriven tag reads 0 - so a half-wired belt sits still rather than running at its authored speed.' },
    ...speedFpmTagParam('Comms'),
    runTag: { type: 'tag', dir: 'in', stType: 'BOOL', onlyWhenDriven: true, default: '', label: 'Run tag (belt runs while true)', group: 'Comms', desc: 'Start/stop gate: false forces the speed to 0 whatever the setpoint says. Unlike the speed tag, this only takes effect once a program actually DRIVES it, so binding it alone will not stop the belt.' },
    runningTag: { type: 'tag', dir: 'out', stType: 'BOOL', default: '', label: 'Running tag (true while moving)', group: 'Comms', desc: 'Feedback the belt publishes for the program to read: true whenever it is actually moving. This is the EFFECTIVE speed, gates included, so a run tag holding the belt at zero reads false here.' },
    ...driveFeedbackParams(2, 'Comms'),
  },
  // Procedural geometry — the belt as a multi-material MeshPart[]: a scrolling fabric bed + steel frame rails
  // + side guards + support legs. Returning an array (not one merged mesh) lets the host surface the fabric
  // and the steel with their own materials.
  geometry(g, p) {
    var DEG = Math.PI / 180
    var hw = p.width / 2
    var h = typeof p.height === 'number' && p.height > 0 ? p.height : 0.28 // belt height = the fillet radius

    // path — the bent belt centreline, composed: segment corners (cumulative tilt) → fillet the bends.
    // Each row's tilt turns the path from the row before. The turn and the running tilt both stay within ±89°, so
    // the belt never doubles back: the host's colliders and guards follow core/beltPath.ts beltSegmentAngles, which
    // applies the same rule, and g.fillet tightens a bend the way the host's path does.
    var MAX_TILT = 89
    var corners = [[0, 0, 0]]
    var tilt = 0, cx = 0, cy = 0
    for (var i = 0; i < p.segments.length; i++) {
      tilt += Math.max(-MAX_TILT, Math.min(MAX_TILT, p.segments[i][1])) * DEG
      tilt = Math.max(-MAX_TILT * DEG, Math.min(MAX_TILT * DEG, tilt))
      cx += Math.cos(tilt) * p.segments[i][0]
      cy += Math.sin(tilt) * p.segments[i][0]
      corners.push([cx, cy, 0])
    }
    var path = g.fillet(corners, h)
    // frame + guards extend over the end drums by the pulley radius (h/2) to cover the belt loop's wrap.
    var rr = h / 2
    // frame bottom: the rail wall runs from just under the belt (−0.005) down the whole belt loop, so it hides the
    // return run and the drum wraps at any height, and the legs + web-bolts below are measured from it. Rounded to
    // the micrometre: the rail template is pooled BY VALUE with the spurs' literal −0.175, and 0.17 + 0.005 is
    // 0.17500000000000002 in binary, one bit that would split the pool.
    var FB = -Math.round((h + 0.005) * 1e6) / 1e6
    function endTan(a, b) { var dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; return [dx / l, dy / l] }
    var t0 = endTan(path[0], path[1]), tN = endTan(path[path.length - 2], path[path.length - 1])
    var framePath = [[path[0][0] - t0[0] * rr, path[0][1] - t0[1] * rr, 0]]
    for (var fi = 0; fi < path.length; fi++) framePath.push([path[fi][0], path[fi][1], 0])
    framePath.push([path[path.length - 1][0] + tN[0] * rr, path[path.length - 1][1] + tN[1] * rr, 0])

    // convert each side's guardExtents X overrides to framePath ARC bounds via the end tangents (a mated end
    // run is horizontal, so cos ≈ 1; the clamp guards a steeply-tilted authored end).
    var frameLen = 0
    for (var fl = 1; fl < framePath.length; fl++) frameLen += Math.hypot(framePath[fl][0] - framePath[fl - 1][0], framePath[fl][1] - framePath[fl - 1][1])
    var extRows = Array.isArray(p.guardExtents) ? p.guardExtents : []
    var backFaceX = framePath[0][0], frontFaceX = framePath[framePath.length - 1][0]
    function sideArcSpan(sign) {
      var lo = 0, hi = frameLen
      for (var xr = 0; xr < extRows.length; xr++) {
        if (extRows[xr][0] !== sign) continue
        lo = Math.max(lo, (extRows[xr][1] - backFaceX) / Math.max(Math.abs(t0[0]), 0.25))
        hi = Math.min(hi, frameLen - (frontFaceX - extRows[xr][2]) / Math.max(Math.abs(tN[0]), 0.25))
      }
      return [lo, hi]
    }
    var railArcL = sideArcSpan(-1), railArcR = sideArcSpan(1)

    // 1. BELT BED — the full belt band wrapping the end drums. Drum radius = h/2; the band rides a constant
    // cross-belt ±bw (a sweep would pinch at the drum wraps — its width axis T×up collapses on a vertical
    // tangent), u = arc-length along the loop (fabric tiling). Two shapes:
    //
    //  - STRAIGHT path: instances of two param-independent unit templates — a 1 m band strip (top run +
    //    bottom return; length in scale.x) and a half-cylinder drum-wrap band (one per end) — so every
    //    same-height belt shares two geometries in the scene-global instance pool. u is baked in local metres
    //    (band 0..1 over its unit metre, wrap 0..πr) and each instance carries data: [uMul, uAdd]; the shared
    //    fabric material reconstructs the loop arc-length (u·uMul + uAdd), so the weave tiles continuously
    //    across the four pieces and the scroll rides a per-instance attribute, not a texture offset.
    //
    //  - BENT path: the closed loop (top run → head-drum wrap → bottom return offset 2r down each station's
    //    normal → tail-drum wrap → close) is hatched as one per-belt band — a bend can't share a template.
    var r = h / 2
    var bw = hw - 0.005 // belt band just inside the guards
    // straight iff every filleted path point lies on the end-to-end chord (no fillet arcs survive)
    var bedDx = path[path.length - 1][0] - path[0][0], bedDy = path[path.length - 1][1] - path[0][1]
    var bedL = Math.hypot(bedDx, bedDy)
    var bedStraight = bedL > 0.02
    for (var sp2 = 1; sp2 < path.length - 1 && bedStraight; sp2++) {
      if (Math.abs((path[sp2][0] - path[0][0]) * bedDy - (path[sp2][1] - path[0][1]) * bedDx) / bedL > 1e-6) bedStraight = false
    }
    var bed, bedWraps = null
    if (bedStraight) {
      // band template: 1 m unit strip in the conveying plane (y=0), z ±1 → ±bw via scale.z, u = local metres
      var bandSfc = g.surface()
      var ba0 = bandSfc.vertex(0, 0, -1, 0, 0), bb0 = bandSfc.vertex(0, 0, 1, 0, 1)
      var ba1 = bandSfc.vertex(1, 0, -1, 1, 0), bb1 = bandSfc.vertex(1, 0, 1, 1, 1)
      bandSfc.quad(ba0, bb0, bb1, ba1)
      // wrap template: half-cylinder drum band, top tangent point over the front to the bottom (8 segments,
      // matching the bent bed's g.arc tessellation), drum centre local (0, −r), u = arc metres (0..πr)
      var wrapSfc = g.surface()
      var wPrevA = -1, wPrevB = -1
      for (var wi = 0; wi <= 8; wi++) {
        var wTh = Math.PI / 2 - (wi * Math.PI) / 8
        var wU = r * ((wi * Math.PI) / 8)
        var wA = wrapSfc.vertex(Math.cos(wTh) * r, Math.sin(wTh) * r - r, -1, wU, 0)
        var wB = wrapSfc.vertex(Math.cos(wTh) * r, Math.sin(wTh) * r - r, 1, wU, 1)
        if (wi > 0) wrapSfc.quad(wPrevA, wPrevB, wB, wA)
        wPrevA = wA; wPrevB = wB
      }
      // 4 instances in loop order (uAdd chains their arc-lengths): top run tail→head, head wrap, bottom
      // return head→tail, tail wrap over the back. The return pieces are the same templates rotated π about
      // Z — a proper rotation, not a mirror, so instance-transformed normals stay exact.
      var bedAng = Math.atan2(bedDy, bedDx)
      var bedNx = -bedDy / bedL, bedNy = bedDx / bedL
      var qFwd = Math.abs(bedAng) > 1e-9 ? [0, 0, Math.sin(bedAng / 2), Math.cos(bedAng / 2)] : undefined
      var qBack = [0, 0, Math.sin((bedAng + Math.PI) / 2), Math.cos((bedAng + Math.PI) / 2)]
      var bedHx = path[path.length - 1][0], bedHy = path[path.length - 1][1]
      var wrapU = Math.PI * r
      bed = { desc: bandSfc.build(), finish: 'belt', instances: [
        { position: [0, 0, 0], quaternion: qFwd, scale: [bedL, 1, bw], data: [bedL, 0] },
        { position: [bedHx - bedNx * 2 * r, bedHy - bedNy * 2 * r, 0], quaternion: qBack, scale: [bedL, 1, bw], data: [bedL, bedL + wrapU] },
      ] }
      bedWraps = { desc: wrapSfc.build(), finish: 'belt', instances: [
        { position: [bedHx, bedHy, 0], quaternion: qFwd, scale: [1, 1, bw], data: [1, bedL] },
        { position: [-bedNx * 2 * r, -bedNy * 2 * r, 0], quaternion: qBack, scale: [1, 1, bw], data: [1, 2 * bedL + wrapU] },
      ] }
    } else {
      function nrm(a, b) { var tx = b[0] - a[0], ty = b[1] - a[1], l = Math.hypot(tx, ty) || 1; return [-ty / l, tx / l] }
      var topN = []
      for (var i2 = 0; i2 < path.length; i2++) topN.push(nrm(path[Math.max(0, i2 - 1)], path[Math.min(path.length - 1, i2 + 1)]))
      var head = path[path.length - 1], hn = topN[topN.length - 1]
      var tail = path[0], tn = topN[0]
      var loop = []
      for (var i2 = 0; i2 < path.length; i2++) loop.push([path[i2][0], path[i2][1], 0])
      var hAng = Math.atan2(hn[1], hn[0])
      var hWrap = g.arc([head[0] - hn[0] * r, head[1] - hn[1] * r, 0], r, hAng, hAng - Math.PI, 8) // over the front
      for (var i2 = 1; i2 < hWrap.length; i2++) loop.push([hWrap[i2][0], hWrap[i2][1], 0])
      for (var i2 = path.length - 1; i2 >= 0; i2--) loop.push([path[i2][0] - topN[i2][0] * 2 * r, path[i2][1] - topN[i2][1] * 2 * r, 0])
      var tAng = Math.atan2(tn[1], tn[0])
      var tWrap = g.arc([tail[0] - tn[0] * r, tail[1] - tn[1] * r, 0], r, tAng + Math.PI, tAng, 8) // over the back
      for (var i2 = 1; i2 < tWrap.length - 1; i2++) loop.push([tWrap[i2][0], tWrap[i2][1], 0])
      loop.push([tail[0], tail[1], 0])
      var sfc = g.surface()
      var prevA = -1, prevB = -1, ulen = 0
      for (var i2 = 0; i2 < loop.length; i2++) {
        if (i2 > 0) ulen += Math.hypot(loop[i2][0] - loop[i2 - 1][0], loop[i2][1] - loop[i2 - 1][1])
        var va = sfc.vertex(loop[i2][0], loop[i2][1], -bw, ulen, 0)
        var vb = sfc.vertex(loop[i2][0], loop[i2][1], bw, ulen, 1)
        if (i2 > 0) sfc.quad(prevA, prevB, vb, va)
        prevA = va; prevB = vb
      }
      bed = { desc: sfc.build(), finish: 'belt' }
    }

    // 2. SIDE FRAME RAILS (steel) — an L-rail (0.01 wall + 0.02 flange, h deep, rail top −0.005 just under
    // the belt surface): a vertical wall at the belt edge + an outward top-flange lip.
    //
    // Straight runs are instances of a 1 m unit-rail template (profile z local 0..0.03, outward = +z) — size
    // in scale.x, side in a 180° yaw about the run (steelPiece: NEVER a mirror scale — see the note there),
    // tilt in a Z-rotation; built from constants + the height (the wall depth), so every same-height belt shares
    // one geometry in the scene-global instance pool, like the drum wraps above. Fillet bends stay swept (mitered) meshes: butt-jointed straight pieces
    // would open wedge gaps at each arc facet.
    //
    // split the (collinear-merged) framePath into straight runs >= MIN_RUN + the leftover bend ranges, in
    // the same arc-length space as the guard spans below. runs: {ax, ay, bx, by, s0, s1}; bends: {s0, s1}.
    var MIN_RUN = 0.15
    var pathSplit = (function (poly) {
      var cum = [0]
      for (var j = 1; j < poly.length; j++) cum.push(cum[j - 1] + Math.hypot(poly[j][0] - poly[j - 1][0], poly[j][1] - poly[j - 1][1]))
      var runs = [], bends = [], bendStart = -1
      var flushBend = function (endIdx) { if (bendStart >= 0) { bends.push({ s0: cum[bendStart], s1: cum[endIdx] }); bendStart = -1 } }
      var c = 0
      for (var j = 1; j <= poly.length - 1; j++) {
        var isLast = j === poly.length - 1
        var turn = false
        if (!isLast) {
          var d1x = poly[j][0] - poly[j - 1][0], d1y = poly[j][1] - poly[j - 1][1]
          var d2x = poly[j + 1][0] - poly[j][0], d2y = poly[j + 1][1] - poly[j][1]
          turn = Math.abs(d1x * d2y - d1y * d2x) > 1e-9 * Math.max(1e-9, Math.hypot(d1x, d1y) * Math.hypot(d2x, d2y))
        }
        if (turn || isLast) {
          if (cum[j] - cum[c] >= MIN_RUN) { flushBend(c); runs.push({ ax: poly[c][0], ay: poly[c][1], bx: poly[j][0], by: poly[j][1], s0: cum[c], s1: cum[j] }) }
          else if (bendStart < 0) bendStart = c
          c = j
        }
      }
      flushBend(poly.length - 1)
      return { runs: runs, bends: bends, cum: cum }
    })(framePath)
    // unit rail template: wall + flange swept 1 m along +X, cross-section z-local (0 = belt edge, +0.03 = flange tip)
    var UNIT_X = [[0, 0, 0], [1, 0, 0]]
    // CAPS: every piece's ends are closed. A straight piece that continues into a bend hides its cap inside the
    // joint; one that stops (a drum end, an opening edge, a retracted junction) would otherwise show a hollow tube.
    var CAPS = { caps: true }
    var railTemplate = g.merge(
      g.sweep([[FB, 0], [FB, 0.01], [-0.005, 0.01], [-0.005, 0]], UNIT_X, CAPS),
      g.sweep([[-0.005, 0.01], [-0.005, 0.03], [0, 0.03], [0, 0.01]], UNIT_X, CAPS),
    )
    // a straight piece from (ax,ay)..(bx,by) at side 'sign': scale.x = length, tilt = Z-rotation. The −Z side
    // is the same prism RUN BACKWARDS (anchored at the far end, yawed 180° so local +z lands on −z), NOT a
    // z-mirror scale. A negative scale makes the instance matrix negative-determinant, which reverses the
    // triangle winding; under DoubleSide three then flips the shading normal by gl_FrontFacing, so the
    // mirrored side is lit as if its OUTER face were the inner one — the two guards/rails read as different
    // colours. The renderer's own mirrored-object fix (frontFaceCW) reads object.matrixWorld and never the
    // per-instance matrix, so an InstancedMesh can't be rescued that way. Running the piece backwards is the
    // same solid (a constant cross-section extrusion) with a POSITIVE determinant, and both sides still share
    // the one pooled template. Gated by src/render/parts/instanceMirror.test.ts.
    function steelPiece(ax, ay, bx, by, sign, zOff) {
      var len = Math.hypot(bx - ax, by - ay)
      var ang = Math.atan2(by - ay, bx - ax)
      // Rz(ang)·Ry(π) — a 180° turn about the run's own up axis; local +x → −run, +y → up, +z → −z
      if (sign < 0) return { position: [bx, by, -zOff], scale: [len, 1, 1], quaternion: [-Math.sin(ang / 2), Math.cos(ang / 2), 0, 0] }
      var inst = { position: [ax, ay, zOff], scale: [len, 1, 1] }
      if (Math.abs(ang) > 1e-9) inst.quaternion = [0, 0, Math.sin(ang / 2), Math.cos(ang / 2)]
      return inst
    }
    var frame = null, frameBends = null
    var railCutAt = railCutLookup(p)
    var railFills = []
    if (p.frameRails !== false) {
      // per-side spans clamped to the extents arc bounds (railArcL/R); with no overrides a rail spans its run exactly.
      var railInsts = []
      for (var ri = 0; ri < pathSplit.runs.length; ri++) {
        var run = pathSplit.runs[ri]
        for (var rsg2 = 0; rsg2 < 2; rsg2++) {
          var rSign = rsg2 === 0 ? -1 : 1
          var rArc = rSign === -1 ? railArcL : railArcR
          var rA = Math.max(run.s0, rArc[0]), rB = Math.min(run.s1, rArc[1])
          if (rB - rA < 1e-4) continue
          var rp0 = runAt(run, rA), rp1 = runAt(run, rB)
          // an extents end merged onto another conveyor is CUT to fit against that one's frame (_shared/
          // guardMitre.js, rows matched by plan X): the instanced rail stops square where the cut is deepest and fills,
          // built in the full piece's template frame (x from its origin end, z out from the bed edge), carry it on
          var rSlope = 1 / Math.max(Math.abs(Math.cos(Math.atan2(rp1[1] - rp0[1], rp1[0] - rp0[0]))), 0.25)
          var rcA = rA === rArc[0] ? railCutAt(rSign, rp0[0]) : null
          var rcB = rB === rArc[1] ? railCutAt(rSign, rp1[0]) : null
          if (rcA === null && rcB === null) { railInsts.push(steelPiece(rp0[0], rp0[1], rp1[0], rp1[1], rSign, hw)); continue }
          var rLen = rB - rA, rFull = steelPiece(rp0[0], rp0[1], rp1[0], rp1[1], rSign, hw)
          // [c, template x of the end, +1 when the piece lies at larger template x]; the right side's origin is a
          var rEnds = [[rcA, rSign > 0 ? 0 : rLen, rSign > 0 ? 1 : -1], [rcB, rSign > 0 ? rLen : 0, rSign > 0 ? -1 : 1]]
          var sqA = rA, sqB = rB
          for (var rei = 0; rei < 2; rei++) {
            if (rEnds[rei][0] === null) continue
            var rCut = railEndBands(rEnds[rei][1], rEnds[rei][2], rEnds[rei][0] * rSlope, FB)
            var pull = Math.abs(rCut.sq - rEnds[rei][1]) // how far the square end stands back from the cut end
            if (rei === 0) sqA = rA + pull
            else sqB = rB - pull
            for (var rbd = 0; rbd < rCut.bands.length; rbd++) {
              var rBand = rCut.bands[rbd]
              var rOutline = rBand.pts.map(function (q) { return [q[0], q[1] + 0.01] })
              railFills.push(g.transform(g.extrude(rOutline, rBand.y0, rBand.y1, { axis: 'y' }), { rotate: rFull.quaternion || [0, 0, 0, 1], translate: rFull.position }))
            }
          }
          if (sqB - sqA > 1e-4) { var sa2 = runAt(run, sqA), sb2 = runAt(run, sqB); railInsts.push(steelPiece(sa2[0], sa2[1], sb2[0], sb2[1], rSign, hw)) }
        }
      }
      if (railInsts.length) frame = { desc: railTemplate, finish: 'frame', instances: railInsts }
      var bendRails = []
      for (var bi2 = 0; bi2 < pathSplit.bends.length; bi2++) {
        for (var bsg = -1; bsg <= 1; bsg += 2) {
          var bArc = bsg === -1 ? railArcL : railArcR
          var bA = Math.max(pathSplit.bends[bi2].s0, bArc[0]), bB = Math.min(pathSplit.bends[bi2].s1, bArc[1])
          if (bB - bA < 1e-4) continue
          var bpoly = bendPolyline(pathSplit.bends[bi2], bA, bB)
          if (bpoly.length < 2) continue
          var z0 = bsg * hw, z1 = bsg * (hw + 0.01), z2 = bsg * (hw + 0.03)
          bendRails.push(g.sweep([[FB, z0], [FB, z1], [-0.005, z1], [-0.005, z0]], bpoly, CAPS))
          bendRails.push(g.sweep([[-0.005, z1], [-0.005, z2], [0, z2], [0, z1]], bpoly, CAPS))
        }
      }
      if (bendRails.length) frameBends = { desc: g.merge.apply(g, bendRails), finish: 'frame' }
    }

    // 3. SIDE GUARDS (steel) — a thin (0.005) wall just outside the rail (at hw + wall 0.01), rising from
    // −0.005 to 0.15 along the surface normal, its top edge turned OUTWARD into a 20 mm return (LIP) so it reads
    // as formed sheet steel. The return is visual: the host builds guard colliders from the shared guard
    // constants (core/beltGuards.ts), never from this profile. Independently toggled per side and split around any
    // guardOpenings, so a side is one-or-more spans, not a single ribbon. collision:'box' — the host gives
    // the kept spans static guard walls so cargo can't fall off.
    // the sub-polyline of a polyline between arc-lengths a..b (interpolated end points + the interior vertices).
    function subPolyline(poly, a, b) {
      function at(s) {
        var aa = 0
        for (var j = 1; j < poly.length; j++) {
          var seg = Math.hypot(poly[j][0] - poly[j - 1][0], poly[j][1] - poly[j - 1][1])
          if (aa + seg >= s || j === poly.length - 1) { var t = seg > 1e-9 ? (s - aa) / seg : 0; return [poly[j - 1][0] + (poly[j][0] - poly[j - 1][0]) * t, poly[j - 1][1] + (poly[j][1] - poly[j - 1][1]) * t, 0] }
          aa += seg
        }
        return [poly[poly.length - 1][0], poly[poly.length - 1][1], 0]
      }
      var pts = [at(a)], cum = 0
      for (var j = 1; j < poly.length; j++) { cum += Math.hypot(poly[j][0] - poly[j - 1][0], poly[j][1] - poly[j - 1][1]); if (cum > a + 1e-6 && cum < b - 1e-6) pts.push([poly[j][0], poly[j][1], 0]) }
      pts.push(at(b)); return pts
    }
    // the polyline a bend piece is swept along, a..b of the bend's range. A sweep squares its end to the last chord, and
    // the fillet's end chords turn short of the run, so a bend end met by a straight piece opened a wedge gap (~6 mm at
    // the bottom of the rail on a 15° bend). Such an end starts 1 mm back inside the straight piece, on the run.
    function bendPolyline(bend, a, b) {
      var pa = a === bend.s0 && a > 1e-4 ? a - 0.001 : a
      var pb = b === bend.s1 && b < frameLen - 1e-4 ? b + 0.001 : b
      return subPolyline(framePath, pa, pb)
    }
    // complementary KEPT spans of [0,total] after removing the opening ranges (sorted, clamped, merged).
    function keptSpans(total, ranges) {
      var rs = ranges.slice().sort(function (u, v) { return u[0] - v[0] }), spans = [], cur = 0
      for (var ri = 0; ri < rs.length; ri++) { var a = Math.max(0, rs[ri][0]), b = Math.min(total, rs[ri][1]); if (b <= a) continue; if (a > cur + 1e-4) spans.push([cur, a]); cur = Math.max(cur, b) }
      if (cur < total - 1e-4) spans.push([cur, total]); return spans
    }
    // Like the rails: guard pieces on straight runs are instances of a 1 m unit-guard template (z-local
    // 0..0.005, y −0.005..0.15), pieces crossing a fillet bend stay swept. A span straddling both is
    // intersected with the run/bend arc-ranges and each overlap emitted through its own channel.
    // the guard section, z measured outward from the guard's inner face: sheet 0..0.005, then the top return
    // out to LIP. Concave (an L), which the capped sweep triangulates properly.
    var LIP = 0.025, LIP_T = 0.005
    function guardSection(zIn, sign) {
      var z1 = zIn + sign * 0.005, z2 = zIn + sign * LIP
      return [[-0.005, zIn], [-0.005, z1], [0.15 - LIP_T, z1], [0.15 - LIP_T, z2], [0.15, z2], [0.15, zIn]]
    }
    var guardTemplate = g.sweep(guardSection(0, 1), UNIT_X, CAPS)
    // point at arc-length s within a straight run (collinear, so linear interpolation is exact)
    function runAt(run, s) {
      var t = (s - run.s0) / Math.max(run.s1 - run.s0, 1e-9)
      return [run.ax + (run.bx - run.ax) * t, run.ay + (run.by - run.ay) * t]
    }
    var guardInsts = [], guardSweeps = [], mitreFills = []
    // MITRED ENDS (_shared/guardMitre.js): where a guard meets the guard of a conveyor merged onto this one (or the
    // one this one merges onto), its end is cut on the plane the two share instead of square, so neither runs through
    // the other
    var mitreAt = mitreLookup(p)
    // the section between the square end an instanced piece stops at (the cut's deepest point, c*LIP in) and the cut
    // itself, in the unit template's frame (x along, y up, z outward from the inner face). xe = the end at the inner
    // face; hiEnd = the piece lies at x < xe.
    function mitreFill(xe, hiEnd, c) {
      var into = hiEnd ? -1 : 1, xs = xe + into * c * LIP, xt = xe + into * c * 0.005
      return g.merge(
        g.extrude([[xe, 0], [xt, 0.005], [xs, 0.005], [xs, 0]], -0.005, 0.15, { axis: 'y' }),
        g.extrude([[xt, 0.005], [xs, LIP], [xs, 0.005]], 0.15 - LIP_T, 0.15, { axis: 'y' }),
      )
    }
    var ops = Array.isArray(p.guardOpenings) ? p.guardOpenings : []
    var holes = Array.isArray(p.guardHoles) ? p.guardHoles : []
    var holePanels = {} // hole height → the panel instances cut at it (one pooled template per height)
    for (var gsi = 0; gsi < 2; gsi++) {
      var gside = gsi === 0 ? -1 : 1
      if (!(gside === -1 ? p.leftGuard !== false : p.rightGuard !== false)) continue
      var ranges = []
      // openings are arc-length from the belt tail; framePath starts rr (the drum extension) before it, so + rr.
      for (var oi = 0; oi < ops.length; oi++) { var sd = ops[oi][2]; if (sd === gside || sd === 0) ranges.push([ops[oi][0] + rr, ops[oi][1] + rr]) }
      // the extents retraction: drop everything outside this side's arc bounds (a flush-merged end)
      var gArc = gside === -1 ? railArcL : railArcR
      if (gArc[0] > 1e-4) ranges.push([-1, gArc[0]])
      if (gArc[1] < frameLen - 1e-4) ranges.push([gArc[1], frameLen + 1])
      // SENSOR-BEAM HOLES: a panel-long gap in the sheet, filled below by a panel with the hole cut through. Only
      // where the whole panel lands on one straight run, inside what the openings and extents leave standing; a
      // hole that would straddle a bend (or an opening) leaves the guard uncut there.
      var keptBefore = keptSpans(frameLen, ranges)
      for (var hi = 0; hi < holes.length; hi++) {
        var hrow = holes[hi]
        if (hrow[2] !== gside) continue
        var hs = hrow[0] + rr, h0 = hs - HOLE_PANEL / 2, h1 = hs + HOLE_PANEL / 2, hrun = null, inKept = false
        for (var hr = 0; hr < pathSplit.runs.length; hr++) { var cand = pathSplit.runs[hr]; if (h0 >= cand.s0 && h1 <= cand.s1) hrun = cand }
        for (var hk = 0; hk < keptBefore.length; hk++) if (h0 >= keptBefore[hk][0] && h1 <= keptBefore[hk][1]) inKept = true
        if (!hrun || !inKept) continue
        ranges.push([h0, h1])
        var hp = runAt(hrun, hs), hAng = Math.atan2(hrun.by - hrun.ay, hrun.bx - hrun.ax)
        var hKey = hrow[1].toFixed(4)
        if (!holePanels[hKey]) holePanels[hKey] = { y: hrow[1], insts: [] }
        // the panel's frame is the guard template's (outward +z); the −Z side is the same panel yawed 180° about
        // the run's up axis, like steelPiece — never a mirror scale
        holePanels[hKey].insts.push(gside > 0
          ? { position: [hp[0], hp[1], hw + 0.01], quaternion: [0, 0, Math.sin(hAng / 2), Math.cos(hAng / 2)] }
          : { position: [hp[0], hp[1], -(hw + 0.01)], quaternion: [-Math.sin(hAng / 2), Math.cos(hAng / 2), 0, 0] })
      }
      var gSection = guardSection(gside * (hw + 0.01), gside), spans = keptSpans(frameLen, ranges)
      for (var spi = 0; spi < spans.length; spi++) {
        var sp0 = spans[spi][0], sp1 = spans[spi][1]
        for (var ri2 = 0; ri2 < pathSplit.runs.length; ri2++) {
          var grun = pathSplit.runs[ri2]
          var oa = Math.max(sp0, grun.s0), ob = Math.min(sp1, grun.s1)
          if (ob - oa < 1e-4) continue
          var ga = runAt(grun, oa), gb = runAt(grun, ob)
          // a span end that meets another conveyor's guard is MITRED (its plan X matched against the host-fed rows,
          // which are plan X too): the instanced piece stops square where the cut is deepest and a fill carries the
          // section on out to the cut. A mitre is a PLAN retraction, so it stretches by 1/cos along a sloped run.
          var slopeK = 1 / Math.max(Math.abs(Math.cos(Math.atan2(gb[1] - ga[1], gb[0] - ga[0]))), 0.25)
          var cA = oa === sp0 ? mitreAt(gside, ga[0]) * slopeK : 0, cB = ob === sp1 ? mitreAt(gside, gb[0]) * slopeK : 0
          if ((cA + cB) * LIP >= ob - oa - 1e-4) cA = cB = 0 // too short to hold both cuts: stays square
          var sa = runAt(grun, oa + cA * LIP), sb = runAt(grun, ob - cB * LIP)
          guardInsts.push(steelPiece(sa[0], sa[1], sb[0], sb[1], gside, hw + 0.01))
          if (cA > 0 || cB > 0) {
            // the fills sit in the FULL piece's template frame (x from its origin end, z outward): the right side's
            // origin is a, the left side's is b (steelPiece runs it backwards under a 180 degree yaw)
            var fr = steelPiece(ga[0], ga[1], gb[0], gb[1], gside, hw + 0.01), fl = ob - oa
            var ends = [[cA, gside > 0 ? 0 : fl, gside < 0], [cB, gside > 0 ? fl : 0, gside > 0]]
            for (var ei = 0; ei < 2; ei++) {
              if (ends[ei][0] <= 0) continue
              mitreFills.push(g.transform(mitreFill(ends[ei][1], ends[ei][2], ends[ei][0]), { rotate: fr.quaternion || [0, 0, 0, 1], translate: fr.position }))
            }
          }
        }
        for (var bi3 = 0; bi3 < pathSplit.bends.length; bi3++) {
          var gbend = pathSplit.bends[bi3]
          var ba = Math.max(sp0, gbend.s0), bb = Math.min(sp1, gbend.s1)
          if (bb - ba < 1e-4) continue
          var gpoly = bendPolyline(gbend, ba, bb)
          if (gpoly.length >= 2) guardSweeps.push(g.sweep(gSection, gpoly, CAPS))
        }
      }
    }
    var guards = guardInsts.length ? { desc: guardTemplate, finish: 'guard', collision: 'box', instances: guardInsts } : null
    var guardBends = guardSweeps.length ? { desc: g.merge.apply(g, guardSweeps), finish: 'guard', collision: 'box' } : null
    // VISUAL ONLY, like the hole panels: the colliders keep square ends (cargo only meets the inner faces, which the
    // cut leaves where they were)
    var guardMitreFill = mitreFills.length ? { desc: g.merge.apply(g, mitreFills), finish: 'guard' } : null
    // the hole panels: one part per hole height, its instances every panel cut at it. VISUAL ONLY (no collision):
    // the host builds the guard's collider without the holes, so cargo still meets a whole wall.
    var holeParts = Object.keys(holePanels).sort().map(function (k) { return { desc: holePanel(g, holePanels[k].y, true), finish: 'guard', instances: holePanels[k].insts } })

    // deck Y at a plan-X station, interpolated between the bracketing path points: a straight incline run is
    // just its 2 endpoints, so nearest-point would snap a mid-run leg to a run end — out by its whole rise.
    function surfaceYAt(px) {
      for (var j = 1; j < path.length; j++) {
        if (px <= Math.max(path[j - 1][0], path[j][0]) || j === path.length - 1) {
          var dx = path[j][0] - path[j - 1][0]
          var t = Math.abs(dx) > 1e-9 ? Math.max(0, Math.min(1, (px - path[j - 1][0]) / dx)) : 0
          return path[j - 1][1] + (path[j][1] - path[j - 1][1]) * t
        }
      }
      return path[0][1]
    }
    var minX = Infinity, maxX = -Infinity
    for (var i = 0; i < path.length; i++) { if (path[i][0] < minX) minX = path[i][0]; if (path[i][0] > maxX) maxX = path[i][0] }
    var span = maxX - minX

    // arc-length from the tail to a plan-X station: the leg exclusion zone is in arc-length, which differs
    // from plan-X on an inclined run.
    function arcAtX(px) {
      var acc = 0
      for (var j = 1; j < path.length; j++) {
        var seg = Math.hypot(path[j][0] - path[j - 1][0], path[j][1] - path[j - 1][1]), x0 = path[j - 1][0], x1 = path[j][0]
        if (px <= x1 || j === path.length - 1) { var t = Math.abs(x1 - x0) > 1e-9 ? Math.max(0, Math.min(1, (px - x0) / (x1 - x0))) : 0; return acc + seg * t }
        acc += seg
      }
      return acc
    }

    // 4. SUPPORT LEGS — real floor supports (_shared/legs.js: channel uprights under the side frames, a
    // support channel across, mounting brackets, foot plates, telescoping inner legs, cross + knee braces), built
    // leg-local (floor at y=0, up to the leg height) then placed at each station with its foot on the surface below
    // THAT station: part-local −standHeight, shifted by the host-fed legRests row covering it, so the leg top still
    // meets the frame bottom (FB + the deck elevation there) while each foot stands on its own surface.
    var standH = typeof p.standHeight === 'number' && p.standHeight > 0 ? p.standHeight : 0.75
    var FLOOR_Y = -standH
    // Every support piece is a box → instances of one unit cube (size in scale, a knee brace turned about z), so
    // all the leg hardware in the scene draws as one pooled bank.
    var legInsts = []
    // Hex bolt heads — instances of one unit hex prism template (flat-topped, radius 1 in XY, depth 1 along
    // Z, centred): axis 'z' = identity, 'y' = a +90° X-rotation laying the prism axis along +Y. r/depth live
    // in each instance's scale.
    var hexSfc = g.surface()
    var hexF = [], hexB = []
    for (var hk = 0; hk < 6; hk++) {
      var ha = (hk / 6) * Math.PI * 2 + Math.PI / 6 // flat-topped
      var hu = Math.cos(ha), hwv = Math.sin(ha)
      hexF.push(hexSfc.vertex(hu, hwv, 0.5))
      hexB.push(hexSfc.vertex(hu, hwv, -0.5))
    }
    for (var hk = 1; hk < 5; hk++) { hexSfc.triangle(hexF[0], hexF[hk], hexF[hk + 1]); hexSfc.triangle(hexB[0], hexB[hk + 1], hexB[hk]) }
    for (var hk = 0; hk < 6; hk++) { var hk2 = (hk + 1) % 6; hexSfc.quad(hexF[hk], hexB[hk], hexB[hk2], hexF[hk2]) }
    var hexTemplate = hexSfc.build()
    var hexInsts = []
    function hexAt(cx, cy, cz, r, depth, axis) {
      var inst = { position: [cx, cy, cz], scale: [r, r, depth] }
      if (axis === 'y') inst.quaternion = [0.7071067811865476, 0, 0, 0.7071067811865476] // rotX(+90°): z-depth → +Y
      hexInsts.push(inst)
    }
    function legAt(x0, height, footY, dir) {
      var pc = legPieces(hw, height, dir, -FB)
      for (var i = 0; i < pc.boxes.length; i++) {
        var b = pc.boxes[i], inst = { position: [b[0] + x0, b[1] + footY, b[2]], scale: [b[3], b[4], b[5]] }
        if (b[6]) inst.quaternion = [0, 0, Math.sin(b[6] / 2), Math.cos(b[6] / 2)]
        legInsts.push(inst)
      }
      for (var j = 0; j < pc.bolts.length; j++) { var t = pc.bolts[j]; hexAt(t[0] + x0, t[1] + footY, t[2], t[3], t[4], t[5]) }
    }
    // Plan-X leg stations honouring the tail/head/middle toggles + per-end offsets/clearance + spacing, with
    // the exclusion zone removed. Tail-origin: offsets are plan-X; the middle cadence steps at absolute
    // multiples of legSpacing, not an even division.
    var rests = Array.isArray(p.legRests) ? p.legRests : []
    function restDyAt(lx) { for (var ri = 0; ri < rests.length; ri++) { var rw = rests[ri]; if (lx >= rw[0] && lx <= rw[1]) return rw[2] } return 0 }
    // knee braces lean toward the middle of the bed, and only where the deck is level: a brace reaching along a
    // tilted run would meet the frame a slope's rise away from where it was drawn to.
    function braceDir(lx) { return Math.abs(surfaceYAt(lx + 0.3) - surfaceYAt(lx - 0.3)) > 0.01 ? 0 : lx <= (minX + maxX) / 2 ? 1 : -1 }
    function placeLeg(lx) { var dy = restDyAt(lx); var lh = standH + FB + surfaceYAt(lx) - dy; if (lh > 0.05) legAt(lx, lh, FLOOR_Y + dy, braceDir(lx)) } // foot plane → frame bottom
    if (p.legs !== false) {
      var tailOff = typeof p.tailLegOffset === 'number' ? p.tailLegOffset : LEG_END_INSET
      var headOff = typeof p.headLegOffset === 'number' ? p.headLegOffset : LEG_END_INSET
      var tailClr = typeof p.tailLegClearance === 'number' ? p.tailLegClearance : LEG_CLEARANCE
      var headClr = typeof p.headLegClearance === 'number' ? p.headLegClearance : LEG_CLEARANCE
      var legSp = typeof p.legSpacing === 'number' && p.legSpacing > 0.1 ? p.legSpacing : LEG_SPACING
      var exS = typeof p.exclusionStart === 'number' ? p.exclusionStart : 0
      var exE = typeof p.exclusionEnd === 'number' ? p.exclusionEnd : 0
      var useExcl = exE > exS
      var tailX = minX + tailOff, headX = maxX - headOff
      var raw = []
      if (headX - tailX < 0.1) {
        if (p.tailLeg !== false || p.headLeg !== false) raw.push((minX + maxX) / 2) // short belt: one centred post
      } else {
        if (p.tailLeg !== false) raw.push(tailX)
        if (p.middleLegs !== false) {
          var loX = tailX + tailClr, hiX = headX - headClr // the middle cadence starts beyond each end's clearance
          for (var v = Math.ceil(loX / legSp) * legSp; v <= hiX + 1e-6; v += legSp) raw.push(v)
        }
        if (p.headLeg !== false) raw.push(headX)
      }
      for (var li = 0; li < raw.length; li++) {
        if (useExcl && arcAtX(raw[li]) >= exS && arcAtX(raw[li]) <= exE) continue
        placeLeg(raw[li])
      }
    }
    var legs = legInsts.length ? { desc: g.box([1, 1, 1], [0, 0, 0]), finish: 'leg', instances: legInsts } : null

    // 5. FRAME WEB-BOLTS — vertical hex bolt pairs every 1.2 m down each rail's mid-wall, following the
    // surface normal so an inclined run keeps them on the tilted wall. The pair closes up on a shallow wall so both
    // heads stay 3 mm inside it (the wall runs -0.005 .. FB); a 0.17 m belt keeps its 0.04. Floored above 0: the
    // pair loop below steps by 2 * bGap.
    var bSpace = 1.2, bZ = hw + 0.013, yMid = FB / 2, br = 0.012, bH = 0.01
    var bGap = Math.max(0.001,Math.min(0.04, -0.005 - 0.003 - br - yMid, yMid - br - 0.003 - FB))
    var pathLen = 0
    for (var i = 1; i < path.length; i++) pathLen += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
    // position + normal at an arc-length s, interpolated between points (a straight belt's filleted path is
    // only 2 corners, so nearest-point would clump the bolts at the ends).
    function sampleAt(s) {
      var acc = 0
      for (var j = 1; j < path.length; j++) {
        var dx = path[j][0] - path[j - 1][0], dy = path[j][1] - path[j - 1][1], seg = Math.hypot(dx, dy)
        if (acc + seg >= s || j === path.length - 1) {
          var t = seg > 1e-9 ? (s - acc) / seg : 0, l = seg || 1
          return { x: path[j - 1][0] + dx * t, y: path[j - 1][1] + dy * t, nx: -dy / l, ny: dx / l }
        }
        acc += seg
      }
      return { x: path[0][0], y: path[0][1], nx: 0, ny: 1 }
    }
    if (p.frameRails !== false) { // no frame ⇒ no web-bolts (the leg bolts still stand)
      var nB = Math.max(2, Math.round(pathLen / bSpace))
      for (var bi = 0; bi < nB; bi++) {
        var smp = sampleAt(((bi + 0.5) / nB) * pathLen)
        for (var bs = -1; bs <= 1; bs += 2) {
          for (var bd = -bGap; bd <= bGap; bd += 2 * bGap) hexAt(smp.x + smp.nx * (yMid + bd), smp.y + smp.ny * (yMid + bd), bs * bZ, br, bH, 'z')
        }
      }
    }
    var bolts = hexInsts.length ? { desc: hexTemplate, finish: 'bolt', instances: hexInsts } : null

    // stable emit order — the host reconciles instanced banks by index — dropping the parts a toggle removed.
    var parts = [bed]
    if (bedWraps) parts.push(bedWraps)
    if (frame) parts.push(frame)
    if (frameBends) parts.push(frameBends)
    if (guards) parts.push(guards)
    if (guardBends) parts.push(guardBends)
    if (legs) parts.push(legs)
    if (bolts) parts.push(bolts)
    // hole panels LAST: they come and go with the sensors in the scene, and the host reconciles instanced banks by
    // index, so appending them leaves every other part's bank where it was
    for (var hpi = 0; hpi < holeParts.length; hpi++) parts.push(holeParts[hpi])
    // the mitre fills after them, for the same reason: they come and go with the junctions
    if (guardMitreFill) parts.push(guardMitreFill)
    if (railFills.length) parts.push({ desc: g.merge.apply(g, railFills), finish: 'frame' })
    return parts
  },
  step(ctx) {
    // Tag precedence: speedTag (REAL in) replaces the speed param as the commanded speed; runTag (BOOL)
    // gates it to 0, but ONLY while a controller actually drives the tag (ctx.tagDriven, output ownership) —
    // undriven, the authored speed rules; runningTag (BOOL out) = effective speed ≠ 0, written every step.
    // the unit the conveyor is set up in: everything below this line is m/s
    const cmd = commandedSpeed(ctx)
    const fpm = cmd.fpm, commanded = cmd.commanded
    const running = ctx.tagDriven(ctx.params.runTag) ? ctx.readTag(ctx.params.runTag) : true
    const s = rampedSpeed(ctx, drive, cmd, running ? commanded : 0)
    // the readout the Inspector shows for 'speed' while a setpoint tag owns it: the EFFECTIVE value,
    // gates and all, not the raw setpoint (a runTag holding this at 0 must not read as the commanded rate)
    reportSpeed(ctx, fpm, s)
    if (ctx.params.runningTag) ctx.writeTag(ctx.params.runningTag, s !== 0)
    // drive feedback: the velocity as a share of the speed at 30, an encoder pulse and the odometer
    publishDrive(ctx, drive, cmd, s)
    // flow axis = the part's local +X in world space; the host redistributes this speed along each segment's
    // own tangent, so cargo is carried up/over an incline too.
    ctx.setSurfaceVelocity({ x: ctx.forward.x * s, y: 0, z: ctx.forward.z * s })
  },
})
