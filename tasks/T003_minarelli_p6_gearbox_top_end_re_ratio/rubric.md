1. Full credit requires: the two smallest gears of the constant-mesh cluster are each re-cut to one fewer tooth (raising the top two ratios), and the solution clearly targets those two gears and no others. Major failures: changed the wrong gears, changed only one, added teeth instead of removing, re-ratioed gears on the wrong shaft, or left the cluster unchanged.
Weight: 20

2. Full credit requires: both re-cut gears are valid involute spur gears with the same module and pressure angle as the rest of the cluster, sound tooth geometry (no degenerate/self-intersecting profile), and a watertight solid that exports cleanly. The new tip/root diameters follow standard full-depth relations for the new counts. Major failures: distorted or non-involute teeth, wrong module (tip diameter does not match m·(z+2) for the new count), invalid/exploded solids, or a "gear" that is really a plain disc.
Weight: 20

3. Full credit requires: the centre-distance/meshing constraint is respected — the module is held so each re-cut gear still meshes with its unchanged partner (the mainshaft tooth removed is implicitly compensated on the countershaft), and the six-gear tooth sequence stays strictly monotonic after the change. Major failures: a re-cut that would no longer mesh (module changed to force a count), a non-monotonic or reversed ladder, two gears ending up equal, or the axial station / rotation axis moved.
Weight: 20

4. Full credit requires: the other four cluster gears keep their tooth counts, and the crankshaft, clutch, primary drive, shift mechanism, shafts and bearings are untouched; each re-cut gear keeps its original bore and face width. Major failures: collateral edits to other gears or parts, a changed/blocked bore, a different face width, or a global rebuild that disturbs unrelated geometry.
Weight: 15

5. Full credit requires: the choice of "taller top two" is realized sensibly — the two genuinely highest (smallest) gears are picked, the one-tooth step is applied consistently, and the result is a usable gearbox (sane ratio progression, gears that still fit on the shaft). Major failures: an arbitrary or physically implausible re-ratio, ignoring the meshing/centre-distance reasoning, or a ladder that no longer makes sense.
Weight: 10

6. Full credit requires: solution.py is readable and parametric — module, tooth counts and gear placement are named/derived rather than magic literals, and the gear construction is reproducible. Major failures: opaque hard-coded geometry, dead or copy-pasted code, or a script that cannot regenerate the exported STEP.
Weight: 10

7. Full credit requires: evidence the model was inspected (counts/module/axis read from the part), both output files written to the required paths, and a brief rationale for the chosen counts. Major failures: no inspection, missing outputs, or wrong file paths.
Weight: 5
