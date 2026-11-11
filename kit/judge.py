"""Rubric judge: a (swappable) chat model scores each rubric criterion from 0 to 1, weighted by the rubric.

The judge sees the task prompt, the rubric, the submitted solution.py, the verifier's per-check results and the tail of
the solver transcript. The verifier's measurements are facts; the judge decides how they map onto the criteria and
scores the parts a verifier cannot measure (reasoning, code quality, evidence of inspection).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ChatModel
from .tasks import Task

JUDGE_SYSTEM = """You grade a CAD-editing attempt against a rubric. Be strict and literal: full credit only when the
criterion's full-credit description is met; any listed major failure means at most 0.25 for that criterion.
The verifier results are measurements of the submitted geometry; trust them over the attempt's own claims.
Answer with one JSON object only, no prose:
{"criteria": [{"index": <int>, "score": <0..1>, "reason": "<one sentence>"}, ...]}"""


def _verifier_digest(v: dict, limit: int = 60) -> str:
    rows = []
    for c in (v.get("criteria") or v.get("checks") or [])[:limit]:
        rows.append(f"- {c.get('id')}: {'PASS' if c.get('passed') else 'FAIL'} :: {c.get('description', '')[:160]} :: "
                    f"{json.dumps(c.get('details', {}), default=str)[:240]}")
    head = f"score={v.get('score')} passed={v.get('passed')} critical_failed={v.get('critical_failed')} reproducible={v.get('reproducible')}"
    return head + "\n" + "\n".join(rows)


def _transcript_tail(transcript: dict, max_chars: int = 6000) -> str:
    parts = []
    for t in transcript.get("turns", []):
        parts.append(f"[turn {t.get('turn')}] {str(t.get('reply', ''))[:1500]}")
        if "result" in t:
            r = t["result"]
            parts.append(f"  -> exit {r.get('returncode')}; stdout: {str(r.get('stdout', ''))[:600]}")
    text = "\n".join(parts)
    return text[-max_chars:] if text else "(no transcript: scripted or replayed attempt)"


def judge(model: ChatModel, task: Task, output_dir: Path, verifier: dict, transcript: dict) -> dict:
    rubric = task.rubric()
    if not rubric:
        return {"skipped": "task has no rubric.md"}
    py = output_dir / "solution.py"
    code = py.read_text(encoding="utf-8", errors="replace")[:20000] if py.exists() else "(solution.py missing)"
    user = (f"# Task prompt\n{task.prompt}\n\n# Rubric\n{task.rubric_text}\n\n# Submitted solution.py\n```python\n{code}\n```\n\n"
            f"# Verifier results\n{_verifier_digest(verifier)}\n\n# Transcript (tail)\n{_transcript_tail(transcript)}")
    raw = model.chat(JUDGE_SYSTEM, [{"role": "user", "content": user}])
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        parsed = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        parsed = {}
    by_idx = {int(c.get("index", -1)): c for c in parsed.get("criteria", []) if isinstance(c, dict)}
    total_w = sum(r["weight"] for r in rubric) or 1.0
    rows, got = [], 0.0
    for r in rubric:
        c = by_idx.get(r["index"], {})
        s = max(0.0, min(1.0, float(c.get("score", 0.0) or 0.0)))
        got += s * r["weight"]
        rows.append({"index": r["index"], "weight": r["weight"], "score": s, "reason": c.get("reason", "missing in judge output")})
    return {"judge": model.name, "rubric_score": round(got / total_w, 4), "criteria": rows, "parsed_ok": bool(by_idx)}
