// Box — a piece of authored cargo. Demonstrates the cargo geometry kind: the package geometry declares
// { kind: 'cargo', cargoKind: 'box' } and the host builds the part as one dynamic physics body sized/tinted
// from the params below (instanced batch render, gizmo grab, pilot carry). There is nothing to simulate
// here: cargo is passive payload, so step() is empty.

definePart({
  params: {
    // size drives both the render scale and the dynamic body's half-extents (centre origin). Each carries a
    // face handle, so a placed box shows a resize dot on all six faces; the host holds the opposite face.
    length: { type: 'number', default: 0.6, min: 0.1, step: 0.05, label: 'Length (m)', handle: { kind: 'face', axis: 'x' }, desc: 'Extent along local X. Drives the collision body as well as the visual, and the box is centred on its origin.' },
    width: { type: 'number', default: 0.4, min: 0.1, step: 0.05, label: 'Width (m)', handle: { kind: 'face', axis: 'z' }, desc: 'Extent along local Z. Drives the collision body as well as the visual.' },
    height: { type: 'number', default: 0.4, min: 0.1, step: 0.05, label: 'Height (m)', handle: { kind: 'face', axis: 'y' }, desc: 'Extent along local Y. Drives the collision body as well as the visual.' },
    mass: { type: 'number', default: 10, min: 0.5, max: 100, step: 0.5, label: 'Mass (kg)', desc: 'Physical mass. Heavier cargo is harder for a conveyor to accelerate and pushes lighter cargo out of the way.' },
    color: { type: 'color', default: '#ffffff', label: 'Color', desc: 'Tint over the cardboard texture. White leaves it untinted.' },
  },
  step() {
  },
})
