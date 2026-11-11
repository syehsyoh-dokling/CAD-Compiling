import cadquery as cq
from cadquery import exporters

# Input and output paths (relative to working directory /workspace)
INPUT_STEP = "files/problem/model.step"
OUTPUT_STEP = "output/solution.step"

# Load the original model
model = cq.importers.importStep(INPUT_STEP)

# Combine all solids into a single solid (original STEP has multiple)
bracket = model.solids().combine()

# NEMA 17 standard mounting pattern (smallest that clears the central 38.1 mm bore)
# - Hole spacing: 31 mm square (center-to-center)
# - Standard screw: M3
# - Standard clearance hole diameter: 3.5 mm
HOLE_SPACING = 31.0  # mm
HOLE_DIAMETER = 3.5  # mm clearance for M3
HOLE_RADIUS = HOLE_DIAMETER / 2.0  # 1.75 mm

# Offsets for the four holes (square pattern centered on axis)
offset = HOLE_SPACING / 2.0  # 15.5 mm
points = [
    (offset, offset),
    (offset, -offset),
    (-offset, offset),
    (-offset, -offset),
]

# Base plate spans z = -71.5 (bottom) to -61.5 (top), thickness 10 mm
# Cut only through the base plate
PLATE_BOTTOM_Z = -71.5
PLATE_THICKNESS = 10.0

# Build cutter as four vertical cylinders (parallel to motor/Z axis)
cutter = (
    cq.Workplane("XY")
    .pushPoints(points)
    .circle(HOLE_RADIUS)
    .extrude(PLATE_THICKNESS + 0.2)
    .translate((0, 0, PLATE_BOTTOM_Z - 0.1))
)

# Perform the cut to add the four clearance holes (dual pattern: NEMA 23 remains)
result = bracket.cut(cutter)
result = result.clean()

# Export the edited model
exporters.export(result, OUTPUT_STEP)

print(f"Edited model written to {OUTPUT_STEP}")
print(f"Added NEMA 17 (31 mm pattern, 3.5 mm clearance holes) dual-patterned with existing NEMA 23 holes.")
print(f"Central coupling bore (38.1 mm) and all other features preserved.")
