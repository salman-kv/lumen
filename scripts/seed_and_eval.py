"""Seed the two demo organizations and run the evaluation questions against a running server.

  uv run python scripts/seed_and_eval.py                 # seed + evaluate
  uv run python scripts/seed_and_eval.py --seed-only
  uv run python scripts/seed_and_eval.py --eval-only [--base http://localhost:8000]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "sample_data"
spec = json.loads((DATA / "test_questions.json").read_text(encoding="utf-8"))


def seed(c: httpx.Client) -> dict:
    tokens = {}
    for key, o in spec["organizations"].items():
        r = c.post("/api/auth/login", json={"email": o["email"], "password": o["password"]})
        if r.status_code != 200:
            r = c.post("/api/auth/register", json={"org_name": o["name"], "email": o["email"], "password": o["password"]})
            r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        existing = {d["filename"] for d in c.get("/api/kb/documents", headers=h).json()["documents"]}
        for pdf in sorted((DATA / key).glob("*.pdf")):
            if pdf.name in existing:
                continue
            with open(pdf, "rb") as f:
                up = c.post("/api/kb/documents", headers=h, files={"file": (pdf.name, f, "application/pdf")})
            print(f"  [{key}] upload {pdf.name}: {up.status_code}")
            up.raise_for_status()
        for _ in range(120):  # wait for background processing
            docs = c.get("/api/kb/documents", headers=h).json()["documents"]
            if all(d["status"] != "processing" for d in docs):
                break
            time.sleep(1)
        for d in docs:
            print(f"  [{key}] {d['filename']}: {d['status']} pages={d['pages']} chunks={d['chunks']} rules={d['rules']}")
        c.patch("/api/assistant", headers=h, json={
            "assistant_name": o["assistant_name"], "brand_color": o["brand_color"],
            "welcome_message": o["welcome"], "suggestions": o["suggestions"]})
        a = c.get("/api/assistant", headers=h).json()
        tokens[key] = a["token"]
        print(f"  [{key}] assistant URL: {a['url']}")
    (DATA / ".tokens.json").write_text(json.dumps(tokens), encoding="utf-8")
    return tokens


def evaluate(c: httpx.Client, tokens: dict) -> int:
    fails, rows = 0, []
    for q in spec["questions"]:
        t = time.time()
        r = c.post("/api/ask", json={"token": tokens[q["org"]], "question": q["q"]}, timeout=300)
        dt = time.time() - t
        d = r.json()
        exp, problems = q["expect"], []
        if d.get("status") != exp["status"]:
            problems.append(f"status {d.get('status')} != {exp['status']}")
        verdict = (d.get("decisions") or {}).get("verdict")
        if "verdict" in exp and verdict != exp["verdict"]:
            problems.append(f"verdict {verdict} != {exp['verdict']}")
        if "doc" in exp and not any(x["document"] == exp["doc"] for x in d.get("references", [])):
            problems.append(f"missing reference {exp['doc']}")
        if exp["status"] == "no_knowledge" and d.get("references"):
            problems.append("no_knowledge but references returned")
        ok = not problems
        fails += not ok
        refs = ", ".join(sorted({f"{x['document']} p.{x['page']}" for x in d.get("references", [])})) or "-"
        print(f"\n#{q['id']:>2} [{'PASS' if ok else 'FAIL'}] ({q['org']}, {q['type']}) {dt:.1f}s")
        print(f"   Q: {q['q']}")
        print(f"   A: {d.get('answer', '')[:400].replace(chr(10), ' ')}")
        print(f"   status={d.get('status')} verdict={verdict} type={d.get('question_type', {}).get('label')} refs: {refs}")
        for p in problems:
            print("   !!", p)
        rows.append({**q, "result": d, "pass": ok, "seconds": round(dt, 1)})
    (DATA / "eval_results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\n{len(rows) - fails}/{len(rows)} passed")
    return fails


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--seed-only", action="store_true")
    ap.add_argument("--eval-only", action="store_true")
    a = ap.parse_args()
    with httpx.Client(base_url=a.base, timeout=120) as c:
        if a.eval_only:
            toks = json.loads((DATA / ".tokens.json").read_text())
        else:
            print("Seeding...")
            toks = seed(c)
        if not a.seed_only:
            sys.exit(1 if evaluate(c, toks) else 0)
