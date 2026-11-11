"""Task discovery and the task folder contract.

tasks/<ID>_<slug>/
    task.json                 id, title, timeout_s, renders, attempts
    prompt.md                 what the model sees
    rubric.md                 numbered criteria, each ending with "Weight: N" (for the rubric judge)
    files/problem/            model.step and render_*.png (copied into the model's /workspace)
    grader-support/           gt_solution.py, gt_solution.step (never shown to the model)
    verifier/test.py          deterministic verifier exposing run_tests(context)
    attempts/<name>/          optional recorded outputs (solution.py, solution.step) for replay
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
TASKS_DIR = KIT / "tasks"


@dataclass
class Task:
    dir: Path
    id: str
    title: str
    timeout_s: int = 600
    renders: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)

    @property
    def prompt(self) -> str:
        return (self.dir / "prompt.md").read_text(encoding="utf-8")

    @property
    def rubric_text(self) -> str:
        p = self.dir / "rubric.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @property
    def problem_dir(self) -> Path:
        return self.dir / "files" / "problem"

    @property
    def gt_step(self) -> Path:
        return self.dir / "grader-support" / "gt_solution.step"

    @property
    def gt_py(self) -> Path:
        return self.dir / "grader-support" / "gt_solution.py"

    @property
    def verifier(self) -> Path:
        return self.dir / "verifier" / "test.py"

    def rubric(self) -> list[dict]:
        """Parse rubric.md into [{index, text, weight}]."""
        items, cur = [], None
        for line in self.rubric_text.splitlines():
            m = re.match(r"^\s*(\d+)\.\s+(.*)", line)
            if m:
                cur = {"index": int(m.group(1)), "text": m.group(2).strip(), "weight": 0.0}
                items.append(cur)
                continue
            w = re.match(r"^\s*Weight:\s*([\d.]+)", line)
            if w and cur is not None:
                cur["weight"] = float(w.group(1))
            elif cur is not None and line.strip():
                cur["text"] += " " + line.strip()
        return items


def load_task(path: Path) -> Task:
    meta = json.loads((path / "task.json").read_text(encoding="utf-8"))
    return Task(dir=path, id=meta["id"], title=meta.get("title", path.name), timeout_s=int(meta.get("timeout_s", 600)),
                renders=meta.get("renders", []), attempts=meta.get("attempts", []))


def list_tasks(selector: str = "all") -> list[Task]:
    tasks = [load_task(p) for p in sorted(TASKS_DIR.iterdir()) if (p / "task.json").exists()]
    if selector in ("", "all"):
        return tasks
    wanted = {s.strip() for s in selector.split(",")}
    return [t for t in tasks if t.id in wanted or t.dir.name in wanted]
