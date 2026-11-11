"""Solvers turn a task + workspace into files in /workspace/output and a transcript.

    AgentSolver   a chat model in a run-code loop (the real evaluation)
    golden        runs grader-support/gt_solution.py; must score 1.0 (checks the task itself)
    noop          copies the input unchanged; must fail (checks the verifier is not trivially satisfied)
    replay        copies a recorded attempt (attempts/<name>/) to grade outputs produced elsewhere
"""
from __future__ import annotations

import re
import shutil

from .models import ChatModel
from .sandbox import Workspace
from .tasks import Task

SYSTEM = """You are a mechanical CAD engineer working in a Linux sandbox with Python 3 and CadQuery installed.

How to work:
- To run code, reply with exactly one fenced code block in Python. It is executed as a script and you receive its exit
  code, stdout and stderr in the next message. Print whatever you need to see; nothing else is shown to you.
- Inspect the input model before editing it: load it, measure it, and confirm the features the task refers to.
- Write the required output files to /workspace/output/ exactly as the task specifies. solution.py must be a complete
  script that regenerates solution.step from the input on its own.
- Check your result before finishing: reload solution.step, confirm it is one valid solid and measure the edited
  features.
- When the output files are written and checked, reply with a short summary of what you changed and why, ending with
  the word FINAL on its own line, and no code block."""

CODE_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S)


class AgentSolver:
    def __init__(self, model: ChatModel, max_turns: int = 24, step_timeout: int = 300):
        self.model, self.max_turns, self.step_timeout = model, max_turns, step_timeout

    def solve(self, task: Task, ws: Workspace, sample: int = 0) -> dict:
        files = sorted(p.name for p in task.problem_dir.iterdir())
        first = task.prompt + "\n\nFiles in /workspace/files/problem/: " + ", ".join(files)
        images = [task.problem_dir / r for r in task.renders] if task.renders else []
        messages = [{"role": "user", "content": first}]
        turns, finished, error = [], False, None
        for turn in range(self.max_turns):
            try:
                reply = self.model.chat(SYSTEM, messages, images)
            except Exception as exc:  # noqa: BLE001  (API errors end the attempt; they are recorded, not hidden)
                error = f"{type(exc).__name__}: {str(exc)[:500]}"
                break
            messages.append({"role": "assistant", "content": reply})
            blocks = CODE_RE.findall(reply)
            if not blocks:
                turns.append({"turn": turn, "reply": reply})
                finished = "FINAL" in reply
                if finished:
                    break
                messages.append({"role": "user", "content": "No code block found. Run code, or end with FINAL when the outputs are written."})
                continue
            res = ws.run_python(blocks[0], timeout=self.step_timeout)
            turns.append({"turn": turn, "reply": reply, "result": res})
            note = "" if len(blocks) == 1 else "\n(Only the first code block was run.)"
            messages.append({"role": "user", "content": f"exit code: {res['returncode']}\nstdout:\n{res['stdout']}\nstderr:\n{res['stderr']}{note}"})
        return {"solver": f"agent:{self.model.name}", "turns": turns, "finished": finished, "error": error,
                "n_turns": len(turns)}


class GoldenSolver:
    def solve(self, task: Task, ws: Workspace, sample: int = 0) -> dict:
        code = task.gt_py.read_text(encoding="utf-8")
        (ws.output / "solution.py").write_text(code, encoding="utf-8")
        res = ws.run_python(code, timeout=task.timeout_s, name="gt_solution.py")
        return {"solver": "golden", "turns": [{"turn": 0, "result": res}], "finished": res["returncode"] == 0, "error": None, "n_turns": 1}


class NoopSolver:
    def solve(self, task: Task, ws: Workspace, sample: int = 0) -> dict:
        shutil.copy2(task.problem_dir / "model.step", ws.output / "solution.step")
        code = "import shutil\nshutil.copy('/workspace/files/problem/model.step', '/workspace/output/solution.step')\n"
        (ws.output / "solution.py").write_text(code, encoding="utf-8")
        return {"solver": "noop", "turns": [], "finished": True, "error": None, "n_turns": 0}


class ReplaySolver:
    """Sample i replays the i-th recorded attempt of the task."""

    def solve(self, task: Task, ws: Workspace, sample: int = 0) -> dict:
        if not task.attempts:
            return {"solver": "replay", "turns": [], "finished": False, "error": "task has no recorded attempts", "n_turns": 0}
        name = task.attempts[sample % len(task.attempts)]
        for f in (task.dir / "attempts" / name).iterdir():
            shutil.copy2(f, ws.output / f.name)
        return {"solver": f"replay:{name}", "turns": [], "finished": True, "error": None, "n_turns": 0, "attempt": name}


SCRIPTED = {"golden": GoldenSolver, "noop": NoopSolver, "replay": ReplaySolver}
