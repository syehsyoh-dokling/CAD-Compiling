You are helping edit a CAD model of a motor-mount bracket.

You are given these input files:
- `/workspace/files/problem/model.step` — starting CAD model
- `/workspace/files/problem/render_front.png` — front view
- `/workspace/files/problem/render_side.png` — side view
- `/workspace/files/problem/render_iso.png` — isometric view

You must write both required output files:
- `/workspace/output/solution.py` — CadQuery script that performs the edit
- `/workspace/output/solution.step` — the edited model (STEP)
Requirements:
- Add the four clearance holes for the inferred frame, centered on the ballscrew/
  coupling axis, through the base plate.
- Keep the existing NEMA 23 mounting holes — do not fill, move, or remove them.
- Preserve the central coupling/pilot bore, the ballscrew bearing seat and its
  retainer holes on the top plate, the side frame-mounting holes, and the overall
  bracket envelope. Only the four new holes should change.
- The result must be a single clean, valid, nonempty model.
- Use CadQuery only.
