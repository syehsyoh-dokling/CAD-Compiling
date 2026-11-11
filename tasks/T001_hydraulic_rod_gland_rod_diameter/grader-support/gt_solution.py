"""
GT reference solution: hydraulic rod-gland rod-diameter retrofit (hard T4/T5, coupled).

Task (intent only; the solver must INFER which features move and by how much):
  - The cylinder is being rebuilt for a larger piston rod, in the SAME tube. The
    gland's whole internal rod bore (every feature that references the rod: the
    wiper pocket + its retention groove, the rod guide lands, the rod-seal groove,
    the main bore, the inboard lead-in and counterbore) must be re-cut to suit the
    bigger rod, preserving every radial running clearance and every seal/wiper
    groove cross-section, and keeping the axial layout.
  - Everything that references the cylinder TUBE, not the rod, is frozen: the
    mounting thread, the flange head OD and its spanner notches, the pilot
    register and its lead-in, both end faces and the overall length.

Inference chain (NOT spelled out in the prompt):
  - Axis = global X through (Y=0, Z=0); length 75 mm, X in [-37.5, 37.5].
  - The smallest internal lands (Ø51.5) guide the current rod; rod nominal Ø50,
    so every internal diameter is a fixed offset above the rod (guide clearance,
    seal section, wiper pocket, counterbore clearance).
  - Rod grows Ø50 -> Ø56 (a +6 mm diameter step). Preserving every clearance and
    every groove section means EVERY internal diameter grows by the same +6 mm
    (radius +3 mm); axial positions are unchanged. The thread/flange/register are
    tube-referenced and do not move.

Measured original bore bands (radius before edit), outboard X- to inboard X+:
   mouth land        X[-37.50,-35.00]  r 31.000  (Ø62.0)
   wiper retain grv  X[-35.00,-33.30]  r 32.250  (Ø64.5)
   wiper pocket land X[-33.30,-26.00]  r 31.000  (Ø62.0)
   rod guide land    X[-26.00,-21.00]  r 25.750  (Ø51.5)
   rod-seal groove   X[-21.00,-11.00]  r 30.000  (Ø60.0)
   rod guide land    X[-11.00, -7.50]  r 25.750  (Ø51.5)
   main bore         X[ -7.50, 21.19]  r 27.500  (Ø55.0)
   30deg lead-in     X[ 21.19, 25.50]  r 27.5 -> 29.985
   inboard counterb. X[ 25.50, 37.50]  r 29.985  (Ø60.0)

Implementation: the new bore is the original profile with every radius +3 mm. Because
the new radius is >= the old radius at every X, the new bore VOID strictly contains the
old void, so cutting a revolve of the new bore profile from the imported solid fully
replaces the bore and leaves the thread, flange, notches, register and end faces exactly
as imported. No external feature is touched.
"""

from __future__ import annotations

import math
import os

import cadquery as cq


INPUT_STEP = os.environ.get("INPUT_STEP", "/workspace/files/problem/model.step")
OUTPUT_STEP = os.environ.get("OUTPUT_STEP", "/workspace/output/solution.step")
OUTPUT_PY = os.environ.get("OUTPUT_PY", "/workspace/output/solution.py")

# --- preserved datum: gland / rod bore axis (measured from the seed) ----------
AXIS_Y = 0.0
AXIS_Z = 0.0
X_OUTBOARD = -37.5         # flange (rod-exit / atmosphere) end face
X_INBOARD = 37.5           # register (oil / pressure) end face

# --- retrofit driver ----------------------------------------------------------
ROD_OLD_D = 50.0           # current rod nominal Ø (guide lands Ø51.5 = rod + 1.5)
ROD_NEW_D = 56.0           # one standard size up
DR = (ROD_NEW_D - ROD_OLD_D) / 2.0   # +3.0 mm radius on every rod-referenced bore

# --- measured original bore: (x_lo, x_hi, r_old). The 30deg cone between the
# main bore and the counterbore is interpolated linearly (its half-angle is set
# by the two cylinder radii it joins, so a straight (x, r) segment reproduces it).
BORE_BANDS = [
    (-37.50, -35.00, 31.000),   # mouth land
    (-35.00, -33.30, 32.250),   # wiper retention groove
    (-33.30, -26.00, 31.000),   # wiper pocket land
    (-26.00, -21.00, 25.750),   # rod guide land (outboard)
    (-21.00, -11.00, 30.000),   # rod-seal groove
    (-11.00, -7.500, 25.750),   # rod guide land (inboard)
    (-7.500, 21.190, 27.500),   # main bore
    # cone 21.19 -> 25.50 : r 27.5 -> 29.985 (handled as a segment below)
    (25.500, 37.500, 29.985),   # inboard counterbore
]
CONE = (21.190, 25.500, 27.500, 29.985)   # x_lo, x_hi, r_lo, r_hi

EXT = 2.5   # extend the cutting void past both end faces so the bore is fully open


def new_radius(r_old: float) -> float:
    """New bore radius for the larger rod: every internal Ø grows by the rod step."""

    return r_old + DR


def bore_void_profile() -> list[tuple[float, float]]:
    """Closed (x, r) polygon of the NEW bore void, revolved later about the X axis.

    Upper boundary = new bore wall (old radius + DR) left->right with vertical
    steps at each band edge; lower boundary returns along the axis (r = 0). The
    ends are extended by EXT past the faces so the cut opens a clean through bore.
    """

    pts: list[tuple[float, float]] = []
    r_first = new_radius(BORE_BANDS[0][2])
    pts.append((X_OUTBOARD - EXT, r_first))   # extended outboard mouth

    prev_r = r_first
    for x_lo, x_hi, r_old in BORE_BANDS[:-1]:
        r_new = new_radius(r_old)
        if r_new != prev_r:
            pts.append((x_lo, r_new))          # vertical step at the band edge
        pts.append((x_hi, r_new))              # run along this band
        prev_r = r_new
        # insert the conical lead-in right after the main bore band
        if abs(x_hi - CONE[0]) < 1e-6:
            r_cone_hi = new_radius(CONE[3])
            pts.append((CONE[1], r_cone_hi))   # straight 30deg segment to counterbore
            prev_r = r_cone_hi

    # final band (counterbore) + extended inboard end
    x_lo, x_hi, r_old = BORE_BANDS[-1]
    r_new = new_radius(r_old)
    if r_new != prev_r:
        pts.append((x_lo, r_new))
    pts.append((x_hi, r_new))
    pts.append((X_INBOARD + EXT, r_new))

    # close along the axis
    pts.append((X_INBOARD + EXT, 0.0))
    pts.append((X_OUTBOARD - EXT, 0.0))
    return pts


def inner_radius(shape, x: float, n: int = 700, r_max: float = 45.0) -> float:
    """First (smallest) radius with material on the YZ ring at station x (bore wall)."""

    best = r_max
    for theta in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        for k in range(n + 1):
            r = r_max * k / n
            p = cq.Vector(x, AXIS_Y + r * math.cos(theta), AXIS_Z + r * math.sin(theta))
            if shape.isInside(p, 1e-3):
                best = min(best, r)
                break
    return best


def main() -> None:
    """Build, validate, and export the re-bored gland + a copy of this script."""

    base = cq.importers.importStep(INPUT_STEP).val()
    assert len(base.Solids()) == 1, f"expected 1 solid, found {len(base.Solids())}"
    vol_in = base.Volume()
    bb_in = base.BoundingBox()
    print(f"[gt] loaded gland: vol {vol_in:.1f} mm^3, length {bb_in.xlen:.2f} mm")

    profile = bore_void_profile()
    void = (
        cq.Workplane("XY")
        .polyline(profile)
        .close()
        .revolve(360.0, (0, 0, 0), (1, 0, 0))
        .val()
    )
    assert void.isValid(), "bore void is not a valid solid"

    result = base.cut(void)
    assert result.isValid(), "re-bored gland is not a valid solid"
    assert len(result.Solids()) == 1, f"solid count changed: {len(result.Solids())}"
    vol_out = result.Volume()
    assert vol_out > 0, "result has non-positive volume"
    assert vol_out < vol_in, "no material removed (bore did not grow)"

    # external envelope must be untouched (tube-referenced features frozen)
    bb_out = result.BoundingBox()
    assert abs(bb_out.xlen - bb_in.xlen) < 0.05, f"length changed: {bb_out.xlen:.3f}"
    assert abs(bb_out.ylen - bb_in.ylen) < 0.1, f"flange OD(y) changed: {bb_out.ylen:.3f}"
    assert abs(bb_out.zlen - bb_in.zlen) < 0.1, f"flange OD(z) changed: {bb_out.zlen:.3f}"

    # spot-check two new internal diameters: main bore -> Ø61, rod-seal groove -> Ø66
    main_bore_d = 2.0 * inner_radius(result, 5.0)
    seal_groove_d = 2.0 * inner_radius(result, -16.0)
    print(f"[gt] new main bore Ø{main_bore_d:.2f} (exp 61.0), "
          f"seal groove Ø{seal_groove_d:.2f} (exp 66.0)")
    assert abs(main_bore_d - 61.0) < 0.6, f"main bore off: Ø{main_bore_d:.3f}"
    assert abs(seal_groove_d - 66.0) < 0.6, f"seal groove off: Ø{seal_groove_d:.3f}"

    print(f"[gt] re-bored: vol {vol_out:.1f} mm^3 (removed {vol_in - vol_out:.1f})")

    os.makedirs(os.path.dirname(OUTPUT_STEP) or ".", exist_ok=True)
    cq.exporters.export(result, OUTPUT_STEP)
    print(f"[gt] exported {OUTPUT_STEP}")

    try:
        import shutil

        os.makedirs(os.path.dirname(OUTPUT_PY) or ".", exist_ok=True)
        shutil.copy(__file__, OUTPUT_PY)
    except OSError as exc:
        print(f"[gt] note: could not copy script to {OUTPUT_PY}: {exc}")


if __name__ == "__main__":
    main()
