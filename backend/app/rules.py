"""Rule cards: typed conditions extracted from policy text at upload time.

Extraction = deterministic pattern miner (+ optional LLM pass whose output is accepted only if its
quoted evidence really appears on the page). Evaluation at question time is pure code (no LLM).
"""
import re
from dataclasses import dataclass

from . import llm

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
OPS = {">=", ">", "<=", "<", "==", "!=", "is_true", "is_false"}
GENERIC_HEADINGS = {"eligibility", "requirements", "criteria", "overview", "conditions", "notes", "how to apply",
                    "application process", "eligibility criteria", "important notes", "summary", "rules", "process"}
BENEFIT_RE = re.compile(
    r"\b(?:for|receive|get|qualify for|apply for|obtain|awarded)\s+(?:the\s+|a\s+|an\s+)?"
    r"((?:[A-Z][\w&'-]*\s)*?[A-Z][\w&'-]*\s(?:Scholarship|Leave|Program|Programme|Allowance|Grant|Bursary|"
    r"Waiver|Bonus|Benefit|Reimbursement|Work|Award))\b")
UP = r"(?:or above|or higher|and above|and higher|or more|at least|minimum|onwards|or later|beyond)"
DOWN = r"(?:at most|maximum|no more than|up to|or lower|or below|not exceed|no higher)"


@dataclass
class RuleCard:
    benefit: str
    field: str
    label: str
    operator: str
    value: str
    page: int
    evidence: str
    source: str = "pattern"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).replace("  ", " ").strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _is_heading(line: str) -> bool:
    l = line.strip()
    return (3 <= len(l) <= 70 and not l.endswith((".", ":", ";", ",", "?")) and l[0].isupper()
            and not re.match(r"^[\-•*\d]", l) and len(l.split()) <= 9)


def _window(text: str, start: int, end: int, n: int = 60) -> str:
    return text[max(0, start - n): end + n].lower()


def _benefit_for(sentence: str, current: str) -> str:
    m = BENEFIT_RE.search(sentence)
    return m.group(1).strip() if m else current


def _num(x: str) -> str:
    v = float(x.replace(",", ""))
    return str(int(v)) if v == int(v) else str(v)


def mine_page(text: str, page: int) -> list[RuleCard]:
    cards: list[RuleCard] = []
    current = ""
    # Sentences/bullets with the heading they sit under
    units: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush():
        if buf:
            for s in re.split(r"(?<=[.!?])\s+|\n(?=[\-•*\d])", " ".join(buf).replace("\n", " ")):
                if s.strip():
                    units.append((current, s.strip()))
            buf.clear()

    lines = text.split("\n")
    if page == 1 and lines:
        lines = lines[1:]  # first line of a document is its title, not a policy heading
    for line in lines:
        if _is_heading(line):
            flush()
            if norm(line) not in GENERIC_HEADINGS:
                current = line.strip()
        else:
            if re.match(r"^\s*[\-•*]|^\s*\d+[.)]\s", line):
                flush()
            buf.append(line.strip())
    flush()

    for heading, sent in units:
        benefit = _benefit_for(sent, heading) or "General policy"
        low = sent.lower()

        def add(field, label, op, value):
            cards.append(RuleCard(benefit, field, label, op, value, page, sent))

        for m in re.finditer(r"\bgpa\b[^.;\n\d]{0,40}?(\d(?:\.\d{1,2})?)|(\d\.\d{1,2})\s*(?:or [a-z]+\s*)?gpa", low):
            val = m.group(1) or m.group(2)
            w = _window(low, m.start(), m.end(), 40)
            op = ">="
            if re.search(r"below|under|less than", w):
                op = "<"
            elif re.search(DOWN, w):
                op = "<="
            add("gpa", "Cumulative GPA", op, _num(val))
        for m in re.finditer(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)[- ]year\b", low):
            w = _window(low, m.start(), m.end(), 40)
            op = ">=" if re.search(UP, w) else "=="
            add("year", "Year of study", op, str(ORD[m.group(1)]))
        for m in re.finditer(r"(\d+)\s*(months?|years?)\s+(?:of\s+)?(?:continuous\s+|full-time\s+)?"
                             r"(?:service|employment|tenure)", low):
            months = int(m.group(1)) * (12 if m.group(2).startswith("year") else 1)
            w = _window(low, m.start(), m.end(), 30)
            add("tenure_months", "Months of service", "<" if "less than" in w else ">=", str(months))
        for m in re.finditer(r"attendance[^.\d]{0,30}(\d{2,3})\s*%|(\d{2,3})\s*%\s*attendance", low):
            add("attendance_percent", "Attendance (%)", ">=", m.group(1) or m.group(2))
        for m in re.finditer(r"(?:at least|minimum of)\s+(\d+)\s+credits?", low):
            add("credits", "Credits completed", ">=", m.group(1))
        for m in re.finditer(r"(?:at least|minimum of)\s+(\d+)\s+(?:working |business |calendar )?days?"
                             r"(?:'|’)?\s*(?:of\s+)?(?:advance\s+)?(?:notice|in advance|before)", low):
            add("notice_days", "Days of advance notice", ">=", m.group(1))
        for m in re.finditer(r"(?:up to|maximum of|no more than|at most)\s+(\d+)\s+days?\s+(?:per|a|each)\s+week", low):
            add("days_per_week", "Remote days per week", "<=", m.group(1))
        for m in re.finditer(r"(?:not|never|cannot|may not|must not|no)\s+(?:currently\s+|already\s+)?"
                             r"(?:hold|holding|receiv(?:e|ing)|have|having|be on)\s+(?:an?\s+|any\s+|another\s+|other\s+)?"
                             r"([a-z][a-z ]{2,40}?(?:scholarship|grant|aid|leave|loan|allowance|award|bursary|probation|warning))", low):
            thing = re.sub(r"\b(any|other|another|an|a)\b", "", m.group(1)).strip()
            add("holds_" + slug(thing), f"Holds a {thing.title()}", "is_false", "false")
        for m in re.finditer(r"(?:must|need to|required to|should)\s+(?:have|obtain|submit|provide|hold|complete|get)\s+"
                             r"(?:an?\s+|the\s+|written\s+|prior\s+|signed\s+|formal\s+|valid\s+)*"
                             r"([a-z][a-z ]{2,40}?(?:approval|consent|certificate|clearance|letter|form|report|recommendation|agreement))", low):
            thing = m.group(1).strip()
            add("has_" + slug(thing), f"Has {thing}", "is_true", "true")
        for m in re.finditer(r"requires?\s+(?:an?\s+|the\s+|written\s+|prior\s+|signed\s+|formal\s+)*"
                             r"([a-z][a-z ]{2,30}?(?:approval|consent|certificate|clearance|recommendation))", low):
            thing = m.group(1).strip()
            add("has_" + slug(thing), f"Has {thing}", "is_true", "true")
    return dedupe(cards)


def dedupe(cards: list[RuleCard]) -> list[RuleCard]:
    seen, out = set(), []
    for c in cards:
        key = (norm(c.benefit), c.field, c.operator, c.value, c.page)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


RULE_CUES = re.compile(r"eligib|must|require|minimum|at least|not allowed|only if|qualif|no more than|maximum", re.I)

LLM_RULE_SYSTEM = (
    "You extract eligibility/policy conditions from a policy page as strict JSON. "
    'Return {"rules":[{"benefit":"name of the benefit/policy","field":"snake_case_fact_name",'
    '"label":"human label","operator":">=|>|<=|<|==|!=|is_true|is_false","value":"number or true/false",'
    '"quote":"exact sentence copied from the text"}]}. Only include conditions explicitly stated. '
    "Never invent conditions. If none, return {\"rules\":[]}."
)


async def llm_rules(text: str, page: int) -> list[RuleCard]:
    try:
        data = await llm.chat_json(LLM_RULE_SYSTEM, text[:3000])
    except llm.LLMError:
        return []
    page_norm = norm(text)
    out = []
    for r in data.get("rules", []) if isinstance(data, dict) else []:
        try:
            op = str(r["operator"]).strip()
            quote = str(r["quote"])
            field = slug(str(r["field"]))
            value = str(r["value"]).strip().lower()
            if op not in OPS or not field or len(norm(quote)) < 12 or norm(quote)[:80] not in page_norm:
                continue  # grounding check: evidence must really be on the page
            if op in (">=", ">", "<=", "<"):
                value = _num(value)
            elif op == "is_true":
                value = "true"
            elif op == "is_false":
                value = "false"
            out.append(RuleCard(str(r.get("benefit") or "General policy")[:150], field,
                                str(r.get("label") or field)[:150], op, value, page, quote[:400], "llm"))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _jaccard(a: str, b: str) -> float:
    x, y = set(norm(a).split()), set(norm(b).split())
    return len(x & y) / max(1, len(x | y))


def gate_llm_rules(pattern_cards: list[RuleCard], llm_cards: list[RuleCard]) -> list[RuleCard]:
    """Small LLMs over-generate. Keep an LLM rule only if it is numeric, attaches to a benefit the pattern
    miner already found, and is NOT a re-statement of something the miner already captured."""
    benefits = {norm(c.benefit) for c in pattern_cards if c.benefit != "General policy"}
    out = []
    for c in llm_cards:
        if c.operator not in (">=", ">", "<=", "<") or norm(c.benefit) not in benefits:
            continue
        same_page = [p for p in pattern_cards if p.page == c.page]
        if any(_jaccard(c.evidence, p.evidence) > 0.4 or (p.operator, p.value) == (c.operator, c.value)
               for p in same_page):
            continue
        out.append(c)
    return out


def evaluate(rule, facts: dict) -> tuple[str, object]:
    """Pure-code Boolean decision. Returns (pass|fail|unknown, actual_value)."""
    if rule.field not in facts or facts[rule.field] is None:
        return "unknown", None
    actual = facts[rule.field]
    op = rule.operator
    try:
        if op == "is_true":
            return ("pass" if bool(actual) else "fail"), actual
        if op == "is_false":
            return ("pass" if not bool(actual) else "fail"), actual
        a, b = float(actual), float(rule.value)
        ok = {">=": a >= b, ">": a > b, "<=": a <= b, "<": a < b, "==": a == b, "!=": a != b}[op]
        return ("pass" if ok else "fail"), actual
    except (ValueError, TypeError, KeyError):
        return "unknown", actual


def describe(rule) -> str:
    sym = {">=": "at least", ">": "more than", "<=": "at most", "<": "less than", "==": "exactly", "!=": "not"}
    if rule.operator == "is_true":
        return f"{rule.label}: required"
    if rule.operator == "is_false":
        return f"{rule.label}: must not apply"
    return f"{rule.label}: {sym[rule.operator]} {rule.value}"
