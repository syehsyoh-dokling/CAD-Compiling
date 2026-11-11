"""Verifier calibration: the golden answer must score 1.0 and every deliberately wrong answer must fail.

Each mutation is a plausible mistake (forgot a feature, used the 6204/6206 numbers, misplaced the groove, ...) and names
the check that must catch it. A verifier that lets any of these pass is too loose; one that fails the golden is too
strict.

Usage:  python authoring/mutations.py [--json calibration.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

import cadquery as cq

ROOT = Path(__file__).resolve().parents[1]
INPUT_STEP = ROOT / "files" / "problem" / "model.step"
GT_STEP = ROOT / "grader-support" / "gt_solution.step"
sys.path.insert(0, str(ROOT / "verifier"))
from test import run_tests  # noqa: E402


def _load_gt():
    spec = importlib.util.spec_from_file_location("gt_solution", ROOT / "grader-support" / "gt_solution.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


gt = _load_gt()


def _extra_hole(p: cq.Shape) -> cq.Shape:
    """Golden part plus an unrequested Ø6 oil hole drilled down through the top of the boss."""
    return gt.retrofit(p).cut(cq.Solid.makeCylinder(3.0, 15.0, cq.Vector(0, 25.0, 55.0), cq.Vector(0, 0, 1)))


def _wider_base(p: cq.Shape) -> cq.Shape:
    return gt.retrofit(p.fuse(cq.Solid.makeBox(5, 30, 15, cq.Vector(60, 0, 0))).clean())


def _two_solids(p: cq.Shape) -> cq.Shape:
    return cq.Compound.makeCompound([gt.retrofit(p), cq.Solid.makeBox(5, 5, 5, cq.Vector(100, 0, 0))])


# name -> (builder from the input shape, the check id(s) that must fail)
MUTATIONS: dict[str, tuple[Callable[[cq.Shape], cq.Shape], tuple[str, ...]]] = {
    "unchanged_input": (lambda p: p, ("C03_seat_diameter",)),
    "seat_for_6206_od62": (lambda p: gt.retrofit(p, seat_d=62.0, groove_d=65.0), ("C03_seat_diameter",)),
    "seat_slightly_large_52p2": (lambda p: gt.retrofit(p, seat_d=52.2), ("C03_seat_diameter",)),
    "shoulder_ignores_groove_17p0": (lambda p: gt.retrofit(p, shoulder_y=17.0), ("C04_shoulder",)),
    "shoulder_kept_at_14": (lambda p: gt.retrofit(p, shoulder_y=14.0), ("C04_shoulder",)),
    "passage_kept_30": (lambda p: gt.retrofit(p, passage_d=30.0), ("C05_passage",)),
    "no_groove": (lambda p: gt.retrofit(p, groove_d=None), ("C06_groove_diameter",)),
    "groove_wrong_dia_54p0": (lambda p: gt.retrofit(p, groove_d=54.0), ("C06_groove_diameter",)),
    "groove_wrong_start_3p0": (lambda p: gt.retrofit(p, groove_y0=3.0), ("C07_groove_position",)),
    "groove_wrong_width_1p75": (lambda p: gt.retrofit(p, groove_w=1.75), ("C07_groove_position",)),
    "no_chamfer": (lambda p: gt.retrofit(p, chamfer=0.0), ("C09_chamfer",)),
    "round_holes_kept": (lambda p: gt.retrofit(p, slot_pitch=0.0), ("C10_slot_right", "C10_slot_left")),
    "slot_too_short_pitch10": (lambda p: gt.retrofit(p, slot_pitch=10.0), ("C10_slot_right",)),
    "slot_too_wide_12": (lambda p: gt.retrofit(p, slot_w=12.0), ("C10_slot_right",)),
    "extra_oil_hole": (_extra_hole, ("C12_reference",)),
    "base_widened": (_wider_base, ("C02_envelope",)),
    "two_solids": (_two_solids, ("C01_load",)),
}


def export(shape: cq.Shape, path: Path) -> None:
    cq.exporters.export(cq.Workplane().add(shape), str(path))


def calibrate() -> dict:
    base = cq.importers.importStep(str(INPUT_STEP)).val()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        golden = run_tests(GT_STEP, GT_STEP, None)
        rows.append({"variant": "golden", "score": golden["score"], "passed": golden["passed"], "failed": golden["failed"],
                     "expected": "pass", "ok": golden["passed"] and golden["score"] == 1.0})
        for name, (build, must_fail) in MUTATIONS.items():
            path = Path(tmp) / f"{name}.step"
            try:
                export(build(base), path)
                res = run_tests(path, GT_STEP, None)
            except Exception as exc:  # noqa: BLE001
                rows.append({"variant": name, "error": str(exc)[:200], "ok": False})
                continue
            caught = all(c in res["failed"] for c in must_fail)
            rows.append({"variant": name, "score": res["score"], "passed": res["passed"], "failed": res["failed"],
                         "expected": f"fail {', '.join(must_fail)}", "ok": (not res["passed"]) and caught})
    return {"all_ok": all(r["ok"] for r in rows), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    report = calibrate()
    for r in report["rows"]:
        mark = "OK " if r["ok"] else "BAD"
        print(f"{mark} {r['variant']:<30} score={r.get('score')!s:<7} failed={r.get('failed', r.get('error'))}")
    print("ALL OK" if report["all_ok"] else "CALIBRATION FAILED")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
