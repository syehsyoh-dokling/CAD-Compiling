"""Grade one finished attempt: deterministic verifier, reproducibility re-run, optional rubric judge."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .sandbox import CAD_PYTHON, Workspace
from .tasks import KIT, Task


def run_verifier(task: Task, output_dir: Path, repro_step: Path | None = None, timeout: int = 900) -> dict:
    cmd = [CAD_PYTHON, str(KIT / "kit" / "grade_one.py"), "--verifier", str(task.verifier),
           "--input", str(task.problem_dir / "model.step"), "--output", str(output_dir / "solution.step"),
           "--py", str(output_dir / "solution.py"), "--gt", str(task.gt_step)]
    if repro_step is not None:
        cmd += ["--repro", str(repro_step)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        lines = [ln for ln in p.stdout.splitlines() if ln.startswith("{")]
        if not lines:
            return {"score": 0.0, "passed": False, "failed_check_ids": ["verifier_crash"], "error": p.stderr[-2000:]}
        return json.loads(lines[-1])
    except subprocess.TimeoutExpired:
        return {"score": 0.0, "passed": False, "failed_check_ids": ["verifier_timeout"], "error": f"timeout {timeout}s"}


def reproduce(task: Task, output_dir: Path) -> tuple[Path | None, Workspace | None]:
    """Run the submitted solution.py in a fresh workspace; return the STEP it produced (or None)."""
    py = output_dir / "solution.py"
    if not py.exists():
        return None, None
    ws = Workspace(task.problem_dir)
    ws.run_python(py.read_text(encoding="utf-8"), timeout=task.timeout_s, name="solution.py")
    step = ws.output / "solution.step"
    return (step if step.exists() else None), ws


def summarize(v: dict) -> dict:
    failed = v.get("failed_check_ids") or v.get("failed") or []
    crit = v.get("critical_failed")
    return {"score": float(v.get("score", 0.0)), "passed": bool(v.get("passed", False)),
            "critical_failed": bool(crit) if not isinstance(crit, list) else bool(crit),
            "failed": failed, "reproducible": (v.get("reproducible") or {}).get("ok"), "error": v.get("error")}
