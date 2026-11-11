"""Golden reference solution: retrofit the pillow block from a 6204 to a 6205 bearing.

Reads the task input (INPUT_STEP, default /workspace/files/problem/model.step), applies the edits and writes
OUTPUT_STEP (default /workspace/output/solution.step). The edits, in the part's coordinates (shaft axis along +Y
through X=0, Z=33; front face Y=0):

  1. Bearing seat Ø52.000 (6205: d25 x D52 x B15) from the front face to a new shoulder at Y=19.15
     (2.00 lip + 2.15 retaining-ring groove + 15.00 bearing width).
  2. Shaft passage Ø33.0 from the shoulder to the back face.
  3. DIN 472-52 internal retaining-ring groove: Ø55.0, width 2.15, from Y=2.00 to Y=4.15, so its inner flank
     is flush with the bearing's front face.
  4. Lead-in chamfer 1.0 x 45° at the mouth of the seat (Ø54.0 at the front face down to Ø52.0 at Y=1.0).
  5. The two Ø11 mounting holes become belt-tension slots: width 11.0, arc centres at X=±39 and X=±51
     (12 mm apart, centred on the old holes at X=±45, Y=15), 23 mm end to end, through the base.
Everything else (base, pedestal, boss, envelope 120 x 30 x 68) stays as it was.
"""
from __future__ import annotations

import os

import cadquery as cq

INPUT_STEP = os.environ.get("INPUT_STEP", "/workspace/files/problem/model.step")
OUTPUT_STEP = os.environ.get("OUTPUT_STEP", "/workspace/output/solution.step")

AXIS_Z = 33.0
SEAT_D, SHOULDER_Y = 52.0, 19.15
PASSAGE_D = 33.0
GROOVE_D, GROOVE_Y0, GROOVE_W = 55.0, 2.00, 2.15
CHAMFER = 1.0
SLOT_W, SLOT_PITCH, SLOT_CENTRES_X, SLOT_Y = 11.0, 12.0, (-45.0, 45.0), 15.0


def cyl_y(radius: float, y0: float, y1: float) -> cq.Solid:
    return cq.Solid.makeCylinder(radius, y1 - y0, cq.Vector(0, y0, AXIS_Z), cq.Vector(0, 1, 0))


def slot(x_mid: float, width: float = SLOT_W, pitch: float = SLOT_PITCH) -> cq.Solid:
    """A stadium-shaped slot through the base (Z -1..16), long axis along X; pitch 0 gives a round hole."""
    half = pitch / 2
    r = width / 2
    a = cq.Solid.makeCylinder(r, 17.0, cq.Vector(x_mid - half, SLOT_Y, -1.0), cq.Vector(0, 0, 1))
    if pitch <= 0:
        return a
    b = cq.Solid.makeCylinder(r, 17.0, cq.Vector(x_mid + half, SLOT_Y, -1.0), cq.Vector(0, 0, 1))
    mid = cq.Solid.makeBox(pitch, width, 17.0, cq.Vector(x_mid - half, SLOT_Y - r, -1.0))
    return a.fuse(b, mid).clean()


def retrofit(part: cq.Shape, seat_d: float = SEAT_D, shoulder_y: float = SHOULDER_Y, passage_d: float = PASSAGE_D,
             groove_d: float | None = GROOVE_D, groove_y0: float = GROOVE_Y0, groove_w: float = GROOVE_W,
             chamfer: float = CHAMFER, slot_w: float = SLOT_W, slot_pitch: float = SLOT_PITCH) -> cq.Shape:
    """The golden edit. The keyword arguments exist only so the harness can build deliberately wrong variants."""
    tools = [cyl_y(seat_d / 2, -1.0, shoulder_y), cyl_y(passage_d / 2, -1.0, 31.0)]
    if groove_d:
        tools.append(cyl_y(groove_d / 2, groove_y0, groove_y0 + groove_w))
    if chamfer > 0:
        # 45° lead-in: radius seat_d/2 + chamfer at Y=0, seat_d/2 at Y=chamfer (cone extended 1 mm in front of the face)
        tools.append(cq.Solid.makeCone(seat_d / 2 + chamfer + 1.0, seat_d / 2, chamfer + 1.0, cq.Vector(0, -1.0, AXIS_Z), cq.Vector(0, 1, 0)))
    tools += [slot(x, slot_w, slot_pitch) for x in SLOT_CENTRES_X]
    return part.cut(*tools).clean()


def main() -> None:
    part = cq.importers.importStep(INPUT_STEP).val()
    result = retrofit(part)
    os.makedirs(os.path.dirname(OUTPUT_STEP) or ".", exist_ok=True)
    cq.exporters.export(cq.Workplane().add(result), OUTPUT_STEP)
    print(f"solution written: {OUTPUT_STEP}  volume={result.Volume():.1f} mm3  valid={result.isValid()}")


if __name__ == "__main__":
    main()
