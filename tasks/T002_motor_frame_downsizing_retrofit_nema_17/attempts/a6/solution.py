#!/usr/bin/env python3
"""CadQuery script to downsize motor mount: add NEMA 17 clearance holes to base plate.

The bracket originally has a NEMA 23 pattern (47.1 mm square, 5 mm dia holes) on the
base plate around the central 38.1 mm dia coupling bore. The smallest NEMA frame
whose standard pattern clears the bore is NEMA 17 (31 mm square spacing).

NEMA 17 standard uses M3/#4-40 screws; standard clearance hole diameter is 3.5 mm.
The four new holes are placed at (±15.5, ±15.5) mm, coaxial with the bore,
drilled through the 10 mm thick base plate only. Existing NEMA 23 holes are left
untouched, making the plate dual-pattern.
"""

import cadquery as cq
from cadquery import importers, exporters


def main():
    # Load the original multi-body STEP model
    model = importers.importStep("/workspace/files/problem/model.step")

    # Union into a single solid (original STEP stores bracket as adjacent bodies)
    bracket = None
    for s in model.solids().vals():
        if bracket is None:
            bracket = cq.Workplane().add(s)
        else:
            bracket = bracket.union(s)

    # NEMA 17 parameters (standard values)
    # - square hole spacing: 31 mm center-to-center
    # - clearance hole diameter: 3.5 mm (for M3 / #4-40 mounting screws)
    hole_diameter = 3.5
    hole_radius = hole_diameter / 2.0
    nema17_spacing = 31.0
    half = nema17_spacing / 2.0
    hole_positions = [
        (half, half),
        (half, -half),
        (-half, half),
        (-half, -half),
    ]

    # Base plate geometry (measured from model)
    plate_bottom_z = -71.5
    plate_thickness = 10.0
    # Cut height with small epsilon to ensure through cut on the plate
    cut_height = plate_thickness + 0.2

    # Cut the four new clearance holes (only through base plate, z-limited)
    for hx, hy in hole_positions:
        cutter = (
            cq.Workplane("XY")
            .moveTo(hx, hy)
            .circle(hole_radius)
            .extrude(cut_height)
            .translate((0, 0, plate_bottom_z))
        )
        bracket = bracket.cut(cutter)

    # Ensure clean single solid result
    result = bracket.solids().val()

    # Export the edited model
    exporters.export(result, "/workspace/output/solution.step")
    print("Exported /workspace/output/solution.step")


if __name__ == "__main__":
    main()
