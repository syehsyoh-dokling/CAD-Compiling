"""A throw-away /workspace for one attempt, and a runner for Python code inside it.

Layout seen by the model (its code refers to these absolute paths):
    /workspace/files/problem/...   task inputs (copied)
    /workspace/output/             where solution.py and solution.step must go
The grader-support folder is NOT copied: the model never sees the golden answer.

On Linux inside Docker, /workspace can be the real path. Elsewhere the literal "/workspace" in the model's code is
rewritten to the temp directory before running. This is a convenience, not a security boundary: run untrusted models
inside the provided Dockerfile (or a VM).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CAD_PYTHON = os.environ.get("CAD_PYTHON", sys.executable)  # interpreter with CadQuery installed
MAX_OUTPUT = 6000


class Workspace:
    def __init__(self, problem_dir: Path, root: Path | None = None):
        self.root = Path(root or tempfile.mkdtemp(prefix="cadws_"))
        (self.root / "files").mkdir(parents=True, exist_ok=True)
        shutil.copytree(problem_dir, self.root / "files" / "problem", dirs_exist_ok=True)
        (self.root / "output").mkdir(exist_ok=True)
        (self.root / "_runs").mkdir(exist_ok=True)
        self.n_runs = 0

    @property
    def posix(self) -> str:
        return self.root.as_posix()

    @property
    def output(self) -> Path:
        return self.root / "output"

    def rewrite(self, code: str) -> str:
        return code if self.posix == "/workspace" else code.replace("/workspace", self.posix)

    def env(self) -> dict:
        return dict(os.environ, INPUT_STEP=f"{self.posix}/files/problem/model.step",
                    OUTPUT_STEP=f"{self.posix}/output/solution.step", OUTPUT_PY=f"{self.posix}/output/solution.py",
                    PYTHONIOENCODING="utf-8")

    def run_python(self, code: str, timeout: int = 300, name: str | None = None) -> dict:
        """Run code (as written by the model, /workspace paths) and return exit code and truncated output."""
        self.n_runs += 1
        script = self.root / "_runs" / (name or f"step_{self.n_runs:02d}.py")
        script.write_text(self.rewrite(code), encoding="utf-8")
        t0 = time.time()
        try:
            p = subprocess.run([CAD_PYTHON, str(script)], cwd=self.root, env=self.env(), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout)
            res = {"returncode": p.returncode, "stdout": _tail(p.stdout), "stderr": _tail(p.stderr)}
        except subprocess.TimeoutExpired:
            res = {"returncode": None, "stdout": "", "stderr": f"timeout after {timeout}s"}
        res["seconds"] = round(time.time() - t0, 2)
        return res

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def _tail(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else "...[truncated]...\n" + text[-MAX_OUTPUT:]
