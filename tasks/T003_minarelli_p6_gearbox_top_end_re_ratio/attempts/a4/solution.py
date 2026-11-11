import cadquery as cq
from math import pi, cos, sin, sqrt, atan2, acos, tan

def make_involute_spur_gear(N, module, pa_deg=20.0, thickness=10.0, bore_dia=15.0, clearance=0.25):
    """Generate a spur gear with involute teeth. Axis along Z, centered at origin, thickness centered on Z=0."""
    pa = pa_deg * pi / 180.0
    rp = N * module / 2.0
    rb = rp * cos(pa)
    ra = rp + module
    rd = rp - (1.0 + clearance) * module
    half_tooth = pi / (2.0 * N)
    ang_pitch = 2 * pi / N
    def right_involute_pt(r):
        alpha = acos(rb / r)
        inv_pa = tan(pa) - pa
        inv_a = tan(alpha) - alpha
        theta = half_tooth + inv_pa - inv_a
        return (r * cos(theta), r * sin(theta))
    def left_involute_pt(r):
        alpha = acos(rb / r)
        inv_pa = tan(pa) - pa
        inv_a = tan(alpha) - alpha
        theta = half_tooth + inv_pa - inv_a
        return (r * cos(-theta), r * sin(-theta))
    n_flank = 6
    r_start = rb
    # theta at involute root (base circle); inv(0)=0
    inv_pa = tan(pa) - pa
    theta_root = half_tooth + inv_pa
    left_root = (rb * cos(-theta_root), rb * sin(-theta_root))
    right_root = (rb * cos(theta_root), rb * sin(theta_root))
    # extend inward to rd so tooth_bump volume overlaps core (for successful fuse to single solid)
    left_root_rd = (rd * cos(-theta_root), rd * sin(-theta_root))
    right_root_rd = (rd * cos(theta_root), rd * sin(theta_root))
    wp = cq.Workplane("XY").moveTo(left_root_rd[0], left_root_rd[1])
    wp = wp.lineTo(left_root[0], left_root[1])  # radial root leg to base
    for j in range(1, n_flank + 1):
        r = r_start + (ra - r_start) * j / n_flank
        p = left_involute_pt(r)
        wp = wp.lineTo(p[0], p[1])
    wp = wp.lineTo(right_involute_pt(ra)[0], right_involute_pt(ra)[1])
    for j in range(n_flank - 1, -1, -1):
        r = r_start + (ra - r_start) * j / n_flank
        p = right_involute_pt(r)
        wp = wp.lineTo(p[0], p[1])
    wp = wp.lineTo(right_root_rd[0], right_root_rd[1])  # radial root leg back to dedendum
    wp = wp.close()
    tooth_bump = wp.extrude(thickness).translate((0, 0, -thickness / 2.0))
    core = cq.Workplane("XY").circle(rd).extrude(thickness).translate((0, 0, -thickness / 2.0))
    # Build using solid .fuse() for reliable single solid (WP.union can leave compounds)
    core_solid = core.val()
    gear_solid = core_solid
    for i in range(N):
        rot_deg = i * ang_pitch * 180.0 / pi
        tb = tooth_bump.rotate((0, 0, 0), (0, 0, 1), rot_deg)
        tb_solid = tb.val()
        gear_solid = gear_solid.fuse(tb_solid)
    if bore_dia > 0:
        br = bore_dia / 2.0
        bore = cq.Workplane("XY").circle(br).extrude(thickness + 2).translate((0, 0, -thickness / 2 - 1))
        gear_solid = gear_solid.cut(bore.val())
    gear_solid = gear_solid.clean()
    # Final safety: ensure exactly one solid via explicit fuse if still multiple
    if hasattr(gear_solid, "Solids") and len(gear_solid.Solids()) > 1:
        fused = gear_solid.Solids()[0]
        for ss in gear_solid.Solids()[1:]:
            fused = fused.fuse(ss)
        gear_solid = fused
    return cq.Workplane().add(gear_solid)

def place_on_x_axis(gear, cx, sy, sz):
    """Rotate gear (Z axis) to have thickness along X, then translate to (cx, sy, sz)."""
    # Rotate +90 deg around Y to map local Z to global X
    g = gear.rotate((0, 0, 0), (0, 1, 0), 90)
    g = g.translate((cx, sy, sz))
    return g

# Load original model
model = cq.importers.importStep("/workspace/files/problem/model.step")
all_solids = model.val().Solids()

# The two gears to re-cut: ids from inspection #5 (N=21 at x~-34.3) and #27 (N=18 at x~-23.8)
# Filter by approximate center x and rmax to be robust
def get_center_and_rmax(s):
    bb = s.BoundingBox()
    cx = (bb.xmin + bb.xmax) / 2
    cy = (bb.ymin + bb.ymax) / 2
    cz = (bb.zmin + bb.zmax) / 2
    rmax = 0.0
    for v in s.Vertices():
        r = sqrt((v.Y - cy)**2 + (v.Z - cz)**2)
        if r > rmax:
            rmax = r
    return cx, cy, cz, rmax, bb.xmin, bb.xmax

to_replace = []
other_solids = []
for s in all_solids:
    cx, cy, cz, rmax, xmin, xmax = get_center_and_rmax(s)
    w = xmax - xmin
    # the two smallest on the cluster shaft y~4.46 z~86.36 , rmax ~20.45 and 17.5 , widths 9 and 11
    if abs(cy - 4.46) < 0.2 and abs(cz - 86.36) < 0.2 and w > 7 and w < 13:
        if 20.0 < rmax < 21.0 and 8.5 < w < 9.5:
            to_replace.append((s, 21, cx, w, xmin, xmax, cy, cz))
        elif 17.0 < rmax < 18.0 and 10.5 < w < 11.5:
            to_replace.append((s, 18, cx, w, xmin, xmax, cy, cz))
        else:
            other_solids.append(s)
    else:
        other_solids.append(s)

print("Found", len(to_replace), "gears to re-cut")
assert len(to_replace) == 2, "Did not find exactly the two smallest gears"

# Shaft approx from data
shaft_y = 4.46
shaft_z = 86.36
m = 1.75
pa = 20.0
bore_d = 15.0

new_gears = []
for old_s, old_N, cx, w, xmin, xmax, cy, cz in to_replace:
    new_N = old_N - 1
    print(f"Re-cutting gear at cx={cx:.2f} from N={old_N} to N={new_N}, width={w}")
    g = make_involute_spur_gear(new_N, m, pa, thickness=w, bore_dia=bore_d)
    # use the gear's own cy cz for placement? but to keep exact same axis use shaft
    placed = place_on_x_axis(g, cx, shaft_y, shaft_z)
    new_gears.append(placed.val())

# Build new compound: other solids + new gears
new_solids = other_solids + new_gears
new_comp = cq.Compound.makeCompound(new_solids)
new_comp.exportStep("/workspace/output/solution.step")
print("Exported /workspace/output/solution.step")

# Also verify the new gears in the output have correct N by quick check (optional, for build)
print("Done.")
