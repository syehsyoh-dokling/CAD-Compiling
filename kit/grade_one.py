"""Run one task verifier on one output, in its own process (called by kit/grade.py with the CadQuery interpreter).

The verifier contract is the CAD_Edit one: verifier/test.py exposes run_tests(context) where
    context = {"paths": {input_step, output_step, output_py, gt_step},
               "input_shape": Shape, "output_shape": Shape, "gt_shape": Shape | None}
and returns {"score": 0..1, "passed": bool, "critical_failed": bool, "failed_check_ids": [...], "criteria": [...]}.

Usage: python kit/grade_one.py --verifier test.py --input model.step --output solution.step --py solution.py
       --gt gt_solution.step [--repro repro.step]
Prints one JSON object.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path


def load_shape(path: str):
    import cadquery as cq

    return cq.importers.importStep(path).val()


def volume(path: str) -> float:
    import cadquery as cq

    return sum(s.Volume() for s in cq.importers.importStep(path).solids().vals())


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("verifier", "input", "output", "py", "gt"):
        ap.add_argument(f"--{a}", required=True)
    ap.add_argument("--repro")
    a = ap.parse_args()
    out: dict = {}
    try:
        if not Path(a.output).exists():
            out = {"score": 0.0, "passed": False, "critical_failed": True, "failed_check_ids": ["output_missing"],
                   "criteria": [], "error": "solution.step was not written"}
        else:
            sys.path.insert(0, str(Path(a.verifier).parent))
            spec = importlib.util.spec_from_file_location("task_verifier", a.verifier)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            paths = {"input_step": a.input, "output_step": a.output, "output_py": a.py, "gt_step": a.gt}
            context = {"paths": paths, "input_shape": load_shape(a.input), "output_shape": load_shape(a.output),
                       "gt_shape": load_shape(a.gt) if Path(a.gt).exists() else None}
            out = mod.run_tests(context)
    except Exception as exc:  # noqa: BLE001
        out = {"score": 0.0, "passed": False, "critical_failed": True, "failed_check_ids": ["verifier_error"], "criteria": [],
               "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()[-3000:]}

    if a.repro:
        try:
            if not Path(a.repro).exists():
                out["reproducible"] = {"ok": False, "reason": "solution.py did not produce solution.step in a fresh workspace"}
            elif Path(a.output).exists():
                v1, v2 = volume(a.output), volume(a.repro)
                out["reproducible"] = {"ok": abs(v1 - v2) <= 1e-4 * max(v1, 1.0), "submitted_volume": round(v1, 3), "rerun_volume": round(v2, 3)}
            else:
                out["reproducible"] = {"ok": False, "reason": "no submitted solution.step to compare"}
        except Exception as exc:  # noqa: BLE001
            out["reproducible"] = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
