"""Evaluate one model on the CAD tasks. The model is the only thing you swap (models.json).

Examples:
    python run_eval.py --model golden                       # every task's golden answer must pass (task self-check)
    python run_eval.py --model noop                         # unchanged input must fail everywhere (verifier self-check)
    python run_eval.py --model replay --k 4                 # grade recorded attempts in tasks/*/attempts/
    python run_eval.py --model claude-opus --tasks T001 --k 3 --judge claude-opus

Results go to results/<timestamp>_<model>/: per attempt transcript.json, output/, verifier.json, judge.json;
plus summary.json and summary.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from kit.grade import reproduce, run_verifier, summarize
from kit.judge import judge
from kit.models import make_chat_model
from kit.sandbox import Workspace
from kit.solvers import SCRIPTED, AgentSolver
from kit.tasks import KIT, list_tasks


def load_models() -> dict:
    return json.loads((KIT / "models.json").read_text(encoding="utf-8"))


def make_solver(name: str, cfg: dict, max_turns: int):
    if name in SCRIPTED:
        return SCRIPTED[name]()
    if name not in cfg:
        sys.exit(f"model {name!r} not in models.json (have: {', '.join(sorted(cfg))}; scripted: {', '.join(SCRIPTED)})")
    return AgentSolver(make_chat_model(cfg[name]), max_turns=max_turns)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, help="a key in models.json, or golden / noop / replay")
    ap.add_argument("--tasks", default="all", help="comma-separated task ids (T001,T002) or 'all'")
    ap.add_argument("--k", type=int, default=1, help="attempts per task (pass@k)")
    ap.add_argument("--max-turns", type=int, default=24)
    ap.add_argument("--judge", default="none", help="a key in models.json for the rubric judge, or 'none'")
    ap.add_argument("--no-repro", action="store_true", help="skip re-running solution.py in a fresh workspace")
    ap.add_argument("--out", default=str(KIT / "results"))
    a = ap.parse_args()

    cfg = load_models()
    solver = make_solver(a.model, cfg, a.max_turns)
    judge_model = None if a.judge == "none" else make_chat_model(cfg[a.judge])
    tasks = list_tasks(a.tasks)
    if not tasks:
        sys.exit(f"no tasks match {a.tasks!r}")
    run_dir = Path(a.out) / f"{time.strftime('%Y%m%d_%H%M%S')}_{a.model}"
    run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for task in tasks:
        k = len(task.attempts) if a.model == "replay" and a.k <= 0 else a.k
        for i in range(k):
            t0 = time.time()
            att_dir = run_dir / task.id / f"s{i}"
            ws = Workspace(task.problem_dir)
            transcript = solver.solve(task, ws, sample=i)
            shutil.copytree(ws.output, att_dir / "output", dirs_exist_ok=True)
            ws.cleanup()
            repro_step, rws = (None, None) if a.no_repro else reproduce(task, att_dir / "output")
            v = run_verifier(task, att_dir / "output", repro_step if not a.no_repro else None)
            if rws:
                rws.cleanup()
            s = summarize(v)
            j = judge(judge_model, task, att_dir / "output", v, transcript) if judge_model else None
            (att_dir / "transcript.json").write_text(json.dumps(transcript, indent=1, default=str), encoding="utf-8")
            (att_dir / "verifier.json").write_text(json.dumps(v, indent=1, default=str), encoding="utf-8")
            if j is not None:
                (att_dir / "judge.json").write_text(json.dumps(j, indent=1), encoding="utf-8")
            row = {"task": task.id, "title": task.title, "sample": i, "solver": transcript.get("solver"),
                   "verifier_score": s["score"], "passed": s["passed"], "critical_failed": s["critical_failed"],
                   "reproducible": s["reproducible"], "failed": s["failed"][:12], "error": s["error"] or transcript.get("error"),
                   "rubric_score": (j or {}).get("rubric_score"), "turns": transcript.get("n_turns"), "seconds": round(time.time() - t0, 1)}
            rows.append(row)
            print(f"{task.id} s{i} {row['solver']:<22} verifier={row['verifier_score']:<6} passed={row['passed']!s:<5} "
                  f"repro={row['reproducible']!s:<5} rubric={row['rubric_score']} failed={row['failed'][:6]}", flush=True)

    summary = build_summary(a.model, rows)
    (run_dir / "summary.json").write_text(json.dumps({"model": a.model, "judge": a.judge, "rows": rows, "per_task": summary}, indent=1), encoding="utf-8")
    (run_dir / "summary.md").write_text(render_md(a.model, a.judge, rows, summary), encoding="utf-8")
    print(f"\nresults: {run_dir}")
    for t, s in summary.items():
        print(f"  {t}: pass@1={s['pass@1']:.2f} pass@{s['k']}={s['pass@k']:.0f} mean_verifier={s['mean_verifier']:.3f}"
              + (f" mean_rubric={s['mean_rubric']:.3f}" if s["mean_rubric"] is not None else ""))
    return 0


def build_summary(model: str, rows: list[dict]) -> dict:
    out: dict = {}
    for task in dict.fromkeys(r["task"] for r in rows):
        rs = [r for r in rows if r["task"] == task]
        rub = [r["rubric_score"] for r in rs if r["rubric_score"] is not None]
        out[task] = {"k": len(rs), "pass@1": sum(r["passed"] for r in rs) / len(rs), "pass@k": float(any(r["passed"] for r in rs)),
                     "mean_verifier": sum(r["verifier_score"] for r in rs) / len(rs),
                     "mean_rubric": (sum(rub) / len(rub)) if rub else None}
    return out


def render_md(model: str, judge_name: str, rows: list[dict], summary: dict) -> str:
    lines = [f"# CAD eval: {model}", "", f"Judge: {judge_name}", "", "| Task | k | pass@1 | pass@k | mean verifier | mean rubric |",
             "|---|---|---|---|---|---|"]
    for t, s in summary.items():
        mr = "" if s["mean_rubric"] is None else f"{s['mean_rubric']:.3f}"
        lines.append(f"| {t} | {s['k']} | {s['pass@1']:.2f} | {s['pass@k']:.0f} | {s['mean_verifier']:.3f} | {mr} |")
    lines += ["", "| Task | sample | solver | verifier | passed | reproducible | rubric | failed checks |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task']} | {r['sample']} | {r['solver']} | {r['verifier_score']} | {r['passed']} | {r['reproducible']} | "
                     f"{'' if r['rubric_score'] is None else r['rubric_score']} | {', '.join(map(str, r['failed'][:6]))} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
