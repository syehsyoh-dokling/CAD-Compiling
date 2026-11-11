You are helping edit a CAD model of a screw-in hydraulic cylinder rod gland (the
threaded head that screws into the end of the cylinder tube and seals around the
piston rod).

You are given these input files:
- `/workspace/files/problem/model.step` — starting CAD model
- `/workspace/files/problem/render_front.png` — front view (looking down the bore)
- `/workspace/files/problem/render_side.png` — side view
- `/workspace/files/problem/render_top.png` — top view
- `/workspace/files/problem/render_iso.png` — isometric view

You must write both required output files:
- `/workspace/output/solution.py` — CadQuery script that performs the edit
- `/workspace/output/solution.step` — the edited model (STEP)
Requirements:
- Open up the rod bore and all of its internal seal/wiper grooves, guide lands,
  lead-in and counterbore for the new Ø56 rod (up from Ø50), preserving each
  original running clearance and each seal/wiper groove cross-section.
- Keep every internal feature at its existing axial position and width; only the
  diameters change.
- Do not alter any tube-mounting geometry: the external thread, the flange head
  and its spanner notches, the pilot register and its lead-in, the end faces, and
  the overall length must be preserved.
- Use CadQuery only.
