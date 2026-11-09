"""Starter and follow-up questions, built from the organization's own documents (no LLM needed).

Starter questions help a visitor see what the assistant knows before typing; follow-ups appear under each answer."""
import re

from .db import Document, Rule, SessionLocal

MAX_SUGGESTIONS = 6
MORE = "Tell me more details"
# names the rule miner can produce that are not a benefit a person would ask to be eligible for
NOISE = {"general policy", "documents", "document", "requirements", "application", "applications", "forms", "form"}


def _title(filename: str) -> str:
    return re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0]).strip()


def auto_questions(org_id: int) -> list[tuple[str, str]]:
    """(question, document) pairs derived from the rule cards and document titles."""
    db = SessionLocal()
    try:
        docs = {d.id: d.filename for d in db.query(Document).filter(Document.org_id == org_id, Document.status == "ready")}
        seen, out = set(), []
        for r in db.query(Rule).filter(Rule.org_id == org_id).order_by(Rule.id):
            if r.benefit.lower() in NOISE or r.benefit in seen or r.doc_id not in docs:
                continue
            seen.add(r.benefit)
            out.append((f"Am I eligible for the {r.benefit}?", docs[r.doc_id]))
            out.append((f"What are the requirements for the {r.benefit}?", docs[r.doc_id]))
        for name in docs.values():
            out.append((f"What does the {_title(name)} cover?", name))
        return out
    finally:
        db.close()


def _same(a: str, b: str) -> bool:
    a, b = a.lower().strip(" ?."), b.lower().strip(" ?.")
    return a in b or b in a


def all_suggestions(org_id: int, custom: list[str]) -> list[str]:
    """The organization's own starter questions first, then generated ones, without duplicates (max 6)."""
    out = [c for c in custom if c.strip()]
    for q, _ in auto_questions(org_id):
        if len(out) >= MAX_SUGGESTIONS:
            break
        if not any(_same(q, o) for o in out):
            out.append(q)
    return out[:MAX_SUGGESTIONS]


def followups(org_id: int, question: str, status: str, refs: list[dict], custom: list[str], detail: bool) -> list[str]:
    """Chips shown under an answer: ask for more detail, or jump to a related question."""
    if status == "needs_info":
        return []
    if status == "no_knowledge":
        return all_suggestions(org_id, custom)[:3]
    docs = {r["document"] for r in refs}
    pairs = auto_questions(org_id)
    related = [q for q, d in pairs if d in docs and not _same(q, question)]
    rest = [q for q, d in pairs if d not in docs and not _same(q, question)]
    out = [] if detail else [MORE]
    for q in related + rest:
        if len(out) >= 3:
            break
        out.append(q)
    return out
