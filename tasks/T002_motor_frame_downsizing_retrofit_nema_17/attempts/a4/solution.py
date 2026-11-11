import cadquery as cq
from cadquery import importers, exporters

bracket = importers.importStep("/workspace/files/problem/model.step")

offset = 31.0 / 2
hole_r = 3.5 / 2
positions = [(offset, offset), (offset, -offset), (-offset, -offset), (-offset, offset)]

plate_bottom_z = -71.5
plate_thick = 10.1

cutters = (
    cq.Workplane("XY")
    .workplane(offset=plate_bottom_z)
    .pushPoints(positions)
    .circle(hole_r)
    .extrude(plate_thick)
)

result = bracket.cut(cutters).clean()

solids_list = result.solids().vals()
fused = solids_list[0]
for s in solids_list[1:]:
    fused = fused.fuse(s)
result = cq.Workplane("XY").add(fused).clean()

exporters.export(result, "/workspace/output/solution.step")
