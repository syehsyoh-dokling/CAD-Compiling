# Task: retrofit a pillow-block housing from a 6204 to a 6205 bearing

You are a mechanical design engineer. The file `/workspace/files/problem/model.step` contains a cast-iron pillow-block
housing that carries a **6204** deep-groove ball bearing. The machine is being upgraded to a 25 mm shaft, so the housing
must now carry a **6205** bearing. It must also be easier to service and to tension the drive belt.

Modify the model and write the result to `/workspace/output/solution.step`. Save the script that produced it as
`/workspace/output/solution.py`. Use any CAD library you like; the result must be a single valid solid.

## The part, as it is now (millimetres)

- Shaft axis along **+Y**, through **X = 0, Z = 33**. Front face at **Y = 0**, back face at **Y = 30**. Mounting face (underside) at **Z = 0**.
- Base plate 120 × 30 × 15 (X −60…60). Pedestal 60 wide. Bearing boss Ø70 about the shaft axis (trimmed flush with the mounting face), so the top of the part is at Z = 68.
- Bearing seat **Ø47.0** (the 6204 outer ring) from the front face to a shoulder at **Y = 14.0**. Behind the shoulder, a **Ø30.0** shaft passage runs to the back face.
- Two **Ø11.0** mounting holes through the base, at **X = ±45, Y = 15**.

## What to change

1. **Bearing seat for a 6205.** Look up the 6205's outer diameter and width yourself (ISO 15 / any bearing catalogue).
   Make the seat cylindrical at the bearing's nominal outer diameter (a slide fit is machined later; model it at
   nominal). The bearing is inserted from the front and sits against a shoulder. Place the shoulder so that the bearing,
   with its front face flush against a retaining ring, fits exactly. The stack from the front face is: a **2.00 mm**
   lip, then the ring groove (item 2), then the bearing.
2. **Retaining-ring groove.** Add the internal groove for a **DIN 472** retaining ring that fits the 6205's outer
   diameter. Use the standard groove diameter and groove width from DIN 472. The groove starts **2.00 mm** behind the
   front face, and its inner flank is flush with the bearing's front face.
3. **Shaft passage.** Behind the shoulder, open the passage to **Ø33.0** through to the back face. It must clear the
   6205's inner ring.
4. **Lead-in chamfer.** Add a **1.0 × 45°** chamfer at the mouth of the bearing seat on the front face.
5. **Belt-tension slots.** Replace each Ø11 mounting hole with a straight slot through the base. Each slot is **11.0 wide**
   and runs along X, centred on the old hole. Its arc centres are **12.0 mm apart**, so the slot is 23.0 mm end to end.

## Keep unchanged

- The overall envelope: 120 × 30 × 68 mm, in the same position.
- The base plate thickness (15), the pedestal, the Ø70 boss and every outer face.
- The shaft axis position. No other features, holes or material may be added or removed.

## How the result is judged

An automatic verifier measures the solid directly (point-in-solid probes and radial scans). It does not read your
feature tree, so any valid modelling approach passes. Each value is checked within its stated tolerance:

| Check | Expected | Tolerance |
|---|---|---|
| Single valid solid, loads from STEP | yes | n/a |
| Envelope (X, Y, Z) | 120 × 30 × 68, from (−60, 0, 0) | ±0.05 |
| Seat diameter | 6205 outer diameter, nominal | ±0.04 on Ø |
| Shoulder position | lip + groove width + bearing width | ±0.05 |
| Groove diameter / width / start | DIN 472 for the 6205 OD / DIN 472 width / Y = 2.00 | ±0.06 / ±0.05 / ±0.05 |
| Shaft passage | Ø33.0 | ±0.06 |
| Lead-in chamfer | 1.0 × 45° | ±0.1 |
| Slots | 11.0 wide, 23.0 end to end, centred on X = ±45, Y = 15 | ±0.05 |
| Everything else unchanged | material compared with the reference | ≤ 0.2 % of the volume differs |
