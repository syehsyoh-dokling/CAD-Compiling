"""
Task-specific deterministic verifier: hydraulic rod-gland rod-Ø retrofit.

The solver re-bores the gland for a larger piston rod in the SAME cylinder tube.
Every rod-referenced internal bore (wiper pocket + its retention groove, the rod
guide lands, the rod-seal groove, the main bore, the inboard lead-in and
counterbore) must grow by the rod step (Ø50 -> Ø56, i.e. +6 mm on diameter / +3 mm
on radius), preserving every radial clearance and every seal/wiper groove section
and keeping the axial layout. Every tube-referenced feature (mounting thread,
flange head OD + spanner notches, pilot register + lead-in, end faces, length) is
frozen.

Verification is representation-agnostic: it marches MATERIAL (point-in-solid) along
radii on the gland axis (global X through Y=0, Z=0). The bore axis is clean, so the
first radius with material at a station is that station's bore-wall radius, and the
last radius with material is the local outer radius. Correctness is pinned by the
new internal diameters at their (unchanged) axial stations, plus checks that the
external/tube-mounting envelope is untouched and that the seal groove kept its
axial position (so a plain straight bore-out cannot pass).

Inferred targets (no numbers are given in the prompt):
  - rod-seal groove  Ø60 -> Ø66 (r 33.0)   |  main bore        Ø55 -> Ø61 (r 30.5)
  - rod guide lands  Ø51.5-> Ø57.5(r 28.75) |  inboard counterb. Ø60 -> Ø66 (r 32.985)
  - wiper pocket     Ø62 -> Ø68 (r 34.0)   |  wiper retention   Ø64.5-> Ø70.5(r 35.25)
  - frozen: thread Ø112.5, register Ø105, flange OD Ø127, length 75.
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
# TASK-SPECIFIC HELPERS (radial material probing on the gland axis)
# ---------------------------------------------------------------------------
# Axis = global X through (AXIS_Y, AXIS_Z). Probes sample point-in-solid on rays
# from the axis at a fixed X station. The gland is a single clean solid of
# revolution, so the FIRST radius with material at a station is the bore wall and
# the LAST radius with material is the local outer radius.

PROBE_TOL = 1e-3
AXIS_Y = 0.0
AXIS_Z = 0.0
R_TOL = 0.7            # radius tolerance: old/new bore walls differ by 3 mm; 0.7 is safe
BISECT_ITERS = 18     # ~45 mm / 2^18 -> sub-0.001 mm radius resolution
# isInside on this solid is ~20 ms (helical-thread B-rep), so probes BISECT the
# monotonic material/air boundary instead of marching: cost is ~18 calls per ray
# rather than hundreds. The bore is a clean solid of revolution, so one ray finds
# the inner wall; the min over two opposed rays guards against slight asymmetry.
INNER_ANGLES = (0.0, math.pi)


def material_at(shape, x: float, r: float, theta: float) -> bool:
    """True if the axis point at (x, radius r, angle theta) is inside the solid."""

    import cadquery as cq

    p = cq.Vector(x, AXIS_Y + r * math.cos(theta), AXIS_Z + r * math.sin(theta))
    return shape.isInside(p, PROBE_TOL)


def _wall_inward_to_outward(shape, x: float, theta: float,
                            r_void: float, r_solid: float) -> float:
    """Bisect the air->material boundary between a void radius and a solid radius.

    r_void < r_solid, material_at(r_void)=False, material_at(r_solid)=True. Returns
    the smallest radius that is inside material (the inner bore wall).
    """

    lo, hi = r_void, r_solid
    for _ in range(BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        if material_at(shape, x, mid, theta):
            hi = mid
        else:
            lo = mid
    return hi


def _wall_outward(shape, x: float, theta: float,
                  r_solid: float, r_void: float) -> float:
    """Bisect the material->air boundary between a solid radius and a void radius.

    r_solid < r_void, material_at(r_solid)=True, material_at(r_void)=False. Returns
    the largest radius that is inside material (the outer surface) at this angle.
    """

    lo, hi = r_solid, r_void
    for _ in range(BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        if material_at(shape, x, mid, theta):
            lo = mid
        else:
            hi = mid
    return lo


def inner_radius(shape, x: float, r_solid: float = 45.0) -> float:
    """Smallest radius with material at station x (the bore wall).

    r_solid (45 mm) sits in the wall metal at every bore station (below the thread
    root Ø109.3 / register Ø105, above every bore wall Ø70.5). The axis (r=0) is in
    the open through bore. Bisect between them.
    """

    best = r_solid
    for theta in INNER_ANGLES:
        if not material_at(shape, x, r_solid, theta):
            continue  # no wall metal where expected on this ray; skip it
        if material_at(shape, x, 0.0, theta):
            return 0.0  # no through bore here at all
        best = min(best, _wall_inward_to_outward(shape, x, theta, 0.0, r_solid))
    return best


def outer_radius(shape, x: float, r_solid: float, r_void: float, angles: int = 12) -> float:
    """Largest radius with material at station x (local outer envelope).

    r_solid is inside the part wall, r_void is clear of the outer surface. Max over
    angles so spanner notches / thread-helix gaps do not undercount the envelope.
    """

    best = 0.0
    for a in range(angles):
        theta = 2 * math.pi * a / angles
        if not material_at(shape, x, r_solid, theta):
            continue
        if material_at(shape, x, r_void, theta):
            best = max(best, r_void)  # solid out past r_void; report the bound
            continue
        best = max(best, _wall_outward(shape, x, theta, r_solid, r_void))
    return best


def void_axial_span(shape, radius: float, x_lo: float, x_hi: float,
                    n: int = 120) -> tuple[float, float]:
    """Axial (X) extent that is VOID at a fixed radius (theta=0) over [x_lo, x_hi].

    Used to locate the rod-seal groove: at a radius above the guide lands but below
    the seal-groove bottom, only the groove reads as open, so its X window pins the
    groove's axial position and width.
    """

    xs = [x_lo + (x_hi - x_lo) * i / n for i in range(n + 1)]
    void = [x for x in xs if not material_at(shape, x, radius, 0.0)]
    if not void:
        return (0.0, 0.0)
    return (min(void), max(void))


# ---------------------------------------------------------------------------
# TASK-SPECIFIC CHECKS
# ---------------------------------------------------------------------------


def build_task_checks(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return task-specific deterministic checks for the rod-Ø retrofit re-bore."""

    output_shape = context["output_shape"]
    checks: list[dict[str, Any]] = []

    # Measure every internal bore wall once at its (unchanged) axial station.
    bore = {
        "main_bore": (5.0, 30.5),         # Ø55 -> Ø61
        "seal_groove": (-16.0, 33.0),     # Ø60 -> Ø66
        "guide_outboard": (-23.5, 28.75),  # Ø51.5 -> Ø57.5
        "guide_inboard": (-9.25, 28.75),  # Ø51.5 -> Ø57.5
        "wiper_pocket": (-30.0, 34.0),    # Ø62 -> Ø68
        "wiper_retain": (-34.1, 35.25),   # Ø64.5 -> Ø70.5
        "counterbore": (31.0, 32.985),    # Ø60 -> Ø66
    }
    meas = {name: inner_radius(output_shape, x) for name, (x, _exp) in bore.items()}

    # 1. CRITICAL — the main rod bore is bored to the new rod (Ø61). Reading the
    # bore wall at the mid main-bore station separates Ø55 (unchanged) from Ø61.
    # Tolerance source: rod step Ø50->Ø56 => bore Ø55->Ø61; +/-0.7 mm radius band.
    # Hackability: unchanged model reads Ø55 and fails; a wrong step fails.
    x, _ = bore["main_bore"]
    d_main = 2.0 * meas["main_bore"]
    checks.append(
        critical(
            check_result(
                "main_bore_resized",
                "Main rod bore re-cut to Ø61 for the Ø56 rod.",
                within_abs(d_main, 61.0, 2 * R_TOL),
                {"diameter": round(d_main, 2), "expected": 61.0, "station_x": x,
                 "tol": round(2 * R_TOL, 2)},
            )
        )
    )

    # 2. CRITICAL — the rod-seal groove also moved to the new rod (Ø66), proving the
    # re-bore covered the seal housing, not just the through bore. A naive straight
    # bore-out (only the main bore) leaves the groove at Ø60 and fails here.
    # Tolerance source: groove Ø60->Ø66 (section preserved); +/-0.7 mm radius band.
    x, _ = bore["seal_groove"]
    d_seal = 2.0 * meas["seal_groove"]
    checks.append(
        critical(
            check_result(
                "seal_groove_resized",
                "Rod-seal groove re-cut to Ø66 (seal section preserved on the bigger rod).",
                within_abs(d_seal, 66.0, 2 * R_TOL),
                {"diameter": round(d_seal, 2), "expected": 66.0, "station_x": x,
                 "tol": round(2 * R_TOL, 2)},
            )
        )
    )

    # 3. SUPPORTIVE — both rod guide lands grew to Ø57.5 (guide clearance preserved
    # over the bigger rod). Catches a solution that resized grooves but not lands.
    # Tolerance source: land Ø51.5->Ø57.5; +/-0.7 mm radius.
    d_go = 2.0 * meas["guide_outboard"]
    d_gi = 2.0 * meas["guide_inboard"]
    lands_ok = within_abs(d_go, 57.5, 2 * R_TOL) and within_abs(d_gi, 57.5, 2 * R_TOL)
    checks.append(
        check_result(
            "guide_lands_resized",
            "Both rod guide lands re-cut to Ø57.5 (running clearance preserved).",
            lands_ok,
            {"outboard": round(d_go, 2), "inboard": round(d_gi, 2), "expected": 57.5},
        )
    )

    # 4. SUPPORTIVE — the outboard wiper pocket (Ø68) and its retention groove
    # (Ø70.5) both grew with the rod. Catches a solution that ignored the wiper end.
    # Tolerance source: pocket Ø62->Ø68, retain Ø64.5->Ø70.5; +/-0.7 mm radius.
    d_wp = 2.0 * meas["wiper_pocket"]
    d_wr = 2.0 * meas["wiper_retain"]
    wiper_ok = within_abs(d_wp, 68.0, 2 * R_TOL) and within_abs(d_wr, 70.5, 2 * R_TOL)
    checks.append(
        check_result(
            "wiper_features_resized",
            "Wiper pocket (Ø68) and its retention groove (Ø70.5) re-cut to the new rod.",
            wiper_ok,
            {"pocket": round(d_wp, 2), "retain": round(d_wr, 2),
             "expected_pocket": 68.0, "expected_retain": 70.5},
        )
    )

    # 5. SUPPORTIVE — inboard (pressure-side) counterbore grew to Ø66. Catches a
    # solution that left the oil-side bore at Ø60.
    # Tolerance source: counterbore Ø60->Ø66; +/-0.7 mm radius.
    d_cb = 2.0 * meas["counterbore"]
    checks.append(
        check_result(
            "counterbore_resized",
            "Inboard counterbore re-cut to Ø66 on the bigger rod.",
            within_abs(d_cb, 66.0, 2 * R_TOL),
            {"diameter": round(d_cb, 2), "expected": 66.0},
        )
    )

    # 6. SUPPORTIVE — the rod-seal groove kept its axial position and width. At a
    # radius between the new guide lands (Ø57.5/r28.75) and the new groove bottom
    # (Ø66/r33), only the groove reads open. Its X window must stay ~[-21,-11]
    # (width ~10, centre ~-16). A plain straight bore-out has no groove here.
    # Tolerance source: seed groove axial geometry; +/-1.5 mm on width and centre.
    v_lo, v_hi = void_axial_span(output_shape, 31.0, -26.0, -7.5)
    width = v_hi - v_lo
    centre = (v_lo + v_hi) / 2.0
    axial_ok = within_abs(width, 10.0, 1.5) and within_abs(centre, -16.0, 1.5)
    checks.append(
        check_result(
            "seal_groove_axial_preserved",
            "Rod-seal groove kept its axial position/width (~10 mm at x~-16).",
            axial_ok,
            {"void_span": [round(v_lo, 2), round(v_hi, 2)],
             "width": round(width, 2), "centre": round(centre, 2)},
        )
    )

    # 7. SUPPORTIVE — tube-mounting thread is preserved (not removed/shrunk). Outer
    # material in the threaded zone must still reach the thread (~Ø112.5 crest).
    # Tolerance source: seed thread crest Ø112.5; require >= Ø108 (thread present).
    d_thread = 2.0 * outer_radius(output_shape, -12.0, 45.0, 62.0)
    thread_ok = d_thread >= 108.0
    checks.append(
        check_result(
            "thread_preserved",
            "External mounting thread is intact (crest ~Ø112.5).",
            thread_ok,
            {"outer_diameter": round(d_thread, 2), "min_expected": 108.0},
        )
    )

    # 8. SUPPORTIVE — pilot register that fits the tube bore is unchanged (Ø105).
    # Tolerance source: seed register Ø105; +/-0.7 mm radius. Catches a solution
    # that grew the OUTSIDE (e.g. uniform scale) along with the bore.
    d_reg = 2.0 * outer_radius(output_shape, 22.5, 45.0, 56.0, angles=6)
    checks.append(
        check_result(
            "register_preserved",
            "Pilot register that pilots into the tube bore is unchanged (Ø105).",
            within_abs(d_reg, 105.0, 2 * R_TOL),
            {"outer_diameter": round(d_reg, 2), "expected": 105.0},
        )
    )

    # 9. SUPPORTIVE — overall envelope preserved: flange OD ~Ø127 and length 75 mm.
    # Pins "tube interface frozen" / "no scaling": a uniform scale or a moved face
    # changes these even when the bore looks right.
    # Tolerance source: seed envelope; +/-0.4 mm.
    bb = output_shape.BoundingBox()
    od = max(bb.ylen, bb.zlen)
    env_ok = within_abs(od, 127.0, 0.4) and within_abs(bb.xlen, 75.0, 0.4)
    checks.append(
        check_result(
            "envelope_preserved",
            "Flange OD (~Ø127) and overall length (75 mm) are unchanged.",
            env_ok,
            {"flange_od": round(od, 2), "length": round(bb.xlen, 2),
             "expected_od": 127.0, "expected_length": 75.0},
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
