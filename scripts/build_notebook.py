"""Build notebooks/cad_model_eval.ipynb from the cell sources below (keeps the notebook diff-able and reproducible).

Usage:  python scripts/build_notebook.py
"""
from __future__ import annotations

import json
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
OUT = KIT / "notebooks" / "cad_model_eval.ipynb"
CELLS: list[tuple[str, str]] = []


def md(text: str) -> None:
    CELLS.append(("markdown", text.strip("\n")))


def code(text: str) -> None:
    CELLS.append(("code", text.strip("\n")))


md("""
# CAD model evaluation and training

This notebook drives the kit in this repo. The model under test is the only thing that changes (`models.json`).

1. **Setup.** Load the tasks.
2. **Self-checks.** Every task's golden answer must pass its verifier; the unchanged input must fail.
3. **Verifier calibration (T004).** 17 deliberately wrong variants; each must fail on the check meant to catch it.
4. **Replay.** Grade recorded attempts (T001–T003) exactly as a live model would be graded.
5. **Evaluate a model.** An agent loop: the model runs Python/CadQuery in a sandboxed `/workspace`, writes
   `solution.py` and `solution.step`, and is graded by the verifier (and optionally a rubric judge). Reports pass@k.
6. **Task family (T004).** Parametric variants with their own golden answers, for training data.
7. **Training (optional, GPU).** LoRA SFT on golden scripts, then verifier-filtered rejection sampling.
""")

md("## 1. Setup")
code("""
# Python 3.10-3.12 with CadQuery. On a fresh machine:  conda env create -f environment.yml  (or pip install -r requirements.txt)
import json, os, subprocess, sys, importlib.util
from pathlib import Path
import pandas as pd

KIT = Path.cwd() if (Path.cwd() / "kit").exists() else Path.cwd().parent
sys.path.insert(0, str(KIT))
os.environ.setdefault("CAD_PYTHON", sys.executable)   # interpreter used to run model code and verifiers

from kit.tasks import list_tasks
TASKS = {t.id: t for t in list_tasks()}
pd.DataFrame([{"id": t.id, "title": t.title, "renders": len(t.renders), "recorded attempts": len(t.attempts),
               "rubric criteria": len(t.rubric())} for t in TASKS.values()])
""")
code("""
def run_eval(*args: str) -> pd.DataFrame:
    \"\"\"Run the CLI (same code path as the command line) and return its per-attempt rows.\"\"\"
    before = set((KIT / "results").glob("*")) if (KIT / "results").exists() else set()
    subprocess.run([sys.executable, str(KIT / "run_eval.py"), *args], cwd=KIT, check=True)
    run_dir = max(set((KIT / "results").glob("*")) - before, key=lambda p: p.stat().st_mtime)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return pd.DataFrame(summary["rows"])
""")

md("## 2. Self-checks: golden must pass, unchanged input must fail")
code("""
golden = run_eval("--model", "golden")
golden[["task", "verifier_score", "passed", "reproducible", "failed"]]
""")
code("""
noop = run_eval("--model", "noop", "--no-repro")
noop[["task", "verifier_score", "passed", "failed"]]
""")
code("""
assert golden["passed"].all(), "a golden answer fails its own verifier: fix the task before evaluating models"
assert not noop["passed"].any(), "an unchanged input passes: the verifier is too loose"
""")

md("""
## 3. Verifier calibration on T004

Each variant is a plausible mistake and names the check that must catch it.
""")
code("""
T4 = TASKS["T004"]
spec = importlib.util.spec_from_file_location("t4_mutations", T4.dir / "authoring" / "mutations.py")
mut = importlib.util.module_from_spec(spec); spec.loader.exec_module(mut)
report = mut.calibrate()
pd.DataFrame(report["rows"])[["variant", "score", "passed", "expected", "failed", "ok"]]
""")
code("""
assert report["all_ok"], "verifier calibration failed"
""")

md("## 4. Replay recorded attempts (T001–T003)")
code("""
replay = run_eval("--model", "replay", "--tasks", "T001,T002,T003", "--k", "4")
replay[["task", "sample", "solver", "verifier_score", "passed", "reproducible", "failed"]]
""")

md("""
## 5. Evaluate a model

Pick a key from `models.json` and set its API key in the environment (`ANTHROPIC_API_KEY`, `NVIDIA_API_KEY`, ...).
Each attempt is a multi-turn agent run, so it costs real tokens: start with one task and `K = 1`.
""")
code("""
MODEL = "claude-opus"      # any key in models.json
JUDGE = "none"             # or a key in models.json to also score the rubric
TASK_IDS = "T004"
K = 1
RUN = False                # set True to spend tokens

if RUN:
    live = run_eval("--model", MODEL, "--tasks", TASK_IDS, "--k", str(K), "--judge", JUDGE)
    display(live[["task", "sample", "verifier_score", "passed", "reproducible", "rubric_score", "turns", "failed"]])
    print(live.groupby("task").agg(pass_at_1=("passed", "mean"), pass_at_k=("passed", "max"), mean_score=("verifier_score", "mean")))
""")

md("""
## 6. A parametric task family (T004)

The family keeps the T004 input part and varies the target bearing and feature sizes. Every variant has a golden
answer built by the same `retrofit()` code, a prompt from a template, and a family score (single valid solid plus the
symmetric volume difference against the variant's golden answer).
""")
code("""
import random, tempfile
import cadquery as cq
from kit.sandbox import Workspace
from kit.solvers import SYSTEM, CODE_RE

spec = importlib.util.spec_from_file_location("gt_solution", T4.gt_py)
gt = importlib.util.module_from_spec(spec); spec.loader.exec_module(gt)
GT_SOURCE = T4.gt_py.read_text(encoding="utf-8")
BASE = cq.importers.importStep(str(T4.problem_dir / "model.step")).val()
PARAMS = ("seat_d", "shoulder_y", "passage_d", "groove_d", "groove_y0", "groove_w", "chamfer", "slot_w", "slot_pitch")

# bearing -> (OD, width, bore d, DIN 472 groove d2, groove width m). The boss is Ø70, so 6206 is the largest that fits.
BEARINGS = {"6205": (52.0, 15.0, 25.0, 55.0, 2.15), "6206": (62.0, 16.0, 30.0, 65.0, 2.15)}

def sample_variant(rng):
    b = rng.choice(list(BEARINGS)); od, w, d, g, m = BEARINGS[b]
    lip = rng.choice([1.5, 2.0, 2.5, 3.0])
    return {"bearing": b, "seat_d": od, "groove_d": g, "groove_w": m, "groove_y0": lip, "shoulder_y": round(lip + m + w, 2),
            "passage_d": d + rng.choice([6.0, 8.0]), "chamfer": rng.choice([0.5, 1.0, 1.5]), "slot_w": 11.0,
            "slot_pitch": rng.choice([8.0, 10.0, 12.0, 16.0])}

def render_prompt(v):
    return (f"The file /workspace/files/problem/model.step is a pillow-block housing for a 6204 bearing (shaft axis along +Y "
            f"through X=0, Z=33; front face Y=0, back face Y=30; Ø11 mounting holes at X=±45, Y=15). Retrofit it for a "
            f"{v['bearing']} bearing: cylindrical seat at the bearing's nominal OD, a DIN 472 internal groove starting "
            f"{v['groove_y0']:.2f} mm behind the front face with its inner flank flush with the bearing, the shoulder placed "
            f"so the bearing fits exactly behind the groove, a Ø{v['passage_d']:.1f} shaft passage behind the shoulder, a "
            f"{v['chamfer']:.1f} x 45° lead-in chamfer at the seat mouth, and each mounting hole replaced by an "
            f"{v['slot_w']:.1f} wide slot along X with arc centres {v['slot_pitch']:.1f} mm apart. Keep everything else. "
            f"Write /workspace/output/solution.py and /workspace/output/solution.step.")

def golden_script(v):
    args = ", ".join(f"{k}={v[k]!r}" for k in PARAMS)
    return (GT_SOURCE.split("def main")[0] + "\\n\\ndef main() -> None:\\n"
            "    part = cq.importers.importStep(INPUT_STEP).val()\\n"
            f"    result = retrofit(part, {args})\\n"
            "    cq.exporters.export(cq.Workplane().add(result), OUTPUT_STEP)\\n\\n\\nmain()\\n")

def family_score(step_path, v, tol_pct=0.2):
    try:
        solids = cq.importers.importStep(str(step_path)).solids().vals()
    except Exception:
        return 0.0
    if len(solids) != 1 or not solids[0].isValid():
        return 0.0
    ref = gt.retrofit(BASE, **{k: v[k] for k in PARAMS}); s = solids[0]
    pct = 100 * (s.Volume() + ref.Volume() - 2 * s.intersect(ref).Volume()) / ref.Volume()
    return 1.0 if pct <= tol_pct else max(0.0, 1 - pct / 10)

def run_family_candidate(script, v):
    ws = Workspace(T4.problem_dir)
    try:
        ws.run_python(script, timeout=300)
        out = ws.output / "solution.step"
        return family_score(out, v) if out.exists() else 0.0
    finally:
        ws.cleanup()

family = [sample_variant(random.Random(i)) for i in range(8)]
pd.DataFrame(family)
""")
code("""
# Each variant's own golden script must score 1.0 under the family score.
[run_family_candidate(golden_script(v), v) for v in family[:3]]
""")

md("""
## 7. Training (optional, needs a GPU)

1. **SFT.** LoRA on (prompt → golden script) pairs from the family.
2. **Rejection sampling.** Sample k scripts per prompt, run each in the sandbox, keep only those that score 1.0, add
   them to the training set and fine-tune again. The verifier is the only judge.

Held-out test: the real T004 prompt graded by the full verifier; it never appears in training.
""")
code("""
TRAIN = False          # set True on a GPU machine (24 GB is enough for a 7B model with LoRA in bf16)
BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
N_TRAIN = 200

def extract_code(text):
    m = CODE_RE.findall(text)
    return m[-1] if m else None

def to_chat(prompt, script):
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt},
            {"role": "assistant", "content": f"```python\\n{script}```\\nFINAL"}]

train_rng = random.Random(100)
sft_rows = []
for _ in range(N_TRAIN):
    v = sample_variant(train_rng)
    sft_rows.append({"messages": to_chat(render_prompt(v), golden_script(v)), "variant": v})
len(sft_rows)
""")
code("""
if TRAIN:
    # %pip install -q transformers peft datasets accelerate
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling, Trainer, TrainingArguments

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16, device_map="auto")
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))

    def tokenize(row):
        return tok(tok.apply_chat_template(row["messages"], tokenize=False), truncation=True, max_length=4096)

    def sft(rows, out_dir):
        ds = Dataset.from_list([{"messages": r["messages"]} for r in rows]).map(tokenize, remove_columns=["messages"])
        args = TrainingArguments(output_dir=str(out_dir), per_device_train_batch_size=1, gradient_accumulation_steps=8,
                                 num_train_epochs=2, learning_rate=1e-4, bf16=True, logging_steps=10, save_strategy="no", report_to=[])
        Trainer(model=model, args=args, train_dataset=ds, data_collator=DataCollatorForLanguageModeling(tok, mlm=False)).train()

    sft(sft_rows, KIT / "runs" / "sft_round0")
""")
code("""
def generate(prompt, n=4, temperature=0.7):
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(model.device)
    out = model.generate(ids, do_sample=True, temperature=temperature, max_new_tokens=2048, num_return_sequences=n)
    return [tok.decode(o[ids.shape[1]:], skip_special_tokens=True) for o in out]

if TRAIN:
    rs_rng, accepted, tried = random.Random(200), [], 0
    for _ in range(50):
        v = sample_variant(rs_rng)
        for text in generate(render_prompt(v)):
            tried += 1
            script = extract_code(text)
            if script and run_family_candidate(script, v) == 1.0:
                accepted.append({"messages": to_chat(render_prompt(v), script), "variant": v})
    print(f"accepted {len(accepted)} / {tried}")
    sft(sft_rows + accepted, KIT / "runs" / "sft_round1")
""")
code("""
if TRAIN:
    # Held-out test: the real T004 prompt, graded by the full verifier (single-shot script, no agent loop).
    from kit.grade import run_verifier
    scores = []
    for text in generate(T4.prompt, n=8):
        ws = Workspace(T4.problem_dir)
        ws.run_python(extract_code(text) or "", timeout=300)
        scores.append(run_verifier(T4, ws.output)["score"]); ws.cleanup()
    print("held-out T004: pass@1 =", sum(s == 1.0 for s in scores) / len(scores), "scores =", scores)
""")

md("""
## Notes

- The verifier is the source of truth for evaluation and training. Re-run sections 2 and 3 after changing a task.
- The family score is looser than the full verifier (volume difference only); it filters training data, and the full
  verifier grades the held-out test.
- Model code runs on this machine. For untrusted models, run the kit inside a container or VM.
""")


def main() -> None:
    nb = {"cells": [{"cell_type": t, "metadata": {}, "source": s.splitlines(keepends=True),
                     **({"outputs": [], "execution_count": None} if t == "code" else {})} for t, s in CELLS],
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python", "version": "3.11"}},
          "nbformat": 4, "nbformat_minor": 5}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"notebook written: {OUT}  ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
