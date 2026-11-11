"""Deterministic verifier: pillow-block retrofit from a 6204 to a 6205 bearing.

Representation-agnostic: it measures MATERIAL in the output solid (point-in-solid probes, radial scans and
bisection along lines) instead of counting faces or reading a feature tree, so any valid modelling approach passes.

Targets (derived in task/prompt.md; mm, shaft axis along +Y through X=0, Z=33, front face Y=0):
    seat Ø52.000 (6205 OD) to a shoulder at Y = 2.00 + 2.15 + 15.00 = 19.15
    DIN 472-52 groove Ø55.0 x 2.15 wide, from Y=2.00 to Y=4.15;  lip Ø52 from Y=0 to Y=2.00
    lead-in chamfer 1.0 x 45° (Ø54 at Y=0 to Ø52 at Y=1);  shaft passage Ø33.0 behind the shoulder
    slots 11.0 wide, 23.0 end to end, centred on X=±45, Y=15, through the 15 mm base
    envelope 120 x 30 x 68 from (-60, 0, 0); all other material as in the reference

Usage:
    python verifier/test.py [--output solution.step] [--gt gt_solution.step] [--py solution.py] [--json result.json]
Defaults follow the harness layout (/workspace/...), overridable with OUTPUT_STEP, GT_STEP, OUTPUT_PY, RESULT_JSON.
Score = weighted share of checks passed; if any critical check fails the score is capped at 0.25.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable

import cadquery as cq

DEFAULT_OUTPUT_STEP = os.environ.get("OUTPUT_STEP", "/workspace/output/solution.step")
DEFAULT_OUTPUT_PY = os.environ.get("OUTPUT_PY", "/workspace/output/solution.py")
DEFAULT_GT_STEP = os.environ.get("GT_STEP", "/workspace/grader-support/gt_solution.step")

AXIS_Z = 33.0
SEAT_D, SHOULDER_Y, PASSAGE_D = 52.0, 19.15, 33.0
GROOVE_D, GROOVE_Y0, GROOVE_Y1 = 55.0, 2.00, 4.15
CHAMFER = 1.0
SLOT_W, SLOT_LEN, SLOT_X, SLOT_Y = 11.0, 23.0, 45.0, 15.0
ENVELOPE = {"xmin": -60.0, "xmax": 60.0, "ymin": 0.0, "ymax": 30.0, "zmin": 0.0, "zmax": 68.0}
CRITICAL_CAP = 0.25


# ---------------------------------------------------------------------------------------------- geometry helpers
def load_solids(path: Path) -> list:
    wp = cq.importers.importStep(str(path))
    solids = wp.solids().vals()
    if not solids:
        solids = [s for v in wp.vals() if hasattr(v, "Solids") for s in v.Solids()]
    return solids


def inside(solids: list, x: float, y: float, z: float) -> bool:
    p = cq.Vector(x, y, z)
    return any(s.isInside(p, 1e-4) for s in solids)


def bisect(solids: list, point: Callable[[float], tuple], t0: float, t1: float, iters: int = 32) -> float | None:
    """The t in [t0, t1] where inside(point(t)) changes; None if both ends agree."""
    a = inside(solids, *point(t0))
    if a == inside(solids, *point(t1)):
        return None
    for _ in range(iters):
        tm = (t0 + t1) / 2
        if inside(solids, *point(tm)) == a:
            t0 = tm
        else:
            t1 = tm
    return (t0 + t1) / 2


def bore_radius(solids: list, y: float, r_lo: float = 8.0, r_hi: float = 34.5) -> float | None:
    """Median radius where material starts around the shaft axis at height Y, over five directions in the XZ plane."""
    found = []
    for deg in (0, 45, 90, 135, 180):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        r = bisect(solids, lambda t, c=c, s=s: (t * c, y, AXIS_Z + t * s), r_lo, r_hi)
        if r is not None:
            found.append(r)
    if not found:
        return None
    found.sort()
    return found[len(found) // 2]


def r3(v: float | None) -> float | None:
    return None if v is None else round(v, 4)


# ---------------------------------------------------------------------------------------------- checks
def check(cid: str, desc: str, passed: bool, weight: float, critical: bool = False, **details: Any) -> dict[str, Any]:
    return {"id": cid, "description": desc, "passed": bool(passed), "weight": weight, "critical": critical, "details": details}


def build_checks(out_step: Path, gt_step: Path | None, out_py: Path | None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not out_step.exists():
        return [check("C01_load", "solution.step exists and loads", False, 3, True, error=f"missing: {out_step}")]
    try:
        solids = load_solids(out_step)
    except Exception as exc:  # noqa: BLE001
        return [check("C01_load", "solution.step exists and loads", False, 3, True, error=str(exc)[:300])]
    valid = all(s.isValid() for s in solids)
    checks.append(check("C01_load", "loads as exactly one valid solid", len(solids) == 1 and valid, 3, True, solids=len(solids), valid=valid))
    if not solids:
        return checks

    shape = solids[0] if len(solids) == 1 else cq.Compound.makeCompound(solids)
    bb = shape.BoundingBox()
    got = {"xmin": bb.xmin, "xmax": bb.xmax, "ymin": bb.ymin, "ymax": bb.ymax, "zmin": bb.zmin, "zmax": bb.zmax}
    env_ok = all(abs(got[k] - v) <= 0.05 for k, v in ENVELOPE.items())
    checks.append(check("C02_envelope", "envelope 120 x 30 x 68 from (-60, 0, 0) unchanged", env_ok, 2, True, measured={k: r3(v) for k, v in got.items()}))

    seat = [bore_radius(solids, y) for y in (8.0, 12.0, 17.0)]
    seat_ok = all(r is not None and abs(2 * r - SEAT_D) <= 0.04 for r in seat)
    checks.append(check("C03_seat_diameter", "bearing seat Ø52.000 (6205 OD) along the seat", seat_ok, 3, True,
                        measured_diameters=[r3(2 * r) if r else None for r in seat], expected=SEAT_D))

    shoulder = bisect(solids, lambda t: (20.5, t, AXIS_Z), 12.0, 25.0)
    checks.append(check("C04_shoulder", "shoulder at Y = 2.00 + 2.15 + 15.00 = 19.15", shoulder is not None and abs(shoulder - SHOULDER_Y) <= 0.05, 2,
                        measured=r3(shoulder), expected=SHOULDER_Y))

    passage = bore_radius(solids, 25.0)
    checks.append(check("C05_passage", "shaft passage Ø33.0 behind the shoulder", passage is not None and abs(2 * passage - PASSAGE_D) <= 0.06, 1,
                        measured=r3(2 * passage) if passage else None, expected=PASSAGE_D))

    groove = bore_radius(solids, (GROOVE_Y0 + GROOVE_Y1) / 2)
    checks.append(check("C06_groove_diameter", "DIN 472-52 groove Ø55.0", groove is not None and abs(2 * groove - GROOVE_D) <= 0.06, 2, True,
                        measured=r3(2 * groove) if groove else None, expected=GROOVE_D))

    r_probe = (SEAT_D / 2 + GROOVE_D / 2) / 2  # between the seat and the groove bottom
    y_mid = (GROOVE_Y0 + GROOVE_Y1) / 2
    front = bisect(solids, lambda t: (r_probe, t, AXIS_Z), 1.2, y_mid)
    back = bisect(solids, lambda t: (r_probe, t, AXIS_Z), y_mid, 6.5)
    flank_ok = front is not None and back is not None and abs(front - GROOVE_Y0) <= 0.05 and abs(back - GROOVE_Y1) <= 0.05
    checks.append(check("C07_groove_position", "groove from Y=2.00 to Y=4.15 (width 2.15, inner flank flush with the bearing)", flank_ok, 2,
                        measured_front=r3(front), measured_back=r3(back), width=r3(back - front) if front and back else None))

    lip = bore_radius(solids, 1.5)
    checks.append(check("C08_lip", "Ø52 lip between the chamfer and the groove", lip is not None and abs(2 * lip - SEAT_D) <= 0.04, 1,
                        measured=r3(2 * lip) if lip else None))

    ch = [bore_radius(solids, y) for y in (0.3, 0.7)]
    want = [SEAT_D / 2 + CHAMFER - y for y in (0.3, 0.7)]
    ch_ok = all(r is not None and abs(r - w) <= 0.1 for r, w in zip(ch, want, strict=True))
    checks.append(check("C09_chamfer", "lead-in chamfer 1.0 x 45° at the seat mouth", ch_ok, 1, measured_radii=[r3(r) for r in ch], expected_radii=want))

    for side, name in ((1, "right"), (-1, "left")):
        xc = side * SLOT_X
        y_hi = bisect(solids, lambda t: (xc, t, 7.5), SLOT_Y, 29.0)
        y_lo = bisect(solids, lambda t: (xc, t, 7.5), SLOT_Y, 1.0)
        x_out = bisect(solids, lambda t: (t, SLOT_Y, 7.5), xc, side * 59.0)
        x_in = bisect(solids, lambda t: (t, SLOT_Y, 7.5), xc, side * 31.0)
        width = None if y_hi is None or y_lo is None else y_hi - y_lo
        length = None if x_out is None or x_in is None else abs(x_out - x_in)
        centre = None if x_out is None or x_in is None else (x_out + x_in) / 2
        through = all(not inside(solids, xc + dx, SLOT_Y, z) for dx in (-6.0, 0.0, 6.0) for z in (0.5, 7.5, 14.5))
        ok = (width is not None and abs(width - SLOT_W) <= 0.05 and length is not None and abs(length - SLOT_LEN) <= 0.05
              and centre is not None and abs(centre - xc) <= 0.05 and through)
        checks.append(check(f"C10_slot_{name}", f"{name} slot 11.0 x 23.0 through the base, centred on X={xc:+.0f}, Y=15", ok, 2, True,
                            width=r3(width), length=r3(length), centre_x=r3(centre), through=through))

    keep = [inside(solids, sx * 58, 2, 14.5) and inside(solids, sx * 58, 28, 0.5) and not inside(solids, sx * 58, 15, 15.5) for sx in (1, -1)]
    keep.append(inside(solids, 0, 15, 67.8) and inside(solids, 32.0, 15, 25.0) and inside(solids, -32.0, 15, 25.0))
    checks.append(check("C11_preserved", "base, pedestal and boss material preserved", all(keep), 1, probes=keep))

    if gt_step is not None and gt_step.exists():
        gt = load_solids(gt_step)
        gshape = gt[0] if len(gt) == 1 else cq.Compound.makeCompound(gt)
        v, vg = shape.Volume(), gshape.Volume()
        try:
            common = shape.intersect(gshape).Volume()
            sym = v + vg - 2 * common
        except Exception:  # noqa: BLE001
            sym = float("nan")
        ok = not math.isnan(sym) and sym / vg <= 0.002 and abs(v - vg) / vg <= 0.002
        checks.append(check("C12_reference", "no other change: ≤ 0.2 % of the volume differs from the reference", ok, 3,
                            volume=round(v, 2), reference_volume=round(vg, 2), symmetric_difference_pct=round(100 * sym / vg, 4) if not math.isnan(sym) else None))

    if out_py is not None:
        has_py = out_py.exists() and out_py.stat().st_size > 0
        checks.append(check("C13_script", "solution.py saved (reproducible)", has_py, 0.5, path=str(out_py)))
    return checks


def aggregate(checks: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(c["weight"] for c in checks) or 1.0
    score = sum(c["weight"] for c in checks if c["passed"]) / total
    critical_failed = [c["id"] for c in checks if c["critical"] and not c["passed"]]
    if critical_failed:
        score = min(score, CRITICAL_CAP)
    return {"score": round(score, 4), "passed": all(c["passed"] for c in checks) and not critical_failed,
            "critical_failed": critical_failed, "failed": [c["id"] for c in checks if not c["passed"]], "checks": checks}


def run_tests(out_step: Any = DEFAULT_OUTPUT_STEP, gt_step: str | Path | None = DEFAULT_GT_STEP,
              out_py: str | Path | None = DEFAULT_OUTPUT_PY) -> dict[str, Any]:
    """Paths form: run_tests(output_step, gt_step, output_py).
    Harness form: run_tests(context) with context["paths"] = {output_step, gt_step, output_py, ...}; the result then also
    carries the harness field names (failed_check_ids, criteria)."""
    if isinstance(out_step, dict):
        p = out_step["paths"]
        res = run_tests(p["output_step"], p.get("gt_step"), p.get("output_py"))
        res["failed_check_ids"], res["criteria"] = res["failed"], res["checks"]
        res["critical_failed"] = bool(res["critical_failed"])
        return res
    return aggregate(build_checks(Path(out_step), Path(gt_step) if gt_step else None, Path(out_py) if out_py else None))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", default=DEFAULT_OUTPUT_STEP)
    ap.add_argument("--gt", default=DEFAULT_GT_STEP)
    ap.add_argument("--py", default=DEFAULT_OUTPUT_PY)
    ap.add_argument("--json", default=os.environ.get("RESULT_JSON"))
    a = ap.parse_args()
    result = run_tests(a.output, a.gt, a.py)
    text = json.dumps(result, indent=2)
    if a.json:
        Path(a.json).write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
