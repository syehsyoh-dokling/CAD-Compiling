#!/usr/bin/env python3
"""
Re-bore a screw-in hydraulic cylinder rod gland from Ø50 rod to Ø56 rod.

- All rod-interfacing internal features (rod bore lands, seal groove, wiper pocket,
  retaining groove, lead-in cone, inboard counterbore) have their diameters increased
  by 6 mm (radial +3 mm) to preserve running clearances and groove cross-sections.
- All axial positions and feature widths/lengths are unchanged.
- External tube-mounting geometry (thread, flange, spanner notches, pilot register,
  external lead-ins, end faces, overall length) is left exactly as-is.
"""

import os
import cadquery as cq


def main():
    input_step = "/workspace/files/problem/model.step"
    output_step = "/workspace/output/solution.step"

    os.makedirs(os.path.dirname(output_step), exist_ok=True)

    # Load the starting model (rod axis along X)
    orig = cq.importers.importStep(input_step)

    # Rotate -90° about Y so bore axis aligns with +Z (makes revolve around Z trivial)
    model_rot = orig.rotate((0, 0, 0), (0, 1, 0), -90)

    # All internal radii are increased by exactly this amount.
    # Original rod radius = 25 mm; new = 28 mm => +3 mm radial on every rod-facing surface.
    DELTA = 3.0

    # Original internal radii (from inspection of cylindrical faces)
    R_LAND_ORIG = 25.75   # rod guide/bearing lands (tightest running clearance)
    R_MID_ORIG = 27.50    # longer guide/bore section
    R_SEAL_ORIG = 30.00   # rod-seal groove bottom
    R_POCKET_ORIG = 31.00 # rod-wiper pocket
    R_RETAIN_ORIG = 32.25 # wiper retaining-ring groove
    R_CBORE_ORIG = 30.00  # inboard counterbore / entry

    # New radii (preserve deltas to rod and preserve groove depths)
    R_LAND = R_LAND_ORIG + DELTA
    R_MID = R_MID_ORIG + DELTA
    R_SEAL = R_SEAL_ORIG + DELTA
    R_POCKET = R_POCKET_ORIG + DELTA
    R_RETAIN = R_RETAIN_ORIG + DELTA
    R_CBORE = R_CBORE_ORIG + DELTA

    # Axial (X) locations of all internal feature boundaries (unchanged)
    X_MOUTH_OUT = -37.5
    X_RETAIN_START = -35.0
    X_RETAIN_END = -33.3
    X_POCKET_END = -26.0
    X_SEAL_START = -21.0
    X_SEAL_END = -11.0
    X_LAND2_END = -7.5
    X_CONE_START = 21.19
    X_CONE_END = 25.5
    X_MOUTH_IN = 37.5

    # Build the cutter: a revolved solid whose outer profile exactly matches the
    # desired new (larger) internal bore geometry. Subtracting it from the original
    # opens up only the rod-related features.
    # Sketch on XZ (X = radial, Z = axial after the rotation above).
    cutter = (
        cq.Workplane("XZ")
        .moveTo(0, X_MOUTH_OUT)
        .lineTo(0, X_MOUTH_IN)                 # axis (centerline)
        .lineTo(R_CBORE, X_MOUTH_IN)           # inboard end face opening (new r)
        .lineTo(R_CBORE, X_CONE_END)           # inboard counterbore (cyl)
        .lineTo(R_MID, X_CONE_START)           # lead-in cone (internal)
        .lineTo(R_MID, X_LAND2_END)            # mid guide/bore (cyl)
        .lineTo(R_LAND, X_LAND2_END)           # radial step to land
        .lineTo(R_LAND, X_SEAL_END)            # land (cyl)
        .lineTo(R_SEAL, X_SEAL_END)            # radial step into seal groove
        .lineTo(R_SEAL, X_SEAL_START)          # rod-seal groove (cyl)
        .lineTo(R_LAND, X_SEAL_START)          # radial step out of seal groove
        .lineTo(R_LAND, X_POCKET_END)          # land (cyl)
        .lineTo(R_POCKET, X_POCKET_END)        # radial step into wiper pocket
        .lineTo(R_POCKET, X_RETAIN_END)        # wiper pocket (cyl)
        .lineTo(R_RETAIN, X_RETAIN_END)        # radial step into retaining groove
        .lineTo(R_RETAIN, X_RETAIN_START)      # retaining groove (cyl)
        .lineTo(R_POCKET, X_RETAIN_START)      # radial step out of retaining groove
        .lineTo(R_POCKET, X_MOUTH_OUT)         # wiper pocket to mouth (cyl)
        .lineTo(0, X_MOUTH_OUT)                # outboard end face opening (new r)
        .close()
        .revolve(360)
    )

    # Enlarge the internals via boolean difference. Only rod-facing surfaces move.
    edited_rot = model_rot.cut(cutter)

    # Rotate +90° about Y to restore the original coordinate system / orientation.
    edited = edited_rot.rotate((0, 0, 0), (0, 1, 0), 90)

    # Export the edited solid
    edited.val().exportStep(output_step)
    print(f"Wrote {output_step}")


if __name__ == "__main__":
    main()
