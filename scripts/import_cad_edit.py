"""Import tasks from a CAD_Edit reviewer folder into this kit's task layout.

For each source folder it copies:
    documentation/01_prompt_original.md   -> prompt.md   (export header removed; the solution.step output line restored)
    documentation/02_rubric_original_raw.md -> rubric.md (export header removed)
    model.step, render_*.png              -> files/problem/
    gt_solution.py, gt_solution.step      -> grader-support/
    test.py                               -> verifier/test.py
    _attempts/*/solution.py|.step         -> attempts/<name>/   (byte-identical duplicates skipped)

Usage:
    python scripts/import_cad_edit.py "C:/CAD_Edit_Work/CAD_Edit/Reviewer" T001="Task#001*" T002="Task#002*" T003="Task#003*"
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
STEP_LINE = "- `/workspace/output/solution.step` — the edited model (STEP)"


def clean_doc(text: str) -> str:
    """Drop the '# ... Original' title and 'Source: restored from ...' line added by the export tool."""
    lines = text.lstrip("\ufeff").splitlines()
    while lines and (lines[0].startswith("# Prompt Original") or lines[0].startswith("# Rubric Original")
                     or lines[0].startswith("Source: restored") or not lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines).strip() + "\n"


def fix_prompt(text: str) -> str:
    """The export lost the solution.step line from the outputs list; put it back after solution.py."""
    if "/workspace/output/solution.step" in text:
        return text
    return re.sub(r"(- `/workspace/output/solution\.py`[^\n]*\n)", lambda m: m.group(1) + STEP_LINE + "\n", text, count=1)


def drop_missing_files(text: str, problem_dir: Path) -> str:
    """Remove input-list lines for files that are not in the package (e.g. a render that was never exported)."""
    out = []
    for line in text.splitlines():
        m = re.search(r"/workspace/files/problem/([\w.\-]+)", line)
        if m and not (problem_dir / m.group(1)).exists():
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def slug(name: str, limit: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return s if len(s) <= limit else s[:limit].rsplit("_", 1)[0]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_task(src: Path, task_id: str) -> dict:
    for old in (KIT / "tasks").glob(f"{task_id}_*"):
        shutil.rmtree(old)
    dst = KIT / "tasks" / f"{task_id}_{slug(src.name.split('_', 1)[-1])}"
    (dst / "files" / "problem").mkdir(parents=True)
    (dst / "grader-support").mkdir()
    (dst / "verifier").mkdir()
    doc = src / "documentation"
    shutil.copy2(src / "model.step", dst / "files" / "problem" / "model.step")
    for png in sorted(src.glob("render_*.png")):
        if "(" not in png.name:  # skip browser duplicates like "render_front (1).png"
            shutil.copy2(png, dst / "files" / "problem" / png.name)
    prompt = fix_prompt(clean_doc((doc / "01_prompt_original.md").read_text(encoding="utf-8")))
    (dst / "prompt.md").write_text(drop_missing_files(prompt, dst / "files" / "problem"), encoding="utf-8")
    (dst / "rubric.md").write_text(clean_doc((doc / "02_rubric_original_raw.md").read_text(encoding="utf-8")), encoding="utf-8")
    for name in ("gt_solution.py", "gt_solution.step"):
        shutil.copy2(src / name, dst / "grader-support" / name)
    shutil.copy2(src / "test.py", dst / "verifier" / "test.py")

    seen: set[str] = set()
    attempts = []
    for folder in sorted(p for p in (src / "_attempts").iterdir() if p.is_dir()) if (src / "_attempts").exists() else []:
        py, step = folder / "solution.py", folder / "solution.step"
        if not py.exists():
            continue
        key = sha(py) + (sha(step) if step.exists() else "")
        if key in seen:
            continue
        seen.add(key)
        name = "a" + re.sub(r"\D", "", folder.name)
        out = dst / "attempts" / name
        out.mkdir(parents=True)
        shutil.copy2(py, out / "solution.py")
        if step.exists():
            shutil.copy2(step, out / "solution.step")
        attempts.append(name)

    meta = {"id": task_id, "title": src.name.split("_", 1)[-1], "source": src.name, "timeout_s": 600,
            "renders": sorted(p.name for p in (dst / "files" / "problem").glob("*.png")), "attempts": attempts}
    (dst / "task.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"task": dst.name, **meta}


def main() -> int:
    root = Path(sys.argv[1])
    for arg in sys.argv[2:]:
        task_id, pattern = arg.split("=", 1)
        matches = sorted(root.glob(pattern))
        if len(matches) != 1:
            print(f"{task_id}: expected one match for {pattern!r}, got {len(matches)}")
            return 1
        print(json.dumps(import_task(matches[0], task_id)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
