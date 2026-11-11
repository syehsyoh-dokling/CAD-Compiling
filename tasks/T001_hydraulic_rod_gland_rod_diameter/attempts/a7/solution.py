#!/usr/bin/env python3
"""
CadQuery script to uprate the hydraulic cylinder rod gland from Ø50 to Ø56 rod.
Only internal rod-facing features (bore, guides, seal groove, wiper pocket, lead-in, inboard counterbore)
have their diameters increased by 6 mm while preserving axial positions, widths, and cross-sections (clearances).
All tube-mounting geometry (external thread, flange, spanner notches, pilot register, end faces, overall length) is unchanged.
"""

import cadquery as cq

# Load the original model
original = cq.importers.importStep("/workspace/files/problem/model.step")

# Original inner (rod-side) profile points extracted from section (X, radius), ordered inboard (X=-37.5) to outboard (X=37.5)
# These are all features that interact with the rod.
original_inner_pts = [
    (-37.5000, 31.0000),  # inboard counterbore start
    (-35.0000, 31.0000),
    (-35.0000, 32.2500),  # counterbore groove/recess
    (-33.3000, 32.2500),
    (-33.3000, 31.0000),
    (-26.0000, 31.0000),
    (-26.0000, 25.7500),  # start inboard rod guide land (r=25.75 for Ø50 rod +0.75mm radial clearance)
    (-21.0000, 25.7500),
    (-21.0000, 30.0000),  # rod seal groove (depth 5mm from rod surface)
    (-11.0000, 30.0000),
    (-11.0000, 25.7500),  # start outboard rod guide land
    (-7.5000, 25.7500),
    (-7.5000, 27.5000),   # clearance bore to wiper area (2.5mm radial over rod)
    (21.1900, 27.5000),
    (25.5000, 29.9850),   # after 30deg lead-in chamfer
    (37.5000, 29.9850),   # outboard wiper pocket mouth
]

# New rod radius = 28mm (from 25mm), delta_r = +3.0mm to preserve all clearances and groove depths
DELTA_R = 3.0
new_inner_pts = [(x, r + DELTA_R) for x, r in original_inner_pts]

# Build the new cavity solid (revolved profile of the enlarged inner features).
# The profile is sketched in the XZ plane (X = axial, Z = radial), then revolved around the X axis.
# The cavity is closed along the axis so the boolean cut enlarges the bore/grooves exactly.
cavity = (
    cq.Workplane("XZ")
    .polyline([(-37.5, 0.0)] + new_inner_pts + [(37.5, 0.0)])
    .close()
    .revolve(360.0, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
)

# Subtract the new larger cavity from the original. This opens up only the rod-side internal features
# while leaving all external/tube interface geometry untouched.
edited = original.cut(cavity)

# Export the edited model
cq.exporters.export(edited, "/workspace/output/solution.step")

print("Done: /workspace/output/solution.step written.")
print("Rod bore and internal rod features enlarged from Ø50 to Ø56 (radial +3mm).")
print("All tube-mounting, flange, thread, pilot, notches, end faces, length preserved.")
