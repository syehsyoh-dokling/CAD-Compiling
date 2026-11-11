"""
Task-specific deterministic verifier: motor-frame downsizing retrofit (hard).

This is the inference variant: the instruction gives NO numbers. The solver must
work out the smallest STANDARD NEMA frame whose bolt circle still clears the
Ø38.1 pilot bore (NEMA 14 = 26 mm square and NEMA 11 = 23 mm square fall inside
the bore; NEMA 17 = 31 mm square is the smallest that fits), then derive the M3
fastener and its clearance hole and add the pattern through the motor-mount base
plate, centered on the ballscrew axis, preserving the existing NEMA 23 holes, the
pilot bore, the ballscrew bearing seat, and the envelope.

The CORRECT inferred geometry is the NEMA 17 pattern (four M3 clearance holes on a
31.0 mm square), so the verified target is identical to the reference solution.

Verification is representation-agnostic: it probes MATERIAL (point-in-solid) on
the whole output compound rather than matching face/solid counts, so any valid
modeling approach passes. The ballscrew axis (X=0, Y=0), base-plate band, and
pilot-bore radius are measured from the seed; the NEMA 17 pitch (31.0 mm) and the
M3 clearance diameter (Ø3.4, ISO 273 medium) are the inferred-target constants.
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


def bbox_dimensions(shape) -> dict[str, float]:
    """Return axis-aligned bounding-box dimensions."""

    box = shape.BoundingBox()
    return {"x": float(box.xlen), "y": float(box.ylen), "z": float(box.zlen)}


def within_abs(value: float, expected: float, tolerance: float) -> bool:
    """Check absolute tolerance."""

    return abs(value - expected) <= tolerance


# ---------------------------------------------------------------------------
# TASK-SPECIFIC HELPERS (material probing around the motor / ballscrew axis)
# ---------------------------------------------------------------------------
# The ballscrew/motor axis is the global Z axis through (X=0, Y=0). Probes test
# point-in-solid so the checks are independent of how the solver modeled the
# part. The base plate (motor-mount face) spans Z in [-71.5, -61.5] (measured).

PROBE_TOL = 1e-3


def solids_of(shape) -> list:
    """Return the list of solids in a shape (or the shape itself if atomic)."""

    solids = shape.Solids()
    return solids if solids else [shape]


def material_at(solids: list, x: float, y: float, z: float) -> bool:
    """True if (x, y, z) lies inside any solid of the shape."""

    import cadquery as cq

    point = cq.Vector(x, y, z)
    return any(solid.isInside(point, PROBE_TOL) for solid in solids)


def scan_radius_to_material(solids: list, z: float, r_max: float = 30.0, samples: int = 300) -> float:
    """Scan outward from the axis along +Y at height z; return first material radius."""

    for i in range(samples):
        r = r_max * i / samples
        if material_at(solids, 0.0, r, z):
            return r
    return r_max


# ---------------------------------------------------------------------------
# TASK-SPECIFIC CHECKS
# ---------------------------------------------------------------------------

# Target spec (instruction + standards).
NEMA17_PATTERN = 31.0           # mm square pitch (NEMA 17)
PATTERN_HALF = NEMA17_PATTERN / 2.0   # 15.5 mm offset from the axis
M3_CLEARANCE_R = 1.7            # Ø3.4 mm M3 clearance (ISO 273 medium)

# Measured base-plate band; probe depths kept safely inside the 10 mm plate.
Z_MID = -66.0
Z_DEEP = -69.0                  # near the motor-mount face
Z_SHALLOW = -64.0              # near the cavity-side face

NEMA17_POSITIONS = [
    (PATTERN_HALF, PATTERN_HALF),
    (PATTERN_HALF, -PATTERN_HALF),
    (-PATTERN_HALF, PATTERN_HALF),
    (-PATTERN_HALF, -PATTERN_HALF),
]
# Existing NEMA 23 holes (~47.1 mm square) to be preserved.
NEMA23_POSITIONS = [(23.5, 23.5), (23.5, -23.5), (-23.5, 23.5), (-23.5, -23.5)]


def build_task_checks(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Return task-specific deterministic checks for the NEMA 17 retrofit."""

    input_shape = context["input_shape"]
    output_shape = context["output_shape"]
    in_solids = solids_of(input_shape)
    out_solids = solids_of(output_shape)

    # Pilot-bore wall radius, measured from the input (~19.05 mm). Used both for
    # bore preservation and for the "frame clears the bore" inference check.
    in_bore_r = scan_radius_to_material(in_solids, Z_MID)

    checks: list[dict[str, Any]] = []

    # 1. CRITICAL — the NEMA 17 pattern was actually drilled. Each of the four
    # 31 mm-square positions must be OPEN (air) through the base plate in the
    # output but was MATERIAL in the input (proves a real cut at the right place,
    # centered on the ballscrew axis). A through hole requires air at two depths.
    # Tolerance source: NEMA 17 standard pitch (31.0 mm); positions exact.
    # Hackability: unchanged input is material here (fail); a wrong-pitch or
    # off-axis pattern misses these probes (fail); a blind/partial hole fails the
    # two-depth through check.
    pattern_detail = []
    pattern_ok = True
    for (hx, hy) in NEMA17_POSITIONS:
        out_open = (
            not material_at(out_solids, hx, hy, Z_MID)
            and not material_at(out_solids, hx, hy, Z_DEEP)
            and not material_at(out_solids, hx, hy, Z_SHALLOW)
        )
        in_solid = material_at(in_solids, hx, hy, Z_MID)
        ok = out_open and in_solid
        pattern_ok = pattern_ok and ok
        pattern_detail.append(
            {"pos": [hx, hy], "output_open": out_open, "input_was_solid": in_solid}
        )
    checks.append(
        critical(
            check_result(
                "nema17_pattern_drilled",
                "Four NEMA 17 holes (31 mm square, on the ballscrew axis) drilled "
                "through the base plate.",
                pattern_ok,
                {"holes": pattern_detail},
            )
        )
    )

    # 2. CRITICAL — the new holes are M3 clearance size (~Ø3.4), not an oversized
    # cut that spoofs check 1. At each hole, probe along the outward radial
    # direction (guaranteed base-plate material): air at r=1.4 (inside Ø3.4),
    # material at r=2.2 (outside Ø3.4).
    # Tolerance source: M3 clearance ISO 273 medium (Ø3.4); bracket accepts a
    # hole radius in [1.4, 2.2] (Ø2.8-4.4). Hackability: catches a single large
    # bore, slots, or grossly wrong drill size at the pattern positions.
    diameter_detail = []
    diameter_ok = True
    for (hx, hy) in NEMA17_POSITIONS:
        norm = math.hypot(hx, hy)
        ux, uy = hx / norm, hy / norm
        inside_air = not material_at(out_solids, hx + 1.4 * ux, hy + 1.4 * uy, Z_MID)
        outside_solid = material_at(out_solids, hx + 2.2 * ux, hy + 2.2 * uy, Z_MID)
        ok = inside_air and outside_solid
        diameter_ok = diameter_ok and ok
        diameter_detail.append(
            {"pos": [hx, hy], "air_at_r1.4": inside_air, "solid_at_r2.2": outside_solid}
        )
    checks.append(
        critical(
            check_result(
                "nema17_hole_diameter",
                "New holes are M3 clearance size (~Ø3.4 mm), not oversized.",
                diameter_ok,
                {"holes": diameter_detail},
            )
        )
    )

    # 2b. CRITICAL — the chosen frame's bolt circle actually CLEARS the pilot bore
    # (the geometric crux of "smallest standard NEMA frame that fits coaxially").
    # Just inside each hole, on the line toward the axis, there must still be solid
    # base-plate web between the bore wall and the hole. A smaller frame (NEMA 14 =
    # 26 mm square, or NEMA 11) puts its bolt circle inside the Ø38.1 bore, so the
    # holes would merge into the bore and this web vanishes.
    # Tolerance source: input bore radius (~19.05 mm) + a thin web margin (0.4 mm).
    # Hackability: a mis-inferred smaller frame fails here AND at the pattern check;
    # an oversized hole that eats the web also fails.
    web_r = in_bore_r + 0.4
    web_detail = []
    web_ok = True
    for (hx, hy) in NEMA17_POSITIONS:
        norm = math.hypot(hx, hy)
        ux, uy = hx / norm, hy / norm
        web_solid = material_at(out_solids, web_r * ux, web_r * uy, Z_MID)
        web_ok = web_ok and web_solid
        web_detail.append({"pos": [hx, hy], "web_solid_at_bore_wall": web_solid})
    checks.append(
        critical(
            check_result(
                "frame_clears_pilot_bore",
                "Chosen mounting frame clears the Ø38.1 pilot bore (solid web "
                "retained between each new hole and the bore).",
                web_ok,
                {"bore_wall_radius": round(in_bore_r, 3), "web_probe_radius": round(web_r, 3),
                 "holes": web_detail},
            )
        )
    )

    # 3. SUPPORTIVE — the Ø38.1 coupling/pilot bore is preserved. The axis must
    # stay open and the bore wall radius must match the input (~19.05 mm).
    # Tolerance source: input measurement; +/-0.6 mm.
    out_bore_r = scan_radius_to_material(out_solids, Z_MID)
    axis_open = not material_at(out_solids, 0.0, 0.0, Z_MID)
    bore_ok = axis_open and within_abs(out_bore_r, in_bore_r, 0.6)
    checks.append(
        check_result(
            "pilot_bore_preserved",
            "Central Ø38.1 mm coupling/pilot bore preserved on the axis.",
            bore_ok,
            {"input_bore_radius": round(in_bore_r, 3),
             "output_bore_radius": round(out_bore_r, 3), "axis_open": axis_open},
        )
    )

    # 4. SUPPORTIVE — the existing NEMA 23 holes are kept (dual-pattern mount).
    # Each ~47.1 mm-square position that was open in the input must remain open.
    # Tolerance source: instruction (preserve NEMA 23 holes); input-derived.
    # Hackability: catches a solver that fills/erases the old pattern.
    nema23_detail = []
    nema23_ok = True
    for (hx, hy) in NEMA23_POSITIONS:
        in_open = not material_at(in_solids, hx, hy, Z_MID)
        out_open = not material_at(out_solids, hx, hy, Z_MID)
        ok = (not in_open) or out_open  # only require preservation where input was open
        nema23_ok = nema23_ok and ok
        nema23_detail.append({"pos": [hx, hy], "input_open": in_open, "output_open": out_open})
    checks.append(
        check_result(
            "nema23_holes_preserved",
            "Existing NEMA 23 mounting holes remain open (dual-pattern mount).",
            nema23_ok,
            {"holes": nema23_detail},
        )
    )

    # 5. SUPPORTIVE — the ballscrew bearing interface on the top plate is intact.
    # The bearing bore stays open at the top and the top-plate material remains.
    # Tolerance source: instruction (preserve bearing seat); input-derived points.
    bearing_bore_open = not material_at(out_solids, 0.0, 0.0, 15.0)
    top_plate_present = material_at(out_solids, 14.0, 0.0, 15.0)
    checks.append(
        check_result(
            "bearing_seat_preserved",
            "Ballscrew bearing seat / top plate preserved.",
            bearing_bore_open and top_plate_present,
            {"bearing_bore_open": bearing_bore_open, "top_plate_present": top_plate_present},
        )
    )

    # 6. SUPPORTIVE — overall envelope is unchanged (no rescale, no added stock).
    # Tolerance source: GT/input measurement; +/-0.5 mm on each axis.
    in_dims = bbox_dimensions(input_shape)
    out_dims = bbox_dimensions(output_shape)
    env_ok = all(within_abs(out_dims[a], in_dims[a], 0.5) for a in ("x", "y", "z"))
    checks.append(
        check_result(
            "envelope_preserved",
            "Overall bounding-box envelope unchanged.",
            env_ok,
            {"input": {k: round(v, 2) for k, v in in_dims.items()},
             "output": {k: round(v, 2) for k, v in out_dims.items()}},
        )
    )

    # 7. SUPPORTIVE — only a small amount of material was removed (four M3 holes),
    # guarding against a do-nothing solution and against gross over-cutting.
    # Tolerance source: GT measurement (~371 mm^3); accept [120, 1000] mm^3.
    removed = float(input_shape.Volume()) - float(output_shape.Volume())
    removed_ok = 120.0 <= removed <= 1000.0
    checks.append(
        check_result(
            "material_removed_small",
            "Removed material consistent with four M3 clearance holes.",
            removed_ok,
            {"removed_mm3": round(removed, 2), "min": 120.0, "max": 1000.0},
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
