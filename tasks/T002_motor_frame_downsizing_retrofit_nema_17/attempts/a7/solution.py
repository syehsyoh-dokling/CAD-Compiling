import cadquery as cq
from cadquery import Compound
import os

# Input model (relative to workspace root when run from /workspace)
INPUT_PATH = "files/problem/model.step"
OUTPUT_PATH = "output/solution.step"

def main():
    # Load the original bracket model
    model = cq.importers.importStep(INPUT_PATH)

    # Identify solids; the main body (solid 0) contains the base plate at the bottom
    solids = model.solids().vals()
    main_solid = solids[0]
    other_solids = solids[1:]

    # NEMA 17 is the smallest standard frame whose mounting pattern clears the central bore.
    # - Standard NEMA 17 bolt pattern: 31 mm square (center-to-center)
    # - Standard mounting screw: M3
    # - Standard clearance hole diameter for M3 (normal fit): 3.5 mm
    # Existing NEMA 23 pattern (47.1 mm square, 5 mm dia holes) remains untouched.
    # The 4 new holes are coaxial with the existing central coupling bore (r=19.05 mm at base).
    NEMA17_SPACING = 31.0  # mm
    HOLE_DIAMETER = 3.5    # mm clearance for M3

    half = NEMA17_SPACING / 2.0
    hole_radius = HOLE_DIAMETER / 2.0
    mount_points = [
        (half, half),
        (half, -half),
        (-half, half),
        (-half, -half),
    ]

    # Base plate thickness and location from inspection of the model
    PLATE_BOTTOM_Z = -71.5
    PLATE_THICKNESS = 10.0

    # Build cutters as a compound of 4 cylinders, sized and positioned to pass
    # cleanly through only the base plate (slightly oversized in Z for reliable boolean)
    cutters = (
        cq.Workplane("XY")
        .pushPoints(mount_points)
        .circle(hole_radius)
        .extrude(PLATE_THICKNESS + 0.2)
        .translate((0, 0, PLATE_BOTTOM_Z - 0.1))
    ).val()

    # Cut only the main solid (base plate lives here); reassemble to keep original solid count/structure
    cut_main = main_solid.cut(cutters)
    result_compound = Compound.makeCompound([cut_main] + other_solids)
    result = cq.Workplane(obj=result_compound)

    # Ensure output dir and export
    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    # Export the shape (compound of 4 solids, matching input structure)
    result.val().exportStep(OUTPUT_PATH)

    print(f"Edited model written to {OUTPUT_PATH}")
    print(f"Added 4x {HOLE_DIAMETER} mm dia clearance holes on {NEMA17_SPACING} mm square NEMA 17 pattern.")
    print(f"Existing NEMA 23 holes and all other features preserved.")

if __name__ == "__main__":
    main()
