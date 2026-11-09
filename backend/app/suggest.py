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


# ---- "I couldn't find that" replies: say what the documents DO cover -------------------------------------------

_HEADING_END = re.compile(r"[.,;:!?)\d]$")
_SENTENCE_END = re.compile(r"[.!?:]$")


def _headings(text: str, title: str) -> list[str]:
    """Short section titles inside a passage ("Late Payment", "Fee Waiver"): a short capitalised line without end
    punctuation, after a finished sentence and before a new sentence."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out = []
    for i, ln in enumerate(lines):
        words = ln.split()
        if not (1 <= len(words) <= 5 and 3 <= len(ln) <= 40) or not ln[0].isupper() or _HEADING_END.search(ln):
            continue
        if i + 1 >= len(lines) or not (lines[i + 1][0].isupper() or lines[i + 1][0] in "-•*"):
            continue
        prev = lines[i - 1] if i else ""
        if len(prev.split()) > 5 and not _SENTENCE_END.search(prev):  # tail of a wrapped sentence, not a title
            continue
        low, tl = ln.lower(), title.lower()
        if low == tl or low in tl or tl in low:
            continue
        out.append(ln)
    return out


def doc_topics(org_id: int, per_doc: int = 5) -> list[tuple[str, list[str]]]:
    """[(document title, [topics])]: benefit names from the rule cards first, then section titles."""
    from .db import Chunk
    db = SessionLocal()
    try:
        docs = db.query(Document).filter(Document.org_id == org_id, Document.status == "ready").order_by(Document.id).all()
        benefits: dict[int, list[str]] = {}
        for r in db.query(Rule).filter(Rule.org_id == org_id).order_by(Rule.id):
            if r.benefit.lower() not in NOISE and r.benefit not in benefits.setdefault(r.doc_id, []):
                benefits[r.doc_id].append(r.benefit)
        out = []
        for d in docs:
            title = _title(d.filename)
            topics = list(benefits.get(d.id, []))
            for c in db.query(Chunk).filter(Chunk.org_id == org_id, Chunk.doc_id == d.id).order_by(Chunk.id):
                for h in _headings(c.text, title):
                    if not any(h.lower() == t.lower() or h.lower() in t.lower() or t.lower() in h.lower() for t in topics):
                        topics.append(h)
            out.append((title, topics[:per_doc]))
        return out
    finally:
        db.close()


def menu_text(org_id: int, max_docs: int = 6) -> str:
    rows = doc_topics(org_id)
    lines = [f"• {t}: {', '.join(tp)}" if tp else f"• {t}" for t, tp in rows[:max_docs]]
    if len(rows) > max_docs:
        lines.append(f"• …and {len(rows) - max_docs} more documents")
    return "\n".join(lines)


def not_found_message(menu: str, typed: str, hits: list, best: float, org_name: str) -> str:
    """Never just "couldn't find": name what was asked, offer the closest section if there is one, and list what the
    knowledge base covers so the visitor can steer."""
    asked = typed.strip().rstrip("?.! ")
    asked = asked if len(asked) <= 70 else asked[:67].rstrip() + "…"
    parts = [f"I couldn't find anything about “{asked}” in {org_name}'s documents, so I won't guess."]
    if hits and best >= 0.04:
        h = hits[0]
        parts.append(f"The closest I have is {h.document}, p.{h.page}, but it doesn't seem to answer this.")
    if menu:
        parts.append("Here's what I can help with:\n" + menu)
    parts.append("Try one of the suggestions below, or ask again using the wording from the policy. "
                 f"For anything else, please contact {org_name} directly.")
    return "\n\n".join(parts)
