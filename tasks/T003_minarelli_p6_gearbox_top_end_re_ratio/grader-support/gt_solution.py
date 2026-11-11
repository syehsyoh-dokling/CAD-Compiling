"""
GT reference solution: Minarelli P6 gearbox top-end re-ratio (hard T5 + coupled).

Task (intent only; the solver must INFER every number):
  - The gearbox mainshaft carries a constant-mesh cluster of six spur gears.
    Make the top two gears "one tooth-step taller" (raise the top-end gearing)
    while keeping each gear meshing with its (unchanged) countershaft partner.
  - Each gear runs on a fixed shaft centre distance, so the tooth COUNTS of a
    meshing pair must keep summing to the same value (centre distance + module
    preserved). Dropping one mainshaft tooth therefore adds one to its partner.
  - The whole six-gear ratio ladder must stay strictly monotonic, the existing
    module / pressure angle are preserved, and every gear keeps its bore, face
    width and the shaft axis. The other four gears and all other parts are
    untouched.

Inference chain (NOT given in the prompt):
  - Measured from the seed, mainshaft axis = global X through (Y=4.48, Z=86.36).
    The six involute spur gears read 33, 30, 27, 25, 23, 21 teeth; tip-derived
    module m = tip/(z+2) = 1.766 mm, 20 deg pressure angle.
  - Shaft-to-clutch centre distance = 38 mm -> for a meshing pair
    z_main + z_counter = 2*CD/m = 43 (constant). So each mainshaft change of -1
    tooth is matched by +1 on the partner; the centre distance is held.
  - "Top two gears, one step taller" -> the two smallest mainshaft gears
    (5th = 23T, 6th = 21T). One tooth taller = one FEWER mainshaft tooth each:
       5th: 23T -> 22T  (partner 20 -> 21)
       6th: 21T -> 20T  (partner 22 -> 23)
    New ladder 33,30,27,25,22,20 is still strictly monotonic (the coupling: the
    new 5th count must stay above the new 6th and below the 4th=25).
  - Derived gear geometry (standard full-depth involute, m = 1.766):
       5th 22T: pitch Ø38.85, tip Ø42.38, root Ø34.44, bore Ø18.0, face 8.0
       6th 20T: pitch Ø35.32, tip Ø38.85, root Ø30.91, bore Ø15.0, face 9.0

Implementation: the two old gear solids are identified by geometry (on the
mainshaft axis, at their measured axial stations and tip-diameter band), removed,
and replaced by freshly cut involute gears at the same axis / axial span / bore /
face width. The other 114 solids are carried through unchanged.
"""

from __future__ import annotations

import math
import os

import cadquery as cq


INPUT_STEP = os.environ.get("INPUT_STEP", "/workspace/files/problem/model.step")
OUTPUT_STEP = os.environ.get("OUTPUT_STEP", "/workspace/output/solution.step")
OUTPUT_PY = os.environ.get("OUTPUT_PY", "/workspace/output/solution.py")

# --- preserved datum: gearbox mainshaft axis (measured from the seed) ---------
AXIS_Y = 4.48
AXIS_Z = 86.36

# --- gear family (measured from the seed cluster) -----------------------------
MODULE = 1.766                       # tip-derived module, preserved (mesh)
PRESSURE_ANGLE = math.radians(20.0)
ADDENDUM_FACTOR = 1.0
DEDENDUM_FACTOR = 1.25

# --- target re-cut gears (derived from the inference chain above) -------------
# 5th gear: 23T -> 22T at its station; 6th gear: 21T -> 20T at its station.
GEAR_5TH = {
    "teeth_new": 22, "face": 8.0, "bore_d": 18.0,
    "x_start": -64.2, "cx": -60.2, "tip_band": (42.0, 46.0),
}
GEAR_6TH = {
    "teeth_new": 20, "face": 9.0, "bore_d": 15.0,
    "x_start": -38.8, "cx": -34.3, "tip_band": (38.0, 43.0),
}

FLANK_POINTS = 16
TIP_POINTS = 4
ROOT_POINTS = 4


def involute_function(angle: float) -> float:
    """Standard involute function inv(a) = tan(a) - a."""

    return math.tan(angle) - angle


def gear_section_points(teeth: int, module: float) -> list[tuple[float, float]]:
    """Closed outer profile of a full involute spur gear as ordered (x, y) points."""

    pitch_radius = module * teeth / 2.0
    base_radius = pitch_radius * math.cos(PRESSURE_ANGLE)
    tip_radius = pitch_radius + ADDENDUM_FACTOR * module
    root_radius = pitch_radius - DEDENDUM_FACTOR * module

    beta = math.pi / (2.0 * teeth) + involute_function(PRESSURE_ANGLE)
    flank_start = max(root_radius, base_radius)

    radii = [
        flank_start + (tip_radius - flank_start) * i / (FLANK_POINTS - 1)
        for i in range(FLANK_POINTS)
    ]

    def flank_angle(radius: float) -> float:
        ratio = max(-1.0, min(1.0, base_radius / radius))
        pressure_at_r = math.acos(ratio)
        return beta - involute_function(pressure_at_r)

    right_flank = [
        (radius * math.cos(flank_angle(radius)), radius * math.sin(flank_angle(radius)))
        for radius in radii
    ]
    left_flank = [(x, -y) for (x, y) in right_flank]

    tip_angle = flank_angle(tip_radius)
    root_angle = beta

    one_tooth: list[tuple[float, float]] = []
    if root_radius < base_radius:
        one_tooth.append(
            (root_radius * math.cos(root_angle), -root_radius * math.sin(root_angle))
        )
    one_tooth.extend(left_flank)
    for i in range(1, TIP_POINTS):
        ang = -tip_angle + (2.0 * tip_angle) * i / TIP_POINTS
        one_tooth.append((tip_radius * math.cos(ang), tip_radius * math.sin(ang)))
    one_tooth.extend(reversed(right_flank))
    if root_radius < base_radius:
        one_tooth.append(
            (root_radius * math.cos(root_angle), root_radius * math.sin(root_angle))
        )

    points: list[tuple[float, float]] = []
    tooth_pitch = 2.0 * math.pi / teeth
    for k in range(teeth):
        rot = k * tooth_pitch
        cos_r, sin_r = math.cos(rot), math.sin(rot)
        for (x, y) in one_tooth:
            points.append((x * cos_r - y * sin_r, x * sin_r + y * cos_r))
        start_ang = rot + root_angle
        end_ang = (k + 1) * tooth_pitch - root_angle
        for i in range(1, ROOT_POINTS):
            ang = start_ang + (end_ang - start_ang) * i / ROOT_POINTS
            points.append((root_radius * math.cos(ang), root_radius * math.sin(ang)))

    return points


def build_spur_gear(teeth: int, module: float, face: float, bore_d: float) -> cq.Workplane:
    """Build one bored involute spur gear, axis along Z, spanning z=0..face."""

    profile = gear_section_points(teeth, module)
    gear = cq.Workplane("XY").polyline(profile).close().extrude(face)
    gear = gear.faces(">Z").workplane(centerOption="CenterOfBoundBox").hole(bore_d)
    return gear


def place_on_mainshaft(gear: cq.Workplane, x_start: float):
    """Rotate the gear's Z axis onto global X and translate to its mainshaft station."""

    g = gear.rotate((0, 0, 0), (0, 1, 0), 90.0)       # Z axis -> +X axis, spans 0..face
    g = g.translate((x_start, AXIS_Y, AXIS_Z))
    return g.val()


def find_target_gear(solids: list, spec: dict) -> int:
    """Locate the cluster gear solid on the mainshaft axis at the given station."""

    matches = []
    for i, s in enumerate(solids):
        c = s.Center()
        if math.hypot(c.y - AXIS_Y, c.z - AXIS_Z) > 5.0:
            continue
        b = s.BoundingBox()
        tip = max(b.ylen, b.zlen)
        if abs(c.x - spec["cx"]) <= 4.0 and spec["tip_band"][0] <= tip <= spec["tip_band"][1]:
            matches.append(i)
    assert len(matches) == 1, f"expected 1 target gear at x={spec['cx']}, found {matches}"
    return matches[0]


def main() -> None:
    """Build, validate, and export the re-ratioed assembly + a copy of this script."""

    asm = cq.importers.importStep(INPUT_STEP).val()
    solids = asm.Solids()
    n_in = len(solids)
    print(f"[gt] loaded assembly: {n_in} solids")

    idx_5th = find_target_gear(solids, GEAR_5TH)
    idx_6th = find_target_gear(solids, GEAR_6TH)
    print(f"[gt] target gears: 5th=solid#{idx_5th} (23T->22T), 6th=solid#{idx_6th} (21T->20T)")

    keep = [s for i, s in enumerate(solids) if i not in (idx_5th, idx_6th)]

    new_5th = place_on_mainshaft(
        build_spur_gear(GEAR_5TH["teeth_new"], MODULE, GEAR_5TH["face"], GEAR_5TH["bore_d"]),
        GEAR_5TH["x_start"],
    )
    new_6th = place_on_mainshaft(
        build_spur_gear(GEAR_6TH["teeth_new"], MODULE, GEAR_6TH["face"], GEAR_6TH["bore_d"]),
        GEAR_6TH["x_start"],
    )

    for tag, gear, spec in (("5th", new_5th, GEAR_5TH), ("6th", new_6th, GEAR_6TH)):
        assert gear.isValid(), f"{tag} rebuilt gear is not a valid solid"
        b = gear.BoundingBox()
        tip_d = MODULE * (spec["teeth_new"] + 2.0 * ADDENDUM_FACTOR)
        assert abs(b.ylen - tip_d) < 1.0, f"{tag} tip Y off: {b.ylen:.3f} vs {tip_d:.3f}"
        assert abs(b.zlen - tip_d) < 1.0, f"{tag} tip Z off: {b.zlen:.3f} vs {tip_d:.3f}"
        assert abs(b.xlen - spec["face"]) < 0.3, f"{tag} face off: {b.xlen:.3f}"

    result = cq.Compound.makeCompound(keep + [new_5th, new_6th])
    assert result.isValid(), "assembled result is not valid"
    assert len(result.Solids()) == n_in, f"solid count changed: {len(result.Solids())} != {n_in}"
    assert result.Volume() > 0, "assembled result has non-positive volume"
    print(f"[gt] reassembled: {len(result.Solids())} solids, volume {result.Volume():.1f} mm^3")

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
