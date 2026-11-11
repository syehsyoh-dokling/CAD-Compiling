"""
Task-specific deterministic verifier: Minarelli P6 gearbox top-end re-ratio.

The solver receives the full bottom-end assembly (116 solids) and must re-cut the
two TOP gears of the mainshaft constant-mesh cluster "one tooth-step taller",
holding the module and the fixed shaft centre distance (so a meshing pair's tooth
counts keep summing to the same value), and keeping the six-gear ratio ladder
strictly monotonic.

Inferred target (no numbers are given in the prompt):
  - Mainshaft axis = global X through (Y=4.48, Z=86.36); six involute spur gears
    read 33, 30, 27, 25, 23, 21 teeth at module m = tip/(z+2) = 1.766 mm.
  - Shaft centre distance 38 mm + module 1.766 -> meshing pair tooth-sum = 43.
  - "Top two, one step taller" = one FEWER mainshaft tooth on each of the two
    smallest gears: 5th 23T -> 22T, 6th 21T -> 20T (partners 20->21, 22->23).
  - New ladder 33,30,27,25,22,20 stays strictly monotonic.

Verification is representation-agnostic: it probes MATERIAL (point-in-solid) on
rings around the mainshaft axis, restricted to the few solids at each axial
station so it stays tractable on the 116-solid assembly. Tooth counts are read at
each gear's module-derived pitch radius. The shaft runs THROUGH the gear bores,
so bore/centre-open probes are intentionally NOT used; correctness is pinned by
tooth count + tip diameter (module) + a solid rim under the teeth.
"""

from __future__ import annotations

import inspect
import json
import math
import os
from pathlib import Path
from typing import Any


DEFAULT_INPUT_STEP = "/workspace/files/problem/model.step"
DEFAULT_OUTPUT_STEP = "/workspace/output/solution.step"
DEFAULT_OUTPUT_PY = "/workspace/output/solution.py"
DEFAULT_GT_STEP = "/workspace/grader-support/gt_solution.step"


def clamp_score(value: float) -> float:
    """Clamp a score to [0, 1]."""

    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(1.0, value))


def current_check_function_name() -> str:
    """Return the verifier helper function that produced a check result."""

    frame = inspect.currentframe()
    if frame is None or frame.f_back is None or frame.f_back.f_back is None:
        return "unknown_check_function"
    return frame.f_back.f_back.f_code.co_name


def check_result(
    check_id: str,
    description: str,
    passed: bool,
    details: dict[str, Any] | None = None,
    score: float | None = None,
    function_name: str | None = None,
) -> dict[str, Any]:
    """Create one fixed-contract criterion result."""

    resolved_score = 1.0 if passed else 0.0
    if score is not None:
        resolved_score = score

    return {
        "id": check_id,
        "description": description,
        "function": function_name or current_check_function_name(),
        "passed": bool(passed),
        "score": round(clamp_score(float(resolved_score)), 4),
        "details": details or {},
    }


def aggregate_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate task checks into the result contract consumed by grade.py."""

    if not checks:
        return {
            "score": 0.0,
            "passed": False,
            "criteria": [
                check_result(
                    "no_task_checks",
                    "No task-specific checks were configured.",
                    False,
                    function_name="aggregate_checks",
                )
            ],
            "failed_check_ids": ["no_task_checks"],
            "failed_check_functions": ["aggregate_checks"],
            "critical_failed": True,
        }

    failed_check_ids = [
        str(check["id"]) for check in checks if not bool(check.get("passed", False))
    ]
    failed_check_functions = [
        str(check.get("function", "unknown_check_function"))
        for check in checks
        if not bool(check.get("passed", False))
    ]
    passed = not failed_check_ids
    critical_failed = any(
        bool(check.get("critical")) and not bool(check.get("passed"))
        for check in checks
    )
    check_scores = [
        clamp_score(
            float(check.get("score", 1.0 if bool(check.get("passed", False)) else 0.0))
        )
        for check in checks
    ]
    fraction_score = sum(check_scores) / len(check_scores)
    return {
        "score": round(fraction_score, 4),
        "passed": passed,
        "criteria": checks,
        "failed_check_ids": failed_check_ids,
        "failed_check_functions": failed_check_functions,
        "critical_failed": critical_failed,
    }


def critical(check: dict[str, Any]) -> dict[str, Any]:
    """Mark a check as core to task correctness."""

    check["critical"] = True
    return check


def load_step(path: Path):
    """Load a STEP file as a CadQuery shape."""

    import cadquery as cq

    return cq.importers.importStep(str(path)).val()


def within_abs(value: float, expected: float, tolerance: float) -> bool:
    """Check absolute tolerance."""

    return abs(value - expected) <= tolerance


# ---------------------------------------------------------------------------
# TASK-SPECIFIC HELPERS (material probing on the mainshaft X axis)
# ---------------------------------------------------------------------------
# The mainshaft rotation axis is the global X axis through (Y0, Z0). Probes
# sample point-in-solid on YZ circles around that axis. To stay tractable on the
# 116-solid assembly (each isInside is ~6 ms), probing is restricted to the few
# solids near the axis, and per station to the solids spanning that X coordinate.

PROBE_TOL = 1e-3
AXIS_Y = 4.48          # mainshaft axis, measured from the seed
AXIS_Z = 86.36
MODULE = 1.766         # tip-derived module of the cluster, preserved (mesh)
NEAR_AXIS_R = 22.0     # keep cluster gears + shaft, drop off-axis assembly parts

# Each cluster gear: label -> (axial station x, expected post-edit teeth). The two
# starred gears are the re-cut targets; the rest must be carried through unchanged.
GEAR_STATIONS = [
    ("1st", -128.7, 33),
    ("2nd", -103.2, 30),
    ("3rd", -93.5, 27),
    ("4th", -69.4, 25),
    ("5th", -60.2, 22),   # re-cut: 23 -> 22
    ("6th", -34.3, 20),   # re-cut: 21 -> 20
]
EDITED = {
    "5th": {"x": -60.2, "teeth": 22, "old": 23, "face": 8.0},
    "6th": {"x": -34.3, "teeth": 20, "old": 21, "face": 9.0},
}


def solids_of(shape) -> list:
    """Return the list of solids in a shape (or the shape itself if atomic)."""

    solids = shape.Solids()
    return solids if solids else [shape]


def near_axis_solids(shape) -> list:
    """Solids whose centre lies near the mainshaft axis (cluster gears + shaft)."""

    out = []
    for s in solids_of(shape):
        c = s.Center()
        if math.hypot(c.y - AXIS_Y, c.z - AXIS_Z) <= NEAR_AXIS_R:
            out.append(s)
    return out


def station_solids(near: list, x: float, tol: float = 0.5) -> list:
    """Subset of near-axis solids whose X span covers the station plane."""

    out = []
    for s in near:
        b = s.BoundingBox()
        if b.xmin - tol <= x <= b.xmax + tol:
            out.append(s)
    return out


def material_at(solids: list, x: float, y: float, z: float) -> bool:
    """True if (x, y, z) lies inside any of the given solids."""

    import cadquery as cq

    point = cq.Vector(x, y, z)
    return any(solid.isInside(point, PROBE_TOL) for solid in solids)


def count_teeth_on_ring(solids: list, x: float, radius: float, samples: int = 480) -> int:
    """Count teeth as air->material transitions on a YZ circle around the axis."""

    states = [
        material_at(solids, x,
                    AXIS_Y + radius * math.cos(2 * math.pi * i / samples),
                    AXIS_Z + radius * math.sin(2 * math.pi * i / samples))
        for i in range(samples)
    ]
    return sum(1 for i in range(samples) if states[i] and not states[i - 1])


def outer_material_radius(solids: list, x: float, r_lo: float, r_hi: float,
                          steps: int = 28, angles: int = 24) -> float:
    """Largest radius (around the axis) that still has tooth-tip material."""

    last = 0.0
    for k in range(steps + 1):
        r = r_lo + (r_hi - r_lo) * k / steps
        if any(material_at(solids, x,
                           AXIS_Y + r * math.cos(2 * math.pi * a / angles),
                           AXIS_Z + r * math.sin(2 * math.pi * a / angles))
               for a in range(angles)):
            last = r
    return last


def material_fraction_on_ring(solids: list, x: float, radius: float, samples: int = 180) -> float:
    """Fraction of a YZ circle (around the axis) that is inside material."""

    hits = sum(
        1
        for i in range(samples)
        if material_at(solids, x,
                       AXIS_Y + radius * math.cos(2 * math.pi * i / samples),
                       AXIS_Z + radius * math.sin(2 * math.pi * i / samples))
    )
    return hits / samples


def axial_material_extent(solids: list, radius: float, x_lo: float, x_hi: float,
                          theta: float, samples: int = 60) -> float:
    """Axial (X) extent of material at a fixed radius/angle around the axis."""

    y = AXIS_Y + radius * math.cos(theta)
    z = AXIS_Z + radius * math.sin(theta)
    xs = [x_lo + (x_hi - x_lo) * i / (samples - 1) for i in range(samples)]
    hits = [x for x in xs if material_at(solids, x, y, z)]
    if not hits:
        return 0.0
    return max(hits) - min(hits)


def far_volume(shape) -> float:
    """Total volume of solids well away from the mainshaft (collateral check)."""

    total = 0.0
    for s in solids_of(shape):
        c = s.Center()
        if math.hypot(c.y - AXIS_Y, c.z - AXIS_Z) > 45.0:
            total += float(s.Volume())
    return total


# ---------------------------------------------------------------------------
# TASK-SPECIFIC CHECKS
# ---------------------------------------------------------------------------


def build_task_checks(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return task-specific deterministic checks for the gearbox re-ratio."""

    input_shape = context["input_shape"]
    output_shape = context["output_shape"]

    near = near_axis_solids(output_shape)

    # Read all six mainshaft tooth counts once (each at its module-derived pitch
    # radius), then derive the edit / preservation / ladder checks from them.
    counts: dict[str, int] = {}
    for label, x, znom in GEAR_STATIONS:
        ss = station_solids(near, x)
        pitch_r = MODULE * znom / 2.0
        counts[label] = count_teeth_on_ring(ss, x, pitch_r)

    checks: list[dict[str, Any]] = []

    # 1. CRITICAL — 6th gear re-cut to 20T. Counting at the 20T pitch radius
    # (r=17.66) cleanly separates 19/20/21/22; the unchanged 21T reads 21 here.
    # Tolerance source: inferred z=20 (one tooth taller than 21T); integer exact.
    # Hackability: unchanged 21T fails; a smooth disc reads 0; wrong count fails.
    checks.append(
        critical(
            check_result(
                "reratio_6th_20T",
                "Top (6th) gear re-cut to 20 teeth at its mainshaft station.",
                counts["6th"] == 20,
                {"teeth": counts["6th"], "expected": 20,
                 "pitch_radius": round(MODULE * 20 / 2.0, 3), "station_x": -34.3},
            )
        )
    )

    # 2. CRITICAL — 5th gear re-cut to 22T (the coupled second edit). Counting at
    # the 22T pitch radius (r=19.43) separates 21/22/23; the unchanged 23T reads
    # 23 here. Both edits are required: changing only one fails this gate.
    # Tolerance source: inferred z=22 (one tooth taller than 23T); integer exact.
    checks.append(
        critical(
            check_result(
                "reratio_5th_22T",
                "Second-from-top (5th) gear re-cut to 22 teeth at its station.",
                counts["5th"] == 22,
                {"teeth": counts["5th"], "expected": 22,
                 "pitch_radius": round(MODULE * 22 / 2.0, 3), "station_x": -60.2},
            )
        )
    )

    # 3. SUPPORTIVE — the other four gears are untouched (33/30/27/25). Catches an
    # over-broad rebuild or collateral re-cutting of the wrong gears.
    # Tolerance source: seed measurement; integer exact.
    others = {k: counts[k] for k in ("1st", "2nd", "3rd", "4th")}
    others_ok = others == {"1st": 33, "2nd": 30, "3rd": 27, "4th": 25}
    checks.append(
        check_result(
            "other_gears_unchanged",
            "The other four mainshaft gears keep 33/30/27/25 teeth.",
            others_ok,
            {"counts": others, "expected": {"1st": 33, "2nd": 30, "3rd": 27, "4th": 25}},
        )
    )

    # 4. SUPPORTIVE — ratio ladder stays strictly monotonic (a real gearbox
    # constraint). After the edit the mainshaft counts must read 33,30,27,25,22,20
    # strictly descending. Catches non-monotonic / inverted re-ratios.
    ladder = [counts[k] for k, _, _ in GEAR_STATIONS]
    monotonic = all(ladder[i] > ladder[i + 1] for i in range(len(ladder) - 1))
    ladder_ok = monotonic and ladder == [33, 30, 27, 25, 22, 20]
    checks.append(
        check_result(
            "monotonic_ratio_ladder",
            "Six-gear tooth ladder is strictly monotonic 33,30,27,25,22,20.",
            ladder_ok,
            {"ladder": ladder, "expected": [33, 30, 27, 25, 22, 20], "monotonic": monotonic},
        )
    )

    # 5. SUPPORTIVE — module preserved on the re-cut gears. Tip diameter must equal
    # m*(z+2): 6th -> 38.85 mm, 5th -> 42.38 mm. With the counts fixed above, this
    # pins module = 1.766 (the gears still mesh with their partners).
    # Tolerance source: standard gear relation; +/-1.5 mm for tip/faceting.
    tip6 = 2.0 * outer_material_radius(station_solids(near, -34.3), -34.3, 15.0, 23.0)
    tip5 = 2.0 * outer_material_radius(station_solids(near, -60.2), -60.2, 17.0, 25.0)
    module_ok = within_abs(tip6, MODULE * 22, 1.5) and within_abs(tip5, MODULE * 24, 1.5)
    checks.append(
        check_result(
            "module_preserved",
            "Re-cut gears keep module 1.766 (tip Ø 6th~38.9, 5th~42.4).",
            module_ok,
            {"tip_6th": round(tip6, 2), "expected_6th": round(MODULE * 22, 2),
             "tip_5th": round(tip5, 2), "expected_5th": round(MODULE * 24, 2),
             "tolerance": 1.5},
        )
    )

    # 6. SUPPORTIVE — each re-cut gear is a real toothed wheel (solid rim under the
    # teeth, full face width), not floating teeth or a gutted ring. Probe a full
    # ring just below the new root circle and the axial extent there.
    # Tolerance source: GT geometry; face within +/-1.5 mm of the seed value.
    rim_ok = True
    rim_details: dict[str, Any] = {}
    for lbl, spec in EDITED.items():
        x = spec["x"]
        ss = station_solids(near, x)
        root_r = MODULE * (spec["teeth"] - 2.5) / 2.0
        probe_r = root_r - 1.5
        frac = material_fraction_on_ring(ss, x, probe_r)
        extent = axial_material_extent(ss, probe_r, x - spec["face"], x + spec["face"], theta=0.0)
        ok = frac >= 0.99 and within_abs(extent, spec["face"], 1.5)
        rim_ok = rim_ok and ok
        rim_details[lbl] = {"solid_fraction": round(frac, 3), "face": round(extent, 2),
                            "expected_face": spec["face"], "probe_r": round(probe_r, 2)}
    checks.append(
        check_result(
            "rim_and_face_preserved",
            "Each re-cut gear has a full solid rim under the teeth and its face width.",
            rim_ok,
            rim_details,
        )
    )

    # 7. SUPPORTIVE — the rest of the engine is untouched. Total volume of all
    # solids well away from the mainshaft must match the input (crank, clutch,
    # primary, shift parts, other shaft). Catches collateral edits elsewhere.
    # Tolerance source: identity preservation; 0.5% for export round-off.
    in_far = far_volume(input_shape)
    out_far = far_volume(output_shape)
    far_ok = in_far > 0 and abs(out_far - in_far) / in_far <= 0.005
    checks.append(
        check_result(
            "rest_of_engine_preserved",
            "All parts away from the mainshaft are unchanged (no collateral edits).",
            far_ok,
            {"input_far_volume": round(in_far, 1), "output_far_volume": round(out_far, 1),
             "rel_tol": 0.005},
        )
    )

    return checks


def run_tests(context: dict[str, Any]) -> dict[str, Any]:
    """Fixed entrypoint called by grade.py."""

    checks = build_task_checks(context)
    return aggregate_checks(checks)


def main() -> int:
    """Standalone smoke-test entrypoint for local authoring."""

    paths = {
        "input_step": os.environ.get("INPUT_STEP", DEFAULT_INPUT_STEP),
        "output_step": os.environ.get("OUTPUT_STEP", DEFAULT_OUTPUT_STEP),
        "output_py": os.environ.get("OUTPUT_PY", DEFAULT_OUTPUT_PY),
        "gt_step": os.environ.get("GT_STEP", DEFAULT_GT_STEP),
    }
    context = {
        "paths": paths,
        "input_shape": load_step(Path(paths["input_step"])),
        "output_shape": load_step(Path(paths["output_step"])),
        "gt_shape": load_step(Path(paths["gt_step"])) if Path(paths["gt_step"]).exists() else None,
    }
    print(json.dumps(run_tests(context), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
