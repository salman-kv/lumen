"""Small talk: greetings, thanks, "who are you", "what can you do". Answered by the app (no retrieval, no LLM),
so "hi" never falls into the "not found in the knowledge base" guard and replies are instant.
Only whole messages that are small talk match; anything with real content goes through the normal pipeline."""
import difflib
import re

GREETING = re.compile(r"^(hi+|hello+|hey+|hiya|howdy|yo|hola|namaste|greetings|good (morning|afternoon|evening|day)|"
                      r"sup|what'?s up|hi there|hello there|hey there)( (there|team|assistant|bot|everyone))?$")
HOW_ARE_YOU = re.compile(r"^(hi |hello |hey )?how are you( doing| today)?$|^how'?s it going$")
THANKS = re.compile(r"^(thanks|thank you|thank u|thx|ty|cheers|great thanks|ok thanks|okay thanks|many thanks|"
                    r"thanks a lot|thank you so much|got it thanks|perfect thanks)$")
BYE = re.compile(r"^(bye|goodbye|good bye|see you|see ya|cya|take care|good night)$")
WHO = re.compile(r"^(who|what) are you$|^what is your name$|^what'?s your name$|^who is this$|^introduce yourself$")
HELP = re.compile(r"^(help|help me|what can you do|what can i ask( you)?|what do you do|how can you help( me)?|"
                  r"how do you work|how does this work|what should i ask|what can you help (me )?with)$")
ACK = re.compile(r"^(ok|okay|k|cool|nice|great|awesome|alright|fine|sure|good|got it|i see|understood)$")


VOCAB = ["hi", "hello", "hey", "hiya", "howdy", "hola", "greetings", "morning", "afternoon", "evening", "thanks", "thank", "thx",
         "bye", "goodbye", "help", "who", "what", "are", "you", "good", "there", "please", "whats", "sup", "thank"]


def _fix_typos(t: str) -> str:
    """"helo" -> "hello", "thankyou" -> "thank you": correct near-misses of small-talk words (short messages only)."""
    words = t.split()
    if len(words) > 3:
        return t
    out = []
    for w in words:
        m = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.8) if len(w) >= 3 and w not in VOCAB else []
        out.append(m[0] if m else w)
    return " ".join(out).replace("thankyou", "thank you")


def _norm(text: str) -> str:
    t = re.sub(r"[^\w\s']", " ", text.lower())
    return re.sub(r"\s+", " ", t).strip()


def _topics(docs: list[str]) -> str:
    names = [re.sub(r"[_-]+", " ", d.rsplit(".", 1)[0]).strip() for d in docs[:6]]
    return ", ".join(names)


def reply(text: str, assistant: str, org: str, suggestions: list[str], docs: list[str]) -> str | None:
    t = _norm(text)
    t = _fix_typos(t) if len(t.split()) <= 3 else t
    if not t or len(t.split()) > 6:
        return None
    ask = ""
    if suggestions:
        ask = " You could try: " + " ".join(f"“{s}”" for s in suggestions[:3])
    if GREETING.match(t) or HOW_ARE_YOU.match(t):
        lead = "Hello!" if not t.startswith("how") else "I'm doing well, thanks for asking!"
        return (f"{lead} I'm {assistant}, the assistant for {org}. Ask me about {_topics(docs) or 'our policies'}, "
                f"and I'll answer from our documents and show you where the answer came from.{ask}")
    if WHO.match(t):
        return (f"I'm {assistant}, the assistant for {org}. I only answer from {org}'s own documents, "
                f"and I show the page I used, so you can check it.{ask}")
    if HELP.match(t):
        return (f"I can answer questions from {org}'s documents ({_topics(docs) or 'policies'}), explain rules and "
                f"procedures, compare options, and check whether you qualify for something when you tell me your "
                f"details.{ask}")
    if THANKS.match(t):
        return "You're welcome! Ask me anything else about our policies whenever you like."
    if BYE.match(t):
        return "Goodbye! Come back any time you have a question."
    if ACK.match(t):
        return "Great. What else would you like to know?"
    return None


# ---- other conversation scenarios, handled before any search or LLM call -------------------------------------

INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above|earlier|your) (instructions|rules|prompt)|disregard (all |the |your )?"
    r"(instructions|rules|prompt)|(reveal|show|print|repeat|tell me) (me )?(your |the )?(system |hidden |initial )?"
    r"(prompt|instructions)|system prompt|you are now |pretend (to be|you are)|act as (a |an )?(?!student|employee)|"
    r"jailbreak|developer mode|\bdan mode\b|forget (everything|your (rules|instructions))|override (your|the) (rules|instructions)")
HUMAN = re.compile(r"\b(talk|speak|chat|connect|transfer|escalate)\b.*\b(human|person|agent|representative|someone|staff|"
                   r"real person|support)\b|\b(human|live) (agent|support|help)\b|\bcustomer (service|support)\b")
ABUSE = re.compile(r"\b(fuck|fucking|shit|bitch|bastard|asshole|idiot|stupid|dumb|useless|crap)\b")
VAGUE = re.compile(r"^(i (want|need|would like) to (know|learn|understand)|tell me|explain|more|what about|how about|and)"
                   r"( more)?( about| on)?( (it|that|this|them|those|these|the same|more|everything))?$")
YESNO = re.compile(r"^(yes|yeah|yep|yup|y|no|nope|nah|n|maybe|not sure|idk|i don'?t know)$")
# an action the assistant cannot perform: only used when the knowledge base has no answer for the message
ACTION = re.compile(r"^(please )?(can|could|would|will) you |^(please )?(generate|create|make|write|draft|compose|translate|"
                    r"download|export|print|draw|code|email|send|schedule|remind|search the web|google|summari[sz]e the "
                    r"internet|play|sing|tell me a joke)\b")


def _alpha(text: str) -> str:
    return re.sub(r"[^A-Za-zÀ-ɏͰ-῿぀-鿿가-힯]", "", text)


def route(text: str, assistant: str, org: str, suggestions: list[str], docs: list[str],
          menu=None) -> tuple[str, str, bool] | None:
    """Return (intent, answer, counts_as_answered) for messages the app can handle itself, else None."""
    raw = text.strip()
    t = _norm(raw)
    ask = ""
    if suggestions:
        ask = " You could try: " + " ".join(f"“{s}”" for s in suggestions[:3])
    if INJECTION.search(t):
        return ("blocked", f"I can't change how I work or share my instructions. I'm {assistant}, and I only answer "
                           f"questions from {org}'s documents.{ask}", False)
    letters = _alpha(raw)
    if not letters:
        return ("unclear", f"I didn't catch that. Could you type your question in words?{ask}", False)
    if sum(1 for c in letters if ord(c) > 0x24F) > len(letters) / 2:
        return ("language", f"I can only answer in English at the moment. Please ask your question in English.{ask}",
                False)
    words = t.split()
    small = reply(text, assistant, org, suggestions, docs)
    if small:
        return ("small_talk", small, True)
    if len(words) <= 2 and not re.search(r"[aeiouy]", t) or re.fullmatch(r"(.)\1{3,}", t.replace(" ", "")):
        return ("unclear", f"I didn't understand that. Could you rephrase your question?{ask}", False)
    if len(words) == 1 and len(t) >= 5 and not re.search(r"[aeiouy]", t[1:]):
        return ("unclear", f"I didn't understand that. Could you rephrase your question?{ask}", False)
    if HUMAN.search(t):
        return ("human", f"I'm an automated assistant, so I can't transfer you, but a person at {org} can help. "
                         f"Please contact {org} directly. I'll note that you asked for human help.", False)
    if ABUSE.search(t) and len(words) <= 8:
        return ("abuse", f"I'm sorry this has been frustrating. I'll do my best to help: ask me about "
                         f"{_topics(docs) or 'our policies'} and I'll point you to the exact page.{ask}", True)
    if VAGUE.match(t) and menu:
        return ("unclear", "Could you tell me what you'd like to know more about? I'm not sure yet what "
                           "you're referring to. Here's what I can help with:\n" + menu(), False)
    if YESNO.match(t):
        return ("bare_reply", f"Could you tell me a little more about what you'd like to know?{ask}", True)
    return None


def out_of_scope_message(text: str, assistant: str, org: str, menu: str = "") -> str | None:
    """For a message the knowledge base can't answer: if it is a request for an action, say so clearly."""
    if ACTION.search(_norm(text)):
        return (f"I can't do that. I'm {assistant}, and I can only answer questions from {org}'s documents "
                f"(and show you the page I used)."
                + (f" Here's what I can help with:\n{menu}" if menu
                   else " Try asking about a policy, a deadline or whether you qualify for something."))
    return None
