"""
GT reference solution: NEMA 23 -> NEMA 17 motor-swap retrofit (T4).

Task: the SFU1204 ballscrew support already mounts a NEMA 23 motor (Ø38.1 pilot
bore + four Ø5 holes on a 47.14 mm square). The drive is being changed to a
smaller NEMA 17 motor, so the motor-mount face (the base plate) needs the NEMA 17
bolt pattern added: four M3 clearance holes on a 31.0 mm square, centered on the
ballscrew axis, drilled through the base plate parallel to the screw axis. The
existing NEMA 23 holes are left in place (dual-pattern mount), and the ballscrew
bearing seat, the Ø38.1 coupling bore, the side frame-mounting holes, and the
overall envelope are all preserved.

Seed geometry (measured from problem_files/model.step):
  - ballscrew / motor axis = global Z, through (X=0, Y=0)
  - base plate (motor-mount face) spans Z in [-71.5, -61.5] (10 mm thick)
  - central Ø38.1 mm pilot/coupling bore on the axis (preserved)
  - existing NEMA 23 pattern: 4x Ø5 holes near (+-23.5, +-23.5) (preserved)
  - ballscrew bearing seat + retainer plate on the top plate (preserved)

Edit (standard-driven, derived from NEMA 17 + ISO 273):
  - NEMA 17 mounting pattern = 31.0 mm square -> hole centers at (+-15.5, +-15.5)
  - M3 clearance hole, ISO 273 "medium" fit = Ø3.4 mm
  - drilled parallel to the motor axis (Z) through the base plate
  - centered on the ballscrew axis so the NEMA 17 motor stays coaxial with the
    screw (the bolt pattern, not a pilot, locates the smaller motor; the existing
    Ø38.1 bore is larger than the NEMA 17 Ø22 register and stays as coupling
    clearance)
"""

from __future__ import annotations

import os

import cadquery as cq


# --- paths (overridable for local authoring; platform uses the defaults) -----
INPUT_STEP = os.environ.get("INPUT_STEP", "/workspace/files/problem/model.step")
OUTPUT_STEP = os.environ.get("OUTPUT_STEP", "/workspace/output/solution.step")
OUTPUT_PY = os.environ.get("OUTPUT_PY", "/workspace/output/solution.py")

# --- NEMA 17 interface parameters --------------------------------------------
NEMA17_PATTERN = 31.0           # mm, square bolt-pattern pitch (NEMA 17 standard)
PATTERN_HALF = NEMA17_PATTERN / 2.0   # 15.5 mm, hole offset from the axis
M3_CLEARANCE_DIA = 3.4          # mm, M3 medium clearance (ISO 273)
M3_CLEARANCE_R = M3_CLEARANCE_DIA / 2.0

# Ballscrew / motor axis (measured: central pilot bore and bearing are on (0,0)).
AXIS_X = 0.0
AXIS_Y = 0.0

# Base-plate (motor-mount face) axial band, measured from the seed.
BASE_PLATE_Z_MIN = -71.5        # motor-mount face
BASE_PLATE_Z_MAX = -61.5        # cavity-side face of the base plate
CUT_MARGIN = 0.6                # over-travel so the drill breaks through cleanly


def hole_positions() -> list[tuple[float, float]]:
    """Return the four NEMA 17 hole centers, square pattern about the axis."""

    return [
        (AXIS_X + PATTERN_HALF, AXIS_Y + PATTERN_HALF),
        (AXIS_X + PATTERN_HALF, AXIS_Y - PATTERN_HALF),
        (AXIS_X - PATTERN_HALF, AXIS_Y + PATTERN_HALF),
        (AXIS_X - PATTERN_HALF, AXIS_Y - PATTERN_HALF),
    ]


def build_solution() -> cq.Compound:
    """Load the seed and drill the NEMA 17 clearance pattern through the base.

    The seed is a compound of four solids with coincident faces at the boss /
    top-plate interfaces. Running a boolean across the whole compound makes OCC
    re-mesh those shared faces into thin sliver solids, so the cut is applied
    only to the main body solid (which contains the base plate); the other three
    solids are kept verbatim and recombined. The NEMA 17 holes live entirely in
    the base plate, so this is geometrically equivalent and keeps the model clean.
    """

    solids = cq.importers.importStep(INPUT_STEP).val().Solids()
    main_index = max(range(len(solids)), key=lambda i: solids[i].Volume())
    main_body = solids[main_index]
    other_solids = [s for i, s in enumerate(solids) if i != main_index]

    cut_z_min = BASE_PLATE_Z_MIN - CUT_MARGIN
    cut_z_max = BASE_PLATE_Z_MAX + CUT_MARGIN
    cut_length = cut_z_max - cut_z_min

    # Four through-drills, parallel to the motor axis (Z), spanning the base plate.
    cutter = (
        cq.Workplane("XY", origin=(0, 0, cut_z_min))
        .pushPoints(hole_positions())
        .circle(M3_CLEARANCE_R)
        .extrude(cut_length)
        .val()
    )

    main_cut = main_body.cut(cutter)
    result_shapes = list(main_cut.Solids()) + other_solids
    return cq.Compound.makeCompound(result_shapes)


def main() -> None:
    """Build the retrofit, validate it, and export STEP + a copy of this script."""

    print(
        f"[gt] adding NEMA 17 pattern: {NEMA17_PATTERN} mm square, "
        f"4x Ø{M3_CLEARANCE_DIA} mm (M3 clearance) through base plate "
        f"Z[{BASE_PLATE_Z_MIN}, {BASE_PLATE_Z_MAX}]"
    )

    result = build_solution()
    shape = result

    assert shape.isValid(), "retrofit result is not a valid solid"
    assert shape.Volume() > 0, "retrofit result has non-positive volume"

    # Sanity: the four new holes must be open (air) at mid base plate, and the
    # surrounding base-plate material must remain.
    solids = shape.Solids()

    def material_at(x: float, y: float, z: float) -> bool:
        point = cq.Vector(x, y, z)
        return any(solid.isInside(point, 1e-3) for solid in solids)

    z_mid = (BASE_PLATE_Z_MIN + BASE_PLATE_Z_MAX) / 2.0
    for (hx, hy) in hole_positions():
        assert not material_at(hx, hy, z_mid), f"NEMA17 hole not open at ({hx},{hy})"
    assert not material_at(AXIS_X, AXIS_Y, z_mid), "pilot bore was closed"
    assert material_at(AXIS_X + PATTERN_HALF + 2.2, AXIS_Y + PATTERN_HALF, z_mid), \
        "base-plate ring material missing next to a NEMA17 hole"

    os.makedirs(os.path.dirname(OUTPUT_STEP) or ".", exist_ok=True)
    cq.exporters.export(result, OUTPUT_STEP)
    print(
        f"[gt] exported {OUTPUT_STEP} "
        f"(volume {shape.Volume():.1f} mm^3, solids {len(solids)})"
    )

    try:
        import shutil

        os.makedirs(os.path.dirname(OUTPUT_PY) or ".", exist_ok=True)
        shutil.copy(__file__, OUTPUT_PY)
    except OSError as exc:
        print(f"[gt] note: could not copy script to {OUTPUT_PY}: {exc}")


if __name__ == "__main__":
    main()
