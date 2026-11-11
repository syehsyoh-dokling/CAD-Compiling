You are helping edit a CAD model of a Minarelli P6 moped engine bottom end (crankshaft, gearbox, clutch and primary drive).

You are given these input files:
- `/workspace/files/problem/model.step` — starting CAD model
- `/workspace/files/problem/render_front.png` — front view (looking down the shaft axes)
- `/workspace/files/problem/render_side.png` — side view
- `/workspace/files/problem/render_top.png` — top view
- `/workspace/files/problem/render_iso.png` — isometric view

You must write both required output files:
- `/workspace/output/solution.py` — CadQuery script that performs the edit
- `/workspace/output/solution.step` — the edited model (STEP)
Requirements:
- Re-cut exactly the two smallest gears of that constant-mesh cluster, each to one fewer tooth than it has now, as proper involute spur gears.
- Preserve the module and pressure angle of the cluster so the re-cut gears still mesh at the unchanged shaft centre distance.
- Keep each re-cut gear on the same rotation axis and axial position, with the same bore and face width as the gear it replaces.
- Keep the full cluster's tooth-count sequence strictly monotonic after the change.
- Leave every other gear in the cluster and every other part of the engine (crankshaft, clutch, primary drive, shift mechanism, shafts, bearings) unchanged.
- Use CadQuery only.
