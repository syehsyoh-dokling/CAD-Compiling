#!/usr/bin/env python3
"""
CadQuery script to uprate the hydraulic cylinder rod gland from Ø50 to Ø56 rod.
Only internal rod-related features (bore, lands, seal groove, wiper pocket,
retaining groove, lead-in, inboard counterbore) are enlarged by +3 mm radius.
All tube-mounting geometry (external thread, flange, spanner notches, pilot,
end faces, overall length) is left unchanged.
"""

import cadquery as cq
from cadquery import importers

# Load the original model
model = importers.importStep("/workspace/files/problem/model.step")
solid = model.val()

# Delta for rod diameter increase 50 -> 56 mm => +3 mm on all radii
DELTA = 3.0

# Original inner radii (from inspection)
R_ROD_BORE = 25.75
R_SEAL_GROOVE = 30.0
R_WIPER_POCKET = 27.5
R_MOUTH = 31.0
R_INBOARD_CB = 29.985

# New radii (preserve groove cross-sections and clearances)
R_ROD_BORE_NEW = R_ROD_BORE + DELTA          # 28.75
R_SEAL_GROOVE_NEW = R_SEAL_GROOVE + DELTA    # 33.0
R_WIPER_POCKET_NEW = R_WIPER_POCKET + DELTA  # 30.5
R_MOUTH_NEW = R_MOUTH + DELTA                # 34.0
R_INBOARD_CB_NEW = R_INBOARD_CB + DELTA      # 32.985

# Key axial (X) positions of feature transitions (from planar faces and profile)
X_MOUTH = -37.5
X_ROD_START = -26.0
X_GROOVE_LEFT = -21.0
X_GROOVE_RIGHT = -11.0
X_WIPER_START = -7.5
X_CONE_LEFT = 21.19
X_CONE_RIGHT = 25.5
X_END = 37.5

# Build the new enlarged internal cavity as a revolved solid.
# Sketch in XY plane (X = axial, Y = radial), positive Y half-profile,
# then revolve 360 deg around the X axis (the rod centerline at y=0, z=0).

# Upper bore profile (y >= 0). Points are (x, r_new).
# Order from outboard (left, negative X) to inboard (right, positive X).

profile_points = [
    # Outboard mouth / wiper area (flange end)
    (X_MOUTH, R_MOUTH_NEW),
    # Step to main rod bore / guide land
    (X_ROD_START, R_ROD_BORE_NEW),
    # Rod seal groove (wider cavity)
    (X_GROOVE_LEFT, R_ROD_BORE_NEW),
    (X_GROOVE_LEFT, R_SEAL_GROOVE_NEW),
    (X_GROOVE_RIGHT, R_SEAL_GROOVE_NEW),
    (X_GROOVE_RIGHT, R_ROD_BORE_NEW),
    # Transition to outboard-side of main bore / wiper pocket
    (X_WIPER_START, R_ROD_BORE_NEW),
    (X_WIPER_START, R_WIPER_POCKET_NEW),
    # Long wiper pocket / buffer land
    (X_CONE_LEFT, R_WIPER_POCKET_NEW),
    # Conical lead-in to inboard counterbore
    (X_CONE_RIGHT, R_INBOARD_CB_NEW),
    # Inboard counterbore to end
    (X_END, R_INBOARD_CB_NEW),
]

# Create the 2D half-profile on the XY plane
wp = cq.Workplane("XY")

# Start on axis at outboard end
sketch = wp.moveTo(X_MOUTH, 0)

# Draw the upper profile (radial line)
for x, r in profile_points:
    sketch = sketch.lineTo(x, r)

# Close back along the axis to the start (the cavity is solid to center)
sketch = sketch.lineTo(X_END, 0).close()

# Revolve the profile 360 degrees around the X axis to create the cavity solid.
# axisStart and axisEnd define the X axis through the origin.
cavity = sketch.revolve(360, (0, 0), (1, 0)).val()

# Cut the enlarged cavity from the original solid.
# This only affects internal rod-related diameters/positions while preserving
# all external mounting geometry.
result = solid.cut(cavity)

# Export
result.exportStep("/workspace/output/solution.step")
print("Exported /workspace/output/solution.step")

# Also keep a workplane reference for optional further inspection
result_wp = cq.Workplane(result)
print("Done. Inner features enlarged by +3 mm radius; external geometry preserved.")