"""Everyday wording -> the words policy documents use.

People say "money back if I quit"; the policy says "refund" and "withdraw". Search only matches words and meanings that the
document shares, so the retrieval query gets the policy words appended. It is only used for searching: the visitor's own
words are still what the classifier, the rules and the answer see. Adding words can never invent facts, because the answer
is still written only from passages that were found."""
import re

# (what a person might type, the policy words that mean the same thing)
SYNONYMS: list[tuple[str, str]] = [
    (r"money back|get (my|the) money|pay(ing)? me back|repay|give back", "refund"),
    (r"\b(quit|quitting|drop ?out|dropping out|stop studying|unenrol\w*|unenroll\w*|cancel\w* (my )?(enrol\w*|registration|"
     r"course|subscription)|leave the (course|program|programme|university|college|school))\b", "withdraw withdrawal"),
    (r"\b(how much|price|prices|cost|costs|pay|paying|payment|afford|expensive|cheap)\b", "fee fees tuition"),
    (r"\b(last date|due date|cut ?off|closing date|by when|until when)\b", "deadline"),
    (r"\b(paperwork|what (do|should) i (submit|bring|send|upload)|submit anything|need to (submit|provide|bring)|"
     r"documents? (needed|required))\b", "documents required application submit"),
    (r"\b(time off|days off|day off|holiday|holidays|vacation|pto|take a break)\b", "leave annual leave"),
    (r"\b(work(ing)? from home|wfh|work remotely|hybrid)\b", "remote work"),
    (r"\b(taxi|uber|cab|receipt|receipts|reimburse\w*|travel cost|hotel|meal|meals)\b", "expense claim"),
    (r"\b(approve[sd]?|sign ?off|permission|who (do i|should i) ask)\b", "approval approve"),
    (r"\b(grant|bursary|financial aid|funding)\b", "scholarship"),
    (r"\b(can'?t afford|cannot afford|hardship|struggling to pay|no money)\b", "fee waiver hardship"),
    (r"\b(apply|applying|sign up|register|join)\b", "application apply admission"),
    (r"\b(phone|call|email|reach|talk to someone|address)\b", "contact office email phone"),
    (r"\b(sick|ill|unwell|doctor)\b", "sick leave"),
    (r"\b(baby|maternity|paternity|newborn|pregnan\w*)\b", "parental leave"),
    (r"\b(laptop|desk|chair|equipment|internet|wifi)\b", "home office allowance equipment"),
    (r"\b(grades?|marks|average|score)\b", "gpa grade average"),
    (r"\b(foreign|overseas|abroad|visa)\b", "international students visa english"),
]
_COMPILED = [(re.compile(p, re.I), extra) for p, extra in SYNONYMS]


def expand(question: str) -> str:
    """The question plus the policy words for any everyday phrasing in it. Unchanged when nothing matches."""
    extra: list[str] = []
    for rx, words in _COMPILED:
        if rx.search(question):
            extra += [w for w in words.split() if w not in extra and w not in question.lower().split()]
    return f"{question} {' '.join(extra)}" if extra else question
