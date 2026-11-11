#!/usr/bin/env python3
"""CadQuery script to re-cut the two smallest gears in the constant-mesh cluster
of the Minarelli P6 moped engine gearbox to one fewer tooth each.
"""

import cadquery as cq
from cadquery import importers
import math


def make_involute_spur_gear(teeth, module, face_width, bore_dia, pa_deg=20.0):
    """Create a proper involute spur gear solid using hub + teeth for clean BREP/STEP.
    Axis along +X, centered at origin, face centered on x=0.
    """
    pa = math.radians(pa_deg)
    pitch_r = teeth * module / 2.0
    base_r = pitch_r * math.cos(pa)
    addendum = 1.0 * module
    dedendum = 1.25 * module
    outer_r = pitch_r + addendum
    root_r = pitch_r - dedendum
    bore_r = bore_dia / 2.0
    half_thick = math.pi / teeth

    def involute_pt(rad):
        if rad < base_r:
            rad = base_r
        alpha = math.acos(base_r / rad)
        theta = math.tan(alpha) - alpha
        x = rad * math.cos(theta)
        y = rad * math.sin(theta)
        return x, y

    alpha_p = math.acos(base_r / pitch_r)
    theta_p = math.tan(alpha_p) - alpha_p
    rot = half_thick - theta_p
    n_pts = 5
    tooth_ang = 2 * math.pi / teeth
    overlap = 0.01

    # Hub (root cylinder + bore hole), temp thickness along Z
    hub = cq.Workplane("XY").circle(root_r).circle(bore_r).extrude(face_width)
    hub = hub.translate((0, 0, -face_width / 2.0))
    # Final orient: thickness along X
    hub = hub.rotate((0, 0, 0), (0, 1, 0), 90)

    gear3d = cq.Workplane().add(hub)

    for i in range(teeth):
        base_ang = i * tooth_ang
        rfs = []
        for j in range(n_pts + 1):
            rad = (root_r - overlap) + (outer_r - (root_r - overlap)) * j / n_pts
            ix, iy = involute_pt(rad)
            rx = ix * math.cos(rot) - iy * math.sin(rot)
            ry = ix * math.sin(rot) + iy * math.cos(rot)
            ca = math.cos(base_ang)
            sa = math.sin(base_ang)
            px = rx * ca - ry * sa
            py = rx * sa + ry * ca
            rfs.append((px, py))
        lfs = []
        for j in range(n_pts, -1, -1):
            rad = (root_r - overlap) + (outer_r - (root_r - overlap)) * j / n_pts
            ix, iy = involute_pt(rad)
            rx = ix * math.cos(rot) - iy * math.sin(rot)
            ry = ix * math.sin(rot) + iy * math.cos(rot)
            ry = -ry
            ca = math.cos(base_ang)
            sa = math.sin(base_ang)
            px = rx * ca - ry * sa
            py = rx * sa + ry * ca
            lfs.append((px, py))
        # One tooth profile (root-overlap to outer, tip arc, close chord at inner)
        t_wp = cq.Workplane("XY")
        t_w = t_wp.moveTo(rfs[0][0], rfs[0][1])
        for p in rfs[1:]:
            t_w = t_w.lineTo(p[0], p[1])
        t_w = t_w.radiusArc((lfs[0][0], lfs[0][1]), outer_r)
        for p in lfs[1:]:
            t_w = t_w.lineTo(p[0], p[1])
        t_w = t_w.close()
        t_face = cq.Face.makeFromWires(t_w.val())
        t3d = cq.Workplane("XY").add(t_face).extrude(face_width)
        t3d = t3d.translate((0, 0, -face_width / 2.0))
        # rotate in plane to tooth angle, then orient to X-thickness
        t3d = t3d.rotate((0, 0, 0), (0, 0, 1), math.degrees(base_ang))
        t3d = t3d.rotate((0, 0, 0), (0, 1, 0), 90)
        gear3d = gear3d.union(t3d)

    # final center at origin
    c = gear3d.val().Center()
    gear3d = gear3d.translate((-c.x, -c.y, -c.z))
    return gear3d


def main():
    # Load original model
    orig = importers.importStep("/workspace/files/problem/model.step")
    all_solids = orig.solids().vals()

    # Identify the two smallest gears in the cluster by position and size
    # Solid 20: x~-60.5105, thick=8, dia~44.3 (46 teeth) -> 45 teeth
    # Solid 5: x~-34.1096, thick=9, dia~40.8 (42 teeth) -> 41 teeth
    gear_to_replace = []  # list of (solid, new_teeth, module, face_width, bore_dia, center)
    others = []

    for s in all_solids:
        c = s.Center()
        bb = s.BoundingBox()
        x = c.x
        thick = bb.xlen
        # Precise match using known centers and dimensions
        if abs(x + 60.5105) < 0.01 and abs(thick - 8.0) < 0.01:
            # 46t -> 45t
            bore_r = min(
                math.sqrt((v.Y - c.y) ** 2 + (v.Z - c.z) ** 2)
                for v in s.Vertices()
                if math.sqrt((v.Y - c.y) ** 2 + (v.Z - c.z) ** 2) > 1
            )
            gear_to_replace.append((s, 45, 0.9235, thick, 2 * bore_r, (c.x, c.y, c.z)))
        elif abs(x + 34.1096) < 0.01 and abs(thick - 9.0) < 0.01:
            # 42t -> 41t
            bore_r = min(
                math.sqrt((v.Y - c.y) ** 2 + (v.Z - c.z) ** 2)
                for v in s.Vertices()
                if math.sqrt((v.Y - c.y) ** 2 + (v.Z - c.z) ** 2) > 1
            )
            gear_to_replace.append((s, 41, 0.9268, thick, 2 * bore_r, (c.x, c.y, c.z)))
        else:
            others.append(s)

    if len(gear_to_replace) != 2:
        raise RuntimeError(f"Expected to find exactly 2 gears to replace, found {len(gear_to_replace)}")

    # Build new gears
    new_gears = []
    for old_s, new_t, mod, fw, br, ctr in gear_to_replace:
        g = make_involute_spur_gear(new_t, mod, fw, br)
        g = g.translate(ctr)
        new_gears.append(g.val())

    # Assemble: all unchanged solids + the two new gears
    all_parts = [s.val() if hasattr(s, "val") else s for s in others] + new_gears
    result = cq.Workplane().add(cq.Compound.makeCompound(all_parts))

    # Export
    result.val().exportStep("/workspace/output/solution.step")
    print("Exported /workspace/output/solution.step")
    print("Re-cut 2 gears: 46->45 and 42->41 teeth (module and PA preserved, same axis/pos/facewidth/bore)")
    print(f"Total solids in output: {len(all_parts)}")


if __name__ == "__main__":
    main()
