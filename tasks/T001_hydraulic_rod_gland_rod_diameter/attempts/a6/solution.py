import cadquery as cq
from cadquery import exporters

# Load the original gland model (Ø50 rod)
orig = cq.importers.importStep("/workspace/files/problem/model.step")

# Delta radius for new Ø56 rod (from Ø50)
DELTA_R = 3.0

# Internal bore profile: list of (X, r_old) corners in order from outboard (X=-37.5) to inboard (X=37.5).
# These define all rod-contacting features: wiper pocket, retaining groove, lands, rod-seal groove,
# main guide land, lead-in cone, and inboard counterbore.
# Only radii will be increased; all X positions and feature widths are preserved exactly.
# External tube-mounting geometry (thread, flange, pilot, notches, ends, length) is untouched.
old_profile = [
    (-37.5, 31.0),
    (-35.0, 31.0),
    (-35.0, 32.25),
    (-33.3, 32.25),
    (-33.3, 31.0),
    (-26.0, 31.0),
    (-26.0, 25.75),
    (-21.0, 25.75),
    (-21.0, 30.0),
    (-11.0, 30.0),
    (-11.0, 25.75),
    (-7.5, 25.75),
    (-7.5, 27.5),
    (21.19, 27.5),
    (25.5, 29.985),
    (37.5, 29.985),
]

# Build new profile with enlarged radii (clearances and groove cross-sections preserved)
new_profile = [(x, r + DELTA_R) for x, r in old_profile]

# Create the bore cutter solid by sketching the profile in the X-r plane and revolving around X axis.
# The sketch goes from r=0 (axis) out to the profile, revolved 360deg produces the exact material
# to remove for the new larger internal features.
wp = cq.Workplane("XY")
x0, r0 = new_profile[0]
wp = wp.moveTo(x0, 0).lineTo(x0, r0)
for i in range(1, len(new_profile)):
    px, pr = new_profile[i]
    wp = wp.lineTo(px, pr)
x_end, r_end = new_profile[-1]
wp = wp.lineTo(x_end, 0).close()

bore_cutter = wp.revolve(360.0, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

# Perform the edit: remove the larger bore volume from the original.
# This enlarges only the rod bore, guide lands, seal groove, wiper pocket+retaining groove,
# lead-in, and inboard counterbore. All axial positions, widths, and external geometry remain.
result = orig.cut(bore_cutter)

# Export the edited model
exporters.export(result, "/workspace/output/solution.step")

print("Successfully wrote /workspace/output/solution.step")
print(f"Original volume: {orig.val().Volume():.3f}")
print(f"Edited volume:   {result.val().Volume():.3f}")
print(f"Volume removed:  {orig.val().Volume() - result.val().Volume():.3f}")
