"""Build the task's INPUT model: a pillow-block bearing housing for a 6204 deep-groove ball bearing.

Coordinate system (millimetres):
    shaft axis along +Y, through (X=0, Z=33); front face Y=0, back face Y=30; mounting face Z=0.

Geometry:
    base plate      X -60..60, Y 0..30, Z 0..15
    pedestal        X -30..30, Y 0..30, Z 0..33
    bearing boss    cylinder R35 about the shaft axis, Y 0..30 (top of the part at Z=68), trimmed flush with Z=0
    bearing seat    Ø47.0 (6204 outer ring) from the front face to the shoulder at Y=14.0
    shaft passage   Ø30.0 from the shoulder to the back face
    mounting holes  2 x Ø11.0 through the base at X=±45, Y=15

Usage:  python authoring/make_input.py [out.step]
"""
from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq

AXIS_Z = 33.0
WIDTH_Y = 30.0


def cyl_y(radius: float, y0: float, y1: float) -> cq.Solid:
    """A cylinder about the shaft axis from Y=y0 to Y=y1."""
    return cq.Solid.makeCylinder(radius, y1 - y0, cq.Vector(0, y0, AXIS_Z), cq.Vector(0, 1, 0))


def build_input() -> cq.Shape:
    base = cq.Solid.makeBox(120, WIDTH_Y, 15, cq.Vector(-60, 0, 0))
    pedestal = cq.Solid.makeBox(60, WIDTH_Y, AXIS_Z, cq.Vector(-30, 0, 0))
    boss = cyl_y(35.0, 0.0, WIDTH_Y)
    # the R35 boss would reach Z=-2; trim everything flush with the mounting face Z=0
    body = base.fuse(pedestal, boss).intersect(cq.Solid.makeBox(130, WIDTH_Y, 80, cq.Vector(-65, 0, 0))).clean()
    seat = cyl_y(47.0 / 2, -1.0, 14.0)
    passage = cyl_y(30.0 / 2, -1.0, WIDTH_Y + 1.0)
    holes = [cq.Solid.makeCylinder(5.5, 17.0, cq.Vector(x, 15.0, -1.0), cq.Vector(0, 0, 1)) for x in (-45.0, 45.0)]
    return body.cut(seat, passage, *holes).clean()


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "files" / "problem" / "model.step")
    out.parent.mkdir(parents=True, exist_ok=True)
    shape = build_input()
    cq.exporters.export(cq.Workplane().add(shape), str(out))
    print(f"input written: {out}  volume={shape.Volume():.1f} mm3")


if __name__ == "__main__":
    main()
