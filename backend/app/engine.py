"""The question-answering pipeline.

  question -> [S1] classify -> retrieve (tenant-scoped) -> [S1] choose policy
           -> [LLM] extract user facts  ||  [S1] evidence-support score
           -> [S1 x N, parallel] Boolean rule checks -> [App] combine -> [LLM] phrase answer

Each stage is emitted as an event so the UI can animate the pipeline ("How I decided").
"""
import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

import numpy as np

from . import classifier, llm, models_s1, rules, smalltalk
from .config import settings
from .db import Document, Organization, QuestionLog, Rule, SessionLocal
from .retrieval import Hit, retrieve

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4,
       "5th": 5, "freshman": 1, "sophomore": 2, "junior": 3, "senior": 4}
NEG = re.compile(r"\b(no|not|don't|dont|do not|doesn't|never|without|haven't|have not|hasn't|none)\b")
POS = re.compile(r"\b(have|has|hold|holds|holding|receive|receiving|received|existing|current|currently|already|got|with|on)\b")
MODAL = re.compile(r"\b(can i|could i|am i|do i|would i|will i|may i|eligible|qualify|entitled|allowed|permitted|"
                   r"does my|will my|is it ok|am i able)\b")
INFO_START = re.compile(r"^(what|which|who|whom|when|where|why|how (much|many|long|often|early|late)|list|tell me|explain|"
                        r"describe|give me)\b")
ELIGIBILITY_WORDS = re.compile(r"\b(eligible|eligibility|qualify|qualifies|entitled|am i allowed|can i get|can i receive|"
                               r"do i get|will i get|would i get)\b")
FACT_NUMERIC = {"gpa", "year", "tenure_months", "attendance_percent", "amount", "notice_days", "days_per_week",
                "credits"}


@dataclass
class RuleView:
    id: int
    doc_id: int
    document: str
    page: int
    benefit: str
    field: str
    label: str
    operator: str
    value: str
    evidence: str


@dataclass
class Context:
    org_name: str
    assistant_name: str
    hits: list[Hit]
    rules: list[RuleView]
    doc_count: int
    ready_count: int


def load_context(org_id: int, question: str) -> Context:
    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        docs = db.query(Document).filter(Document.org_id == org_id).all()
        ready = [d for d in docs if d.status == "ready"]
        names = {d.id: d.filename for d in docs}
        rs = [RuleView(r.id, r.doc_id, names.get(r.doc_id, "?"), r.page, r.benefit, r.field, r.label, r.operator,
                       r.value, r.evidence)
              for r in db.query(Rule).filter(Rule.org_id == org_id).all()]
        hits = retrieve(db, org_id, question) if ready else []
        return Context(org.name, org.assistant_name, hits, rs, len(docs), len(ready))
    finally:
        db.close()


# ---------------------------------------------------------------- System 1 decisions

def choose_policy(question: str, rs: list[RuleView]) -> dict:
    """Choice decision: which policy/benefit does this question concern?"""
    groups: dict[str, list[RuleView]] = {}
    for r in rs:
        if r.benefit != "General policy":
            groups.setdefault(r.benefit, []).append(r)
    if not groups:
        return {"benefit": None, "score": 0.0, "alternatives": []}
    q = set(models_s1.tokens(question))
    names = list(groups)
    desc = [f"{n}. " + " ".join(sorted({r.label for r in groups[n]})) for n in names]
    sims = models_s1.embed(desc) @ models_s1.embed([question])[0]
    scored = []
    for n, s in zip(names, sims):
        nt = set(models_s1.tokens(n))
        overlap = len(q & nt) / max(1, len(nt))
        cos = float(max(0.0, (s - 0.4) / 0.4)) if settings.embed_backend != "hash" else 0.0
        scored.append((n, round(0.65 * overlap + 0.35 * cos, 3), overlap))
    scored.sort(key=lambda x: -x[1])
    best = scored[0]
    ok = best[1] >= 0.35 and (best[2] > 0 or settings.embed_backend == "hash" or best[1] >= 0.5)
    return {"benefit": best[0] if ok else None, "score": best[1],
            "alternatives": [{"benefit": n, "score": s} for n, s, _ in scored[:3]]}


def pattern_facts(question: str, fields: dict[str, str]) -> dict:
    """Deterministic fact extractor for common quantities; also validates/falls back when the LLM is down."""
    low = question.lower()
    facts: dict = {}
    if "gpa" in fields:
        m = re.search(r"gpa\s*(?:of|is|was|:|=)?\s*(\d(?:\.\d{1,2})?)|(\d(?:\.\d{1,2})?)\s*(?:/\s*4(?:\.0)?\s*)?gpa", low)
        if m:
            facts["gpa"] = float(m.group(1) or m.group(2))
    if "year" in fields:
        m = re.search(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|freshman|sophomore|junior|senior)"
                      r"(?:[- ]year)?\b", low)
        m2 = re.search(r"\byear\s*(\d)\b|\b(\d)(?:st|nd|rd|th)?[- ]year\b", low)
        if m and (("year" in low[m.start():m.end() + 6]) or m.group(1) in ("freshman", "sophomore", "junior", "senior")):
            facts["year"] = ORD[m.group(1)]
        elif m2:
            facts["year"] = int(m2.group(1) or m2.group(2))
    if "tenure_months" in fields:
        m = re.search(r"(\d+)\s*(months?|years?)(?!\s*(?:of study|old))", low)
        if m:
            facts["tenure_months"] = int(m.group(1)) * (12 if m.group(2).startswith("year") else 1)
    if "attendance_percent" in fields:
        m = re.search(r"(\d{2,3})\s*%", low)
        if m:
            facts["attendance_percent"] = int(m.group(1))
    if "amount" in fields:
        m = re.search(r"[$₹€£]\s?(\d[\d,]*)|(\d[\d,]*)\s*(?:dollars|usd)", low)
        if m:
            facts["amount"] = float((m.group(1) or m.group(2)).replace(",", ""))
    if "days_per_week" in fields:
        m = re.search(r"(\d+)\s*days?\s*(?:per|a|each|/)\s*week", low)
        if m:
            facts["days_per_week"] = int(m.group(1))
    if "notice_days" in fields:
        m = re.search(r"(\d+)\s*(?:working |business )?days?(?!\s*(?:per|a|each)\s*week)", low)
        if m:
            facts["notice_days"] = int(m.group(1))
    if "credits" in fields:
        m = re.search(r"(\d+)\s*credits?", low)
        if m:
            facts["credits"] = int(m.group(1))
    for f, label in fields.items():
        if not f.startswith(("holds_", "has_")):
            continue
        words = [w for w in f.split("_")[1:] if len(w) > 2]
        if not words:
            continue
        # Anchor on the words appearing together ("sports ... scholarship"), so an earlier stray "scholarship"
        # (e.g. in a previous question about the Merit Scholarship) can't hide a negation like "no sports scholarship".
        seq = re.search(r".{0,20}?".join(re.escape(w) for w in words), low)
        if seq:
            at = seq.start()
        else:
            pos = [low.find(w) for w in words]
            if any(p < 0 for p in pos):
                continue
            at = min(pos)
        before = low[max(0, at - 30):at]
        facts[f] = False if NEG.search(before) else True
    return facts


FACT_SYSTEM = (
    "You extract facts about the USER from their question. Return strict JSON object mapping each field name "
    "to a number or true/false, ONLY for facts the user actually stated. Omit anything not stated. Never guess."
)


async def llm_facts(question: str, fields: dict[str, str]) -> dict:
    spec = "\n".join(f'- "{f}": {label}' for f, label in fields.items())
    data = await llm.chat_json(FACT_SYSTEM, f"Fields:\n{spec}\n\nQuestion: {question}\n\nJSON:")
    return ground_facts(question, parse_facts(data, fields))


NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "first": 1, "second": 2, "third": 3, "fourth": 4}


def ground_facts(question: str, facts: dict) -> dict:
    """Small models invent facts. Keep an LLM-extracted fact only if it is verifiable in the question text:
    numbers must literally appear (as digits or number words); yes/no facts are decided by deterministic
    keyword checks only, so LLM booleans are dropped."""
    low = question.lower()
    seen = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", low)}
    seen |= {float(v) for w, v in NUMBER_WORDS.items() if re.search(rf"\b{w}\b", low)}
    out = {}
    for k, v in facts.items():
        if isinstance(v, bool):
            continue
        if float(v) in seen or (k == "tenure_months" and float(v) / 12 in seen):
            out[k] = v
    return out


def parse_facts(data, fields: dict) -> dict:
    out = {}
    for f in fields:
        v = data.get(f) if isinstance(data, dict) else None
        if isinstance(v, bool) or (isinstance(v, (int, float)) and not isinstance(v, bool)):
            out[f] = v
        elif isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "yes"):
                out[f] = True
            elif s in ("false", "no"):
                out[f] = False
            else:
                try:
                    out[f] = float(s)
                except ValueError:
                    pass
    return out


def _timed(fn):
    t = time.perf_counter()
    r = fn()
    return r, round((time.perf_counter() - t) * 1000)


async def decide_boolean(rule: RuleView, facts: dict) -> dict:
    t = time.perf_counter()
    result, actual = rules.evaluate(rule, facts)
    return {"field": rule.field, "label": rule.label, "rule": rules.describe(rule), "operator": rule.operator,
            "value": rule.value, "actual": actual, "result": result, "document": rule.document, "page": rule.page,
            "evidence": rule.evidence, "ms": round((time.perf_counter() - t) * 1000, 2)}


async def decide_score(question: str, passages: list[str]) -> dict:
    t = time.perf_counter()
    scores = await asyncio.to_thread(models_s1.rerank, question, passages)
    return {"support": round(float(max(scores, default=0.0)), 3), "ms": round((time.perf_counter() - t) * 1000)}


def combine(results: list[dict]) -> tuple[str, list[str]]:
    """Application logic: AND over all conditions. Unknown facts are surfaced, never assumed."""
    if any(r["result"] == "fail" for r in results):
        return "not_eligible", []
    missing = [r["label"] for r in results if r["result"] == "unknown"]
    if missing:
        return "need_info", missing
    return "eligible", []


# ---------------------------------------------------------------- answer composition

ANSWER_SYSTEM = (
    "You are {assistant}, the assistant of {org}. Answer ONLY from the provided context. "
    "Be concise (under 90 words), warm and clear, plain text, no markdown, no lists. "
    "Mention source documents like (Doc.pdf, p.4). If the context does not contain the answer, say you could not find it."
)

DECISION_SYSTEM = (
    "You are {assistant}, the assistant of {org}. A policy check has already been run and its result is final. "
    "Write a short, friendly reply (under 80 words, plain text, no lists): begin with the result, then explain it "
    "using ONLY the listed reasons, in natural sentences. Do not add other conditions. If information is missing, "
    "ask for it politely and do not say whether the user is eligible. Cite the document once like (Doc.pdf, p.1)."
)

VERDICT_TEXT = {"eligible": "Eligible", "not_eligible": "Not eligible", "need_info": "More information needed"}


def reason(r: dict) -> str:
    """Accurate plain-English sentence for one decided condition (written by code, not by the LLM)."""
    label, said, op, val = r["label"], r["actual"], r["operator"], r["value"]
    low = label[0].lower() + label[1:]
    thing = re.sub(r"^(Holds an?|Has) ", "", label)
    art = "a " if label.startswith("Holds a ") else ""
    if r["result"] == "unknown":
        if op == "is_false":
            return f"I don't yet know whether you hold {art}{thing}."
        if op == "is_true":
            return f"I don't yet know whether you have {thing}."
        return f"I don't yet know your {low}."
    if op == "is_false":
        return f"You don't hold {art}{thing}." if r["result"] == "pass" else f"You hold {art}{thing}, which isn't allowed."
    if op == "is_true":
        return f"You have {thing}." if r["result"] == "pass" else f"You don't have {thing}."
    sym = {">=": "at least", ">": "more than", "<=": "at most", "<": "less than", "==": "exactly", "!=": "not"}[op]
    ok = "meets" if r["result"] == "pass" else "does not meet"
    return f"Your {low} ({said}) {ok} the requirement of {sym} {val}."


_AFFIRM = re.compile(r"(you are|you're|you appear to be|you qualify|you do qualify)[^.]{0,25}(eligible|qualif)", re.I)
_NEGATE = re.compile(r"(not eligible|ineligible|do not qualify|don't qualify|cannot qualify|not qualify|not able to)", re.I)


def contradicts(answer: str, verdict: str | None) -> bool:
    """Guard against small-model slips: the app's decision is the source of truth."""
    if not verdict:
        return False
    a = answer.lower()
    if verdict == "eligible":
        return bool(_NEGATE.search(a))
    if verdict == "not_eligible":
        return bool(_AFFIRM.search(a)) and not _NEGATE.search(a)
    return bool(_AFFIRM.search(a))  # need_info: any claim of eligibility is premature


def _best_sentence(question: str, hits: list[Hit]) -> str:
    q = set(models_s1.tokens(question))
    best, best_s = "", -1.0
    for h in hits[:3]:
        for s in re.split(r"(?<=[.!?])\s+|\n", h.text):
            s = s.strip()
            if len(s) < 20:
                continue
            sc = len(q & set(models_s1.tokens(s))) / (1 + len(s) / 400)
            if sc > best_s:
                best, best_s = f"{s} ({h.document}, p.{h.page})", sc
    return best


def fallback_answer(question: str, hits: list[Hit], verdict: str | None, results: list[dict],
                    missing: list[str], benefit: str | None) -> str:
    if verdict:
        head = {"eligible": f"Good news: you appear to be eligible for the {benefit}.",
                "not_eligible": f"Based on the policy, you are not eligible for the {benefit}.",
                "need_info": f"I need a bit more information to check the {benefit}: " + ", ".join(missing).lower() + "."}[verdict]
        why = " ".join(reason(r) for r in results if verdict != "need_info" or r["result"] != "unknown")
        src = results[0]
        return f"{head} {why} (Source: {src['document']}, p.{src['page']})".replace("  ", " ")
    return _best_sentence(question, hits) or "I found related passages but could not summarise them."


def _context_block(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{i}] {h.document}, page {h.page}:\n{h.text}" for i, h in enumerate(hits[:4], 1))


def build_references(hits: list[Hit], results: list[dict], best: float) -> list[dict]:
    refs, seen = [], set()
    for r in results:
        key = (r["document"], r["page"])
        if key not in seen:
            seen.add(key)
            refs.append({"document": r["document"], "page": r["page"], "snippet": r["evidence"][:300],
                         "score": None, "kind": "rule"})
    for h in hits:
        key = (h.document, h.page)
        if key in seen or len(refs) >= 4 or h.score < max(settings.min_support, best * 0.35):
            continue
        seen.add(key)
        refs.append({"document": h.document, "page": h.page, "snippet": h.text[:300],
                     "score": round(h.score, 3), "kind": "passage"})
    return refs


def _route(org_id: int, question: str):
    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        docs = [d.filename for d in db.query(Document).filter(Document.org_id == org_id, Document.status == "ready")]
        return smalltalk.route(question, org.assistant_name, org.name, list(org.suggestions or []), docs)
    finally:
        db.close()


def _ev(**kw):
    return {"type": "step", **kw}


async def run(org_id: int, question: str) -> AsyncIterator[dict]:
    t0 = time.perf_counter()
    steps: list[dict] = []

    def done(step_id, label, kind, t_start, detail="", status="done"):
        ms = round((time.perf_counter() - t_start) * 1000)
        s = {"id": step_id, "label": label, "kind": kind, "status": status, "ms": ms, "detail": detail}
        steps.append(s)
        return _ev(**s)

    def running(step_id, label, kind):
        return _ev(id=step_id, label=label, kind=kind, status="running", ms=0, detail="")

    # 0. Small talk ("hi", "thanks", "what can you do") is answered by the app: instant, no search, no LLM
    routed = await asyncio.to_thread(_route, org_id, question)
    if routed:
        intent, chat, as_answered = routed
        t = time.perf_counter()
        yield done("classify", "Classify question", "s1", t, f"{intent.replace('_', ' ')} (rule)")
        for sid, label, kind in (("retrieve", "Search documents", "s1"), ("choose", "Choose policy", "s1"),
                                 ("understand", "Extract facts", "llm"), ("decide", "Run decisions", "s1"),
                                 ("combine", "Combine results", "app"), ("answer", "Write answer", "llm")):
            yield _ev(id=sid, label=label, kind=kind, status="skipped", ms=0, detail="not needed")
        yield {"type": "token", "text": chat}
        yield {"type": "final", "data": _final(chat, "answered", [], intent, 1.0, None, steps, t0, False)}
        _log(org_id, question, intent, "answered" if as_answered else "no_knowledge", False, t0)
        return

    # 1. Retrieval (tenant-scoped) -------------------------------------------------
    yield running("retrieve", "Search knowledge base", "s1")
    t = time.perf_counter()
    ctx = await asyncio.to_thread(load_context, org_id, question)
    hits = ctx.hits
    best = hits[0].score if hits else 0.0
    yield done("retrieve", "Search knowledge base", "s1", t,
               f"{len(hits)} passages, best match {best:.0%}" if hits else "no documents indexed")

    # 2. Classification (System 1) -----------------------------------------------
    yield running("classify", "Classify question", "s1")
    t = time.perf_counter()
    qtype, conf = await asyncio.to_thread(classifier.classify, question)
    yield done("classify", "Classify question", "s1", t, f"{qtype.replace('_', ' ')} ({conf:.0%})")

    # Grounding guard: nothing relevant -> do not invent an answer
    has_rules = bool(ctx.rules)
    choice = await asyncio.to_thread(choose_policy, question, ctx.rules) if has_rules else \
        {"benefit": None, "score": 0.0, "alternatives": []}
    if not hits or (best < settings.min_support and not choice["benefit"]):
        msg = ("This assistant doesn't have any documents yet, so I can't answer questions." if ctx.ready_count == 0
               else "I couldn't find anything about that in the organization's documents, so I won't guess. "
                    "Please contact the organization directly for help.")
        if ctx.ready_count:
            msg = smalltalk.out_of_scope_message(question, ctx.assistant_name, ctx.org_name) or msg
        for sid, label, kind in (("choose", "Choose policy", "s1"), ("understand", "Extract facts", "llm"),
                                 ("decide", "Run decisions", "s1"), ("combine", "Combine results", "app"),
                                 ("answer", "Write answer", "llm")):
            yield _ev(id=sid, label=label, kind=kind, status="skipped", ms=0, detail="skipped")
        yield {"type": "token", "text": msg}
        yield {"type": "final", "data": _final(msg, "no_knowledge", [], qtype, conf, None, steps, t0, False)}
        _log(org_id, question, qtype, "no_knowledge", False, t0)
        return

    # 3. Decide whether structured decisions are needed (application logic) -------
    benefit = choice["benefit"]
    benefit_rules = [r for r in ctx.rules if r.benefit == benefit] if benefit else []
    fields = {r.field: r.label for r in benefit_rules}
    quick = pattern_facts(question, fields) if fields else {}
    modal = bool(MODAL.search(question.lower()))
    # a decision is only meaningful if the user states facts about themselves or asks "can I / am I eligible"
    eligibility_like = (qtype == "eligibility" and (modal or bool(quick))) or (modal and bool(quick))
    # "What GPA do I need for X?" or "How many days do I get?" ask for information, not for a verdict on the user
    if INFO_START.match(question.strip().lower()) and not ELIGIBILITY_WORDS.search(question.lower()):
        eligibility_like = False
    use_decisions = bool(benefit_rules) and eligibility_like

    decisions: dict | None = None
    results: list[dict] = []
    verdict, missing = None, []
    llm_ok = True

    if use_decisions:
        yield running("choose", "Choose policy", "s1")
        t = time.perf_counter()
        yield done("choose", "Choose policy", "s1", t, f"{benefit} ({choice['score']:.0%} match)")

        # 4. LLM understands the question  ||  S1 scores the evidence (parallel)
        yield running("understand", "Extract facts", "llm")
        t = time.perf_counter()
        # The assignment wants the LLM to understand the question, so it always runs here (in parallel with the
        # evidence-score model). Its output is grounded against the question text, and patterns win on conflict.
        llm_task = asyncio.create_task(llm_facts(question, fields)) if settings.llm_provider != "mock" else None
        score_task = asyncio.create_task(decide_score(question, [h.text for h in hits]))
        facts = dict(quick)
        detail_note = "patterns"
        if llm_task:
            try:
                for k, v in (await llm_task).items():
                    facts.setdefault(k, v)  # deterministic patterns win; LLM fills the gaps
                detail_note = "LLM + patterns"
            except llm.LLMError:
                llm_ok = False
                detail_note = "LLM unavailable, used patterns"
        shown = ", ".join(f"{fields.get(k, k)}={v}" for k, v in facts.items()) or "no facts stated"
        yield done("understand", "Extract facts", "llm", t, f"{shown} [{detail_note}]",
                   "done" if llm_ok else "error")
        score = await score_task

        # 5. Parallel Boolean decisions
        yield running("decide", "Run decisions", "s1")
        t = time.perf_counter()
        try:
            results = list(await asyncio.gather(*[decide_boolean(r, facts) for r in benefit_rules]))
        except Exception:
            yield done("decide", "Run decisions", "s1", t, "decision model failed", "error")
            msg = "Sorry, I had trouble evaluating the policy conditions. Please try again."
            yield {"type": "token", "text": msg}
            yield {"type": "final", "data": _final(msg, "error", [], qtype, conf, None, steps, t0, False)}
            _log(org_id, question, qtype, "error", True, t0)
            return
        passed = sum(r["result"] == "pass" for r in results)
        yield done("decide", "Run decisions", "s1", t,
                   f"{len(results)} checks in parallel: {passed} met")

        yield running("combine", "Combine results", "app")
        t = time.perf_counter()
        verdict, missing = combine(results)
        yield done("combine", "Combine results", "app", t, verdict.replace("_", " "))
        decisions = {"path": "decision", "benefit": benefit, "choice": choice, "facts": facts, "booleans": results,
                     "score": score, "verdict": verdict, "missing": missing}
    else:
        for sid, label, kind, why in (("choose", "Choose policy", "s1", "not needed"),
                                      ("understand", "Extract facts", "llm", "not needed"),
                                      ("decide", "Run decisions", "s1", "no multi-condition decision"),
                                      ("combine", "Combine results", "app", "not needed")):
            yield _ev(id=sid, label=label, kind=kind, status="skipped", ms=0, detail=why)
        decisions = {"path": "retrieval", "benefit": benefit, "choice": choice}
        if qtype == "comparison" and len(choice["alternatives"]) > 1:
            names = [a["benefit"] for a in choice["alternatives"][:2] if a["score"] >= 0.3]
            extra = [r for r in ctx.rules if r.benefit in names]
            if extra:
                decisions["compare_rules"] = [rules.describe(r) + f" [{r.benefit}]" for r in extra]

    # 6. LLM writes the answer -----------------------------------------------------
    yield running("answer", "Write answer", "llm")
    t = time.perf_counter()
    refs = build_references(hits, results, best)
    fallback = fallback_answer(question, hits, verdict, results, missing, benefit)
    decision_text = ""
    if verdict:
        lines = "\n".join(f"- {reason(r)} ({r['document']}, p.{r['page']})" for r in results)
        decision_text = f"Policy check result: {VERDICT_TEXT[verdict]} for the {benefit}.\nReasons:\n{lines}"
        if missing:
            decision_text += "\nAsk the user for: " + ", ".join(missing)
    elif decisions.get("compare_rules"):
        decision_text = "KNOWN CONDITIONS:\n" + "\n".join(decisions["compare_rules"])
    tier = None if verdict else amount_tier(question, hits)
    if tier:  # Choice decision made by the app: which approval level applies to this amount
        amt = f"{tier['amount']:,.0f}" if tier["amount"] == int(tier["amount"]) else f"{tier['amount']:,.2f}"
        sentence = (f"For an amount of {amt}, the required approver is {tier['approver']} "
                    f"({tier['document']}, p.{tier['page']}).")
        decisions["tier"] = {"amount": tier["amount"], "approver": tier["approver"]}
        decision_text = f"Policy check result (computed by the app, do not change it): {sentence}"
        fallback = sentence
        refs.insert(0, {"document": tier["document"], "page": tier["page"], "snippet": tier["evidence"][:300],
                        "score": None, "kind": "rule"})
        refs = [refs[0]] + [r for r in refs[1:] if (r["document"], r["page"]) != (tier["document"], tier["page"])]
    user_prompt = f"Question: {question}\n\n{decision_text}\n\nContext:\n{_context_block(hits)}\n\nAnswer:"
    system = (DECISION_SYSTEM if verdict else ANSWER_SYSTEM).format(assistant=ctx.assistant_name, org=ctx.org_name)
    answer, degraded = "", False
    try:
        async for tok in llm.stream_text(system, user_prompt, fallback):
            answer += tok
            yield {"type": "token", "text": tok}
    except llm.LLMError:
        degraded = True
    if not answer.strip():
        degraded = degraded or settings.llm_provider != "mock"
        answer = fallback
        yield {"type": "token", "text": answer}
    corrected = False
    if not degraded and (contradicts(answer, verdict) or (tier and tier["approver"].lower() not in answer.lower())):
        corrected, answer = True, fallback
        yield {"type": "replace", "text": answer}
    doc_names = list(dict.fromkeys([r["document"] for r in refs] + [h.document for h in hits]))
    fixed = fix_citations(answer, doc_names)
    if fixed != answer:
        answer = fixed
        yield {"type": "replace", "text": answer}
    yield done("answer", "Write answer", "llm", t,
               "template fallback (LLM unavailable)" if degraded else
               (f"{settings.llm_provider}, corrected to match the decision" if corrected else f"{settings.llm_provider}"),
               "error" if degraded else "done")
    status = "needs_info" if verdict == "need_info" else "answered"
    yield {"type": "final", "data": _final(answer.strip(), status, refs, qtype, conf, decisions, steps, t0,
                                           degraded or not llm_ok)}
    _log(org_id, question, qtype, status, use_decisions, t0)


def _final(answer, status, refs, qtype, conf, decisions, steps, t0, degraded):
    return {"answer": answer, "status": status, "references": refs,
            "question_type": {"label": qtype, "confidence": round(conf, 3)}, "decisions": decisions,
            "steps": steps, "degraded": degraded, "latency_ms": round((time.perf_counter() - t0) * 1000)}


def _log(org_id, question, qtype, outcome, used, t0):
    db = SessionLocal()
    try:
        db.add(QuestionLog(org_id=org_id, question=question[:1000], qtype=qtype, outcome=outcome,
                           used_decisions=used, latency_ms=round((time.perf_counter() - t0) * 1000)))
        db.commit()
    finally:
        db.close()


# ---- amount tiers ("Expenses above $500 require approval from a Director") -------------------------------------
# A Choice decision made by the app, not the LLM: models routinely pick the wrong tier when reasoning about numbers.
_MONEY = r"[$₹€£]\s?(\d[\d,]*(?:\.\d+)?)"
_TIER = re.compile(r"\b(up to|upto|above|over|exceeding|more than|greater than|below|under|less than|at most)\s+"
                   + _MONEY + r"[^.;]*?\b(?:can be approved by|approved by|require[s]?(?: approval)?(?: from| by)?|"
                   r"needs? approval (?:from|by)|must be approved by)\s+(?:your |a |an |the )?([A-Za-z][A-Za-z ]{2,40}?)"
                   r"(?=[.;,]|$|\s+(?:Expenses?|Claims?|Purchases?|Amounts?|Submit)\b)", re.I)


def question_amount(question: str) -> float | None:
    m = re.search(_MONEY, question) or re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|usd|rupees|inr|euros|eur|pounds)",
                                                 question, re.I)
    return float(m.group(1).replace(",", "")) if m else None


def amount_tier(question: str, hits: list[Hit]) -> dict | None:
    amount = question_amount(question)
    if amount is None:
        return None
    tiers = []
    for h in hits[:4]:
        for sent in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", h.text)):  # PDF line wraps must not cut a name
            for m in _TIER.finditer(sent):
                kind = m.group(1).lower()
                tiers.append((kind in ("up to", "upto", "below", "under", "less than", "at most"),
                              float(m.group(2).replace(",", "")), m.group(3).strip(), h, sent.strip()))
    if not tiers:
        return None
    over = [t for t in tiers if not t[0] and amount > t[1]]
    if over:
        pick = max(over, key=lambda t: t[1])
    else:
        under = [t for t in tiers if t[0] and amount <= t[1]]
        if not under:
            return None
        pick = min(under, key=lambda t: t[1])
    _, _, who, hit, sent = pick
    return {"amount": amount, "approver": who, "document": hit.document, "page": hit.page, "evidence": sent}


def fix_citations(answer: str, documents: list[str]) -> str:
    """Small models shorten or re-space file names ("Doc.pdf", "Remote Work Policy.pdf"). Snap any cited .pdf name
    to the real document name, so every citation points at a file that exists."""
    if not documents:
        return answer
    for d in documents:  # "Remote Work Policy.pdf" / "remote_work_policy.pdf" -> the real name
        stem = re.escape(d[:-4]).replace("_", "[ _]")
        answer = re.sub(stem + r"\.pdf", d, answer, flags=re.I)
    known = {d.lower() for d in documents}

    def snap(m: re.Match) -> str:
        name = m.group(0)
        if name.lower() in known:
            return next(d for d in documents if d.lower() == name.lower())
        words = set(re.findall(r"[a-z0-9]+", name.lower())) - {"pdf", "doc", "document"}
        # the document sharing the most words with the cited name; otherwise the answer's primary source
        best = max(documents, key=lambda d: len(words & set(re.findall(r"[a-z0-9]+", d.lower()))))
        return best if words & set(re.findall(r"[a-z0-9]+", best.lower())) else documents[0]
    return re.sub(r"[\w\-]+\.pdf", snap, answer, flags=re.I)
