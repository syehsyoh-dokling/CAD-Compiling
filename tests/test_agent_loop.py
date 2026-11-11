"""No-cost test of the agent loop: a scripted ChatModel plays the model's side of the conversation.

Turn 1 inspects the input, turn 2 writes and runs the golden script, turn 3 ends with FINAL. The attempt must then pass
the task verifier. This exercises the same path a live model uses (prompt, code extraction, sandbox, grading).

Usage:  python tests/test_agent_loop.py [TASK_ID]     (default T004)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kit.grade import run_verifier, summarize  # noqa: E402
from kit.models import ChatModel  # noqa: E402
from kit.sandbox import Workspace  # noqa: E402
from kit.solvers import AgentSolver  # noqa: E402
from kit.tasks import list_tasks  # noqa: E402

INSPECT = """```python
import cadquery as cq
s = cq.importers.importStep('/workspace/files/problem/model.step')
bb = s.val().BoundingBox()
print('solids', len(s.solids().vals()), 'bbox', round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2))
```"""


class ScriptedModel(ChatModel):
    name = "scripted"

    def __init__(self, golden_code: str):
        self.replies = [INSPECT, f"Writing the edit.\n```python\n{golden_code}\n```", "Outputs written and checked.\nFINAL"]
        self.seen: list[str] = []

    def chat(self, system, messages, images=None):
        self.seen.append(messages[-1]["content"])
        return self.replies[min(len(self.seen) - 1, len(self.replies) - 1)]


def main() -> int:
    task = list_tasks(sys.argv[1] if len(sys.argv) > 1 else "T004")[0]
    gt = task.gt_py.read_text(encoding="utf-8")
    # save solution.py like a model would (the literal /workspace path is mapped to the sandbox)
    gt += "\nfrom pathlib import Path\nPath('/workspace/output/solution.py').write_text(Path(__file__).read_text())\n"
    model = ScriptedModel(gt)
    ws = Workspace(task.problem_dir)
    transcript = AgentSolver(model, max_turns=5).solve(task, ws)
    result = summarize(run_verifier(task, ws.output))
    ws.cleanup()
    ok = transcript["finished"] and transcript["n_turns"] == 3 and result["passed"] and "solids 1" in model.seen[1]
    print({"finished": transcript["finished"], "turns": transcript["n_turns"], "inspect_output": model.seen[1][:120], **result})
    print("AGENT LOOP OK" if ok else "AGENT LOOP FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
