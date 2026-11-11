#!/usr/bin/env python3
"""CadQuery script to re-cut the two smallest gears in the constant-mesh cluster
of the Minarelli P6 moped engine gearbox to one fewer tooth each, preserving
module, pressure angle, axis, position, bore, and face width, while adjusting
profile shift so the gears still mesh at the fixed center distance with their
unchanged partners.
"""

import cadquery as cq
from cadquery import importers
import math

# Parameters from model inspection
GEAR_CY = 4.480
GEAR_CZ = 86.361
CD = 38.0  # shaft center distance
M = 76.0 / 43.0  # module derived from CD and Nsum=43 for all pairs
ALPHA = math.radians(20.0)
X_SHIFT = 0.5416  # profile shift for N-1 gears to keep CD with mate x=0

# The two gears to re-cut (two smallest in descending cluster 33-30-27-25-23-21)
# idx20: N=23 ->22 , idx5: N=21->20
GEARS_TO_REPLACE = [
    {
        "orig_N": 23,
        "new_N": 22,
        "center_x": -60.511,
        "thickness": 8.0,
        "old_root": 18.165,
        "old_tip": 22.160,
        "bore_r": 9.0,
        "cut_r": 17.8,
    },
    {
        "orig_N": 21,
        "new_N": 20,
        "center_x": -34.110,
        "thickness": 9.0,
        "old_root": 16.390,
        "old_tip": 20.386,
        "bore_r": 7.5,
        "cut_r": 15.9,
    },
]


def make_gear_tooth_profile(m, N, alpha, x, n_points=20, bite=0.5):
    """Generate 2D tooth profile points (y, z) for a profile-shifted involute tooth.
    y is radial (tooth points +y), z is tangential. Returns profile list and ra, rr.
    """
    rp = N * m / 2.0
    rb = rp * math.cos(alpha)
    ra = rp + m * (1.0 + x)
    rr = rp - m * (1.25 - x)
    if rr < rb:
        rr = rb * 1.01
    theta_p = math.pi / (2.0 * N) + (2.0 * x * math.tan(alpha)) / N
    t_p = math.sqrt((rp / rb) ** 2 - 1.0)
    px = rb * (math.cos(t_p) + t_p * math.sin(t_p))
    py = rb * (math.sin(t_p) - t_p * math.cos(t_p))
    psi_p = math.atan2(py, px)
    dtheta = theta_p - psi_p

    def involute_pt(t):
        return (
            rb * (math.cos(t) + t * math.sin(t)),
            rb * (math.sin(t) - t * math.cos(t)),
        )

    t_start = math.sqrt(max(0.0, ((rr - bite) / rb) ** 2 - 1.0))
    t_end = math.sqrt((ra / rb) ** 2 - 1.0)
    ts = [t_start + (t_end - t_start) * i / (n_points - 1) for i in range(n_points)]
    pts_r = []
    for t in ts:
        px, pz = involute_pt(t)
        pr = math.hypot(px, pz)
        pa = math.atan2(pz, px) + dtheta
        pa_sym = pa - theta_p
        y = pr * math.cos(pa_sym)
        z = pr * math.sin(pa_sym)
        pts_r.append((y, z))
    pts_l = [(p[0], -p[1]) for p in reversed(pts_r)]
    tip_r = pts_r[-1]
    tip_l = pts_l[0]
    a1 = math.atan2(tip_r[1], tip_r[0])
    a2 = math.atan2(tip_l[1], tip_l[0])
    pts_tip = [
        (ra * math.cos(a1 + (a2 - a1) * i / 5), ra * math.sin(a1 + (a2 - a1) * i / 5))
        for i in range(6)
    ]
    root_r = pts_r[0]
    root_l = pts_l[-1]
    ar1 = math.atan2(root_r[1], root_r[0])
    ar2 = math.atan2(root_l[1], root_l[0])
    rdeep = rr - bite
    pts_root = [
        (
            rdeep * math.cos(ar1 + (ar2 - ar1) * i / 5),
            rdeep * math.sin(ar1 + (ar2 - ar1) * i / 5),
        )
        for i in range(6)
    ]
    profile = [root_r] + pts_r[1:-1] + pts_tip + pts_l[1:-1] + list(reversed(pts_root))
    prof = []
    for p in profile:
        if not prof or math.hypot(p[0] - prof[-1][0], p[1] - prof[-1][1]) > 1e-6:
            prof.append(p)
    if math.hypot(prof[0][0] - prof[-1][0], prof[0][1] - prof[-1][1]) > 1e-6:
        prof.append(prof[0])
    return prof, ra, rr


def make_gear_rim(gear_params, m, alpha, x):
    """Create the replacement outer rim (root land + teeth) to union onto cut hub.
    Uses single full toothed profile + extrude + simple cut for robustness (no per-tooth bools).
    Preserves hub inner (bore etc) from original via intersect in main().
    """
    N = gear_params["new_N"]
    cx = gear_params["center_x"]
    thick = gear_params["thickness"]
    cut_r = gear_params["cut_r"]

    pts_r, pts_tip, pts_l, ra, rr = _get_tooth_pts(m, N, alpha, x, bite=0.0)
    # build full closed outer profile (teeth + root gap arcs at rr)
    full_pts = []
    for i in range(N):
        ang = i * 360.0 / N
        a_rad = math.radians(ang)
        # tooth chain: right root -> invol -> tip -> invol -> left root
        tooth_chain = [pts_r[0]] + pts_r[1:-1] + pts_tip + pts_l[1:-1] + [pts_l[-1]]
        for py, pz in tooth_chain:
            ry = py * math.cos(a_rad) - pz * math.sin(a_rad)
            rz = py * math.sin(a_rad) + pz * math.cos(a_rad)
            full_pts.append((ry, rz))
        # root arc at rr across gap to next tooth right root
        left_py, left_pz = pts_l[-1]
        left_r_ang = math.atan2(left_pz, left_py) + a_rad
        next_i = (i + 1) % N
        next_a_rad = math.radians(next_i * 360.0 / N)
        right_py, right_pz = pts_r[0]
        right_r_ang = math.atan2(right_pz, right_py) + next_a_rad
        d_ang = right_r_ang - left_r_ang
        if d_ang <= 0:
            d_ang += 2 * math.pi
        n_arc = 5
        for j in range(1, n_arc):
            aa = left_r_ang + d_ang * j / n_arc
            full_pts.append((rr * math.cos(aa), rr * math.sin(aa)))
    if full_pts and math.hypot(full_pts[0][0] - full_pts[-1][0], full_pts[0][1] - full_pts[-1][1]) > 1e-6:
        full_pts.append(full_pts[0])
    # extrude full toothed (disk to center), then cut inner at cut_r to make rim annulus
    toothed = (
        cq.Workplane("YZ")
        .polyline(full_pts)
        .close()
        .extrude(thick, both=True)
        .translate((0, GEAR_CY, GEAR_CZ))
        .translate((cx, 0, 0))
    )
    # cut rim ID slightly inside cut_r so rim has thicker wall (avoids thin-feature negative vol in some cases)
    # still >> bore so bore from hub is preserved; extra overlap aids union
    inner_cut = max(7.0, cut_r - 0.3)
    inner_cutter = (
        cq.Workplane("YZ")
        .circle(inner_cut)
        .extrude(thick * 3, both=True)
        .translate((0, GEAR_CY, GEAR_CZ))
        .translate((cx, 0, 0))
    )
    rim = toothed.cut(inner_cutter)
    return rim.val()  # Solid (annulus with correct new teeth)


def _get_tooth_pts(m, N, alpha, x, n_points=20, bite=0.5):
    """Helper: return pts_r, pts_tip, pts_l, ra, rr for use in full profile."""
    rp = N * m / 2.0
    rb = rp * math.cos(alpha)
    ra = rp + m * (1.0 + x)
    rr = rp - m * (1.25 - x)
    if rr < rb:
        rr = rb * 1.01
    theta_p = math.pi / (2.0 * N) + (2.0 * x * math.tan(alpha)) / N
    t_p = math.sqrt((rp / rb) ** 2 - 1.0)
    px = rb * (math.cos(t_p) + t_p * math.sin(t_p))
    py = rb * (math.sin(t_p) - t_p * math.cos(t_p))
    psi_p = math.atan2(py, px)
    dtheta = theta_p - psi_p

    def involute_pt(t):
        return (
            rb * (math.cos(t) + t * math.sin(t)),
            rb * (math.sin(t) - t * math.cos(t)),
        )

    t_start = math.sqrt(max(0.0, ((rr - bite) / rb) ** 2 - 1.0))
    t_end = math.sqrt((ra / rb) ** 2 - 1.0)
    ts = [t_start + (t_end - t_start) * i / (n_points - 1) for i in range(n_points)]
    pts_r = []
    for t in ts:
        px, pz = involute_pt(t)
        pr = math.hypot(px, pz)
        pa = math.atan2(pz, px) + dtheta
        pa_sym = pa - theta_p
        y = pr * math.cos(pa_sym)
        z = pr * math.sin(pa_sym)
        pts_r.append((y, z))
    pts_l = [(p[0], -p[1]) for p in reversed(pts_r)]
    tip_r = pts_r[-1]
    tip_l = pts_l[0]
    a1 = math.atan2(tip_r[1], tip_r[0])
    a2 = math.atan2(tip_l[1], tip_l[0])
    pts_tip = [
        (ra * math.cos(a1 + (a2 - a1) * i / 5), ra * math.sin(a1 + (a2 - a1) * i / 5))
        for i in range(6)
    ]
    return pts_r, pts_tip, pts_l, ra, rr


def main():
    print("Loading model...")
    model = importers.importStep("/workspace/files/problem/model.step")
    all_solids_wp = model.solids().all()
    all_solids = [s.val() for s in all_solids_wp]
    print(f"Loaded {len(all_solids)} solids.")

    # Identify the two gears to replace by center_x and cz
    kept = []
    replaced_count = 0
    new_gears = []
    for s in all_solids:
        com = s.Center()
        vol = s.Volume()
        is_target = False
        for gp in GEARS_TO_REPLACE:
            if (
                abs(com.x - gp["center_x"]) < 0.5
                and abs(com.z - GEAR_CZ) < 0.5
                and vol > 5000
            ):
                is_target = True
                break
        if is_target:
            replaced_count += 1
            print(f"  Replacing gear at cx={com.x:.2f}")
            # find matching params
            gp = None
            for g in GEARS_TO_REPLACE:
                if abs(com.x - g["center_x"]) < 0.5:
                    gp = g
                    break
            # intersect original with cyl to keep only inner hub (r <= cut_r), union new rim+teeth
            cyl = (
                cq.Workplane("YZ")
                .circle(gp["cut_r"] + 0.6)
                .extrude(gp["thickness"] * 3, both=True)
                .translate((0, GEAR_CY, GEAR_CZ))
                .translate((gp["center_x"], 0, 0))
            )
            hub = cq.Workplane().add(s).intersect(cyl).val()
            ng_rim = make_gear_rim(gp, M, ALPHA, X_SHIFT)
            new_gear = cq.Workplane().add(hub).union(cq.Workplane().add(ng_rim)).val()
            v = new_gear.Volume() if hasattr(new_gear, "Volume") else 0
            if v < 0:
                # heal sign by self-union (re-bakes the solid with +vol)
                new_gear = cq.Workplane().add(new_gear).union(cq.Workplane().add(new_gear)).val()
            new_gears.append(new_gear)
        else:
            kept.append(s)

    print(f"Replaced {replaced_count} gears, kept {len(kept)} solids.")

    # Build new compound: fast makeCompound, but extract inner Solids from any Compounds
    # (the constructed new gears are often Compounds; extracting avoids mixing issues that flip vol sign)
    print("Assembling new model...")
    from cadquery import Compound
    shapes = list(kept)
    for ng in new_gears:
        if hasattr(ng, "Solids") and ng.Solids():
            shapes.extend(ng.Solids())
        else:
            shapes.append(ng)
    compound = Compound.makeCompound(shapes)

    # Export
    out_path = "/workspace/output/solution.step"
    print(f"Exporting to {out_path} ...")
    compound.exportStep(out_path)
    print("Done.")

    # Quick verification of new gears (tooth count)
    print("\nVerification of new gears (est N from vertices):")
    for ng in new_gears:
        N_est, r_est = _est_N(ng, GEAR_CY, GEAR_CZ)
        com = ng.Center()
        print(f"  at cx={com.x:.2f}  est_N={N_est}  rmax={r_est}")


def _est_N(solid, cy, cz):
    verts = solid.Vertices()
    rs = [math.hypot(v.Y - cy, v.Z - cz) for v in verts]
    if not rs:
        return None, 0.0
    maxr = max(rs)
    tol = 0.25
    outer_angs = []
    for v in verts:
        r = math.hypot(v.Y - cy, v.Z - cz)
        if abs(r - maxr) <= tol:
            a = math.atan2(v.Z - cz, v.Y - cy)
            outer_angs.append((a + 2 * math.pi) % (2 * math.pi))
    if len(outer_angs) < 8:
        return None, round(maxr, 2)
    angs = sorted(set([round(a, 6) for a in outer_angs]))  # dedup very close
    # cluster close angles (within ~0.1 rad ~ one tip cluster)
    clusters = []
    for a in angs:
        if not clusters or abs(a - clusters[-1][-1]) > 0.1:
            clusters.append([a])
        else:
            clusters[-1].append(a)
    # one rep per cluster
    reps = [sum(c)/len(c) for c in clusters]
    if len(reps) < 4:
        return None, round(maxr, 2)
    # deltas between clusters (should be ~ pitch)
    deltas = []
    n = len(reps)
    for i in range(n):
        d = reps[(i + 1) % n] - reps[i]
        if d <= 0:
            d += 2 * math.pi
        if 0.05 < d < 0.8:
            deltas.append(d)
    if not deltas:
        return len(reps), round(maxr, 2)
    med_d = sorted(deltas)[len(deltas) // 2]
    N = int(round(2 * math.pi / med_d))
    return N, round(maxr, 2)


if __name__ == "__main__":
    main()
