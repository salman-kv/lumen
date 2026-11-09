"""Small talk and conversation scenarios: greetings, thanks, "who are you", "can you help me", "what do you know",
"this is not helpful", "what?". Answered by the app (no retrieval, no LLM), so a casual message never falls into the
"not found in the knowledge base" guard and replies are instant.

Only whole messages that are conversation match; anything with real content goes through the normal pipeline.
Replies stay short and plain. The clickable starter questions under the reply (added by the engine) are the "next step"."""
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
LAUGH = re.compile(r"^(lol+|lmao|rofl|haha+|hehe+|hah)$")
IDENTITY = re.compile(r"^(who (made|built|created|developed|owns|trained) you|who is your (creator|developer|owner)|"
                      r"are you (a |an )?(bot|robot|ai|human|real|person|machine|chatgpt|gpt|chat bot)( or (a )?(human|bot|person))?|"
                      r"is this (a |an )?(bot|ai|human|real person|robot|machine))$")

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


def is_closing(text: str) -> bool:
    """Thanks, goodbye, "ok", "lol": the visitor is done or reacting, so no suggestion chips are offered."""
    t = _norm(text)
    t = _fix_typos(t) if len(t.split()) <= 3 else t
    return bool(THANKS.match(t) or BYE.match(t) or ACK.match(t) or LAUGH.match(t))


def reply(text: str, assistant: str, org: str, suggestions: list[str], docs: list[str]) -> str | None:
    t = _norm(text)
    t = _fix_typos(t) if len(t.split()) <= 3 else t
    if not t or len(t.split()) > 6:
        return None
    if GREETING.match(t) or HOW_ARE_YOU.match(t):
        lead = "Hello!" if not t.startswith("how") else "I'm doing well, thanks for asking!"
        return (f"{lead} I'm {assistant}, the assistant for {org}. I can answer questions about "
                f"{_topics(docs) or 'our policies'} and show you the page each answer came from. What would you like to know?")
    if IDENTITY.match(t):
        return (f"I'm {assistant}, an AI assistant for {org}, not a person. I answer from {org}'s own documents and "
                f"show the page I used, so you can check it. If you need a person, please contact {org} directly.")
    if WHO.match(t):
        return (f"I'm {assistant}, the assistant for {org}. I only answer from {org}'s own documents, "
                f"and I show the page I used, so you can check it.")
    if HELP.match(t):
        return (f"I can answer questions from {org}'s documents ({_topics(docs) or 'policies'}), explain rules and "
                f"procedures, compare options, and check whether you qualify for something when you tell me your "
                f"details. Pick a suggestion below or just type your question.")
    if THANKS.match(t):
        return "You're welcome! Ask me anything else about our policies whenever you like."
    if BYE.match(t):
        return "Goodbye! Come back any time you have a question."
    if ACK.match(t):
        return "Great. What else would you like to know?"
    if LAUGH.match(t):
        return "Haha! Is there anything I can look up for you?"
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
HELP_OFFER = re.compile(
    r"^((can|could|will|would) you )?(please )?help( me)?( please)?$|^(i )?(need|want|require) (some |your )?help( please)?"
    r"( with something)?$|^i have (a|some) (quick )?(question|questions|doubt|doubts|query)( for you)?$|"
    r"^(can|could|may) i ask (you )?(something|a question|a quick question)$|^(i )?(need|want) to (ask|know) (something|a question)$|"
    r"^(i )?(have a )?(problem|issue)$")
OVERVIEW_PHRASE = re.compile(r"^(what('s| is| are) (this|these|here|all this)( all)? (about|for)|what('s| is) (this|here)|"
                             r"what can (i|we) (do|get|find)( here)?|what (do|can) you (offer|know about)( here)?)$")
OVERVIEW_TRIGGER = {"list", "show", "features", "feature", "topics", "topic", "summary", "summarize", "overview", "everything",
                    "know", "offer", "offers", "cover", "covers", "capabilities", "available", "provide", "benefits",
                    "policies"}
# "I am new here, what should I know?": a newcomer wants a starting point
NEWCOMER = re.compile(r"\b(i am|i'?m|im) (new|a new)\b.*\b(what|where|how)\b.*\b(know|start|begin|do|need)\b|"
                      r"^(where|how) (do|should) i (start|begin)$|^(getting started|get started)$")
OVERVIEW_WORDS = set("what which who list show tell give me us you we i do does can could would please all everything every "
                     "features feature topics topic capabilities summary summarize overview know have has about this that these "
                     "those are is the a an of for and with there available offer offers cover covers things stuff else more "
                     "other provide your our policies policy benefits rules information info documents".split())
ANYTHING_ELSE = re.compile(r"^(is that all|that'?s all|anything else|is there anything else|any other( info| information| details)?|"
                           r"nothing else|that'?s it)$")
FRUSTRATED = re.compile(r"(not helpful|isn'?t helpful|unhelpful|you('re| are| r) wrong|that('s| is) (wrong|not right|incorrect|"
                        r"not what i (asked|meant|wanted))|not what i (asked|meant|wanted)|wrong answer|bad answer|doesn'?t help|"
                        r"didn'?t help|no help|you don'?t understand|not working|doesn'?t work|that doesn'?t answer)")
# "what?", "huh", "why", "really?", "I don't understand": with an earlier answer the server explains it again more simply
CLARIFY = re.compile(r"^(what|huh|why|really|seriously|how so|how come|sorry what|pardon|come again|i don'?t (understand|get it)|"
                     r"dont (understand|get it)|i do not understand|i'?m confused|confused|can you explain( that)?"
                     r"( again| more| simply| better)?|explain( that)?( again| more| simply| better)?|say that again|"
                     r"repeat( that)?|simpler|in simple (words|terms)|what do you mean|i didn'?t get (that|it))$")
# an action the assistant cannot perform: only used when the knowledge base has no answer for the message
ACTION = re.compile(r"^(please )?(can|could|would|will) you |^(please )?(generate|create|make|write|draft|compose|translate|"
                    r"download|export|print|draw|code|email|send|schedule|remind|search the web|google|summari[sz]e the "
                    r"internet|play|sing|tell me a joke)\b")


def is_overview(t: str) -> bool:
    """"what all the features we have", "list everything", "give me a summary": nothing specific is asked, so show the menu
    instead of searching. A message that names anything specific (a product, a policy) is never an overview request."""
    words = t.split()
    return bool(OVERVIEW_PHRASE.match(t)) or (
        1 <= len(words) <= 10 and any(w in OVERVIEW_TRIGGER for w in words) and all(w in OVERVIEW_WORDS for w in words))


def _alpha(text: str) -> str:
    return re.sub(r"[^A-Za-zÀ-ɏͰ-῿぀-鿿가-힯]", "", text)


def route(text: str, assistant: str, org: str, suggestions: list[str], docs: list[str],
          menu=None) -> tuple[str, str, bool] | None:
    """Return (intent, answer, counts_as_answered) for messages the app can handle itself, else None.
    `menu` is a callable returning the "what each document covers" list."""
    raw = text.strip()
    t = _norm(raw)

    def what_i_cover() -> str:
        m = menu() if menu else ""
        return m or "\n".join("• " + n for n in _topics(docs).split(", ") if n)

    if INJECTION.search(t):
        return ("blocked", f"I can't change how I work or share my instructions. I'm {assistant}, and I only answer "
                           f"questions from {org}'s documents. Pick a suggestion below or ask me about a policy.", False)
    letters = _alpha(raw)
    if not letters:
        return ("unclear", "I didn't catch that. Could you type your question in words? You can also pick a suggestion below.",
                False)
    if sum(1 for c in letters if ord(c) > 0x24F) > len(letters) / 2:
        return ("language", "I can only answer in English at the moment. Please ask your question in English, "
                            "or pick a suggestion below.", False)
    words = t.split()
    small = reply(text, assistant, org, suggestions, docs)
    if small:
        return ("small_talk", small, True)
    if len(words) <= 2 and not re.search(r"[aeiouy]", t) or re.fullmatch(r"(.)\1{3,}", t.replace(" ", "")):
        return ("unclear", "I didn't understand that. Could you rephrase your question? You can also pick a suggestion below.",
                False)
    if len(words) == 1 and len(t) >= 5 and not re.search(r"[aeiouy]", t[1:]):
        return ("unclear", "I didn't understand that. Could you rephrase your question? You can also pick a suggestion below.",
                False)
    if HUMAN.search(t):
        return ("human", f"I'm an automated assistant, so I can't transfer you, but a person at {org} can help. "
                         f"Please contact {org} directly. I'll note that you asked for human help.", False)
    if ABUSE.search(t) and len(words) <= 8:
        return ("abuse", "I'm sorry this has been frustrating. I'll do my best to help: ask me about "
                         f"{_topics(docs) or 'our policies'} and I'll point you to the exact page.", True)
    if HELP_OFFER.match(t):
        return ("help", "Of course, I'm happy to help! What would you like to know? Here's what I can help with:\n"
                        + what_i_cover(), True)
    if is_overview(t):
        return ("overview", f"Here's what I can help with at {org}:\n{what_i_cover()}\n\nAsk me about any of these in your "
                            "own words, or pick a suggestion below.", True)
    if NEWCOMER.search(t):
        return ("overview", f"Welcome to {org}! A good place to start is one of these topics:\n{what_i_cover()}\n\n"
                            "Tell me about your situation, for example your year or role, and I can check what applies to you.",
                True)
    if ANYTHING_ELSE.match(t):
        return ("overview", "That's everything I found about that. I can also help with:\n" + what_i_cover(), True)
    if len(words) <= 9 and FRUSTRATED.search(t):
        return ("frustrated", "I'm sorry that wasn't what you needed. Could you tell me a bit more, or try asking it a "
                              "different way? Here's what I can help with:\n" + what_i_cover(), False)
    if CLARIFY.match(t) or (VAGUE.match(t) and menu):
        return ("unclear", "Could you tell me what you'd like to know more about? I'm not sure yet what you're referring "
                           "to. Here's what I can help with:\n" + what_i_cover(), False)
    if YESNO.match(t):
        return ("bare_reply", "Could you tell me a little more about what you'd like to know? You can also pick a "
                              "suggestion below.", True)
    return None


def out_of_scope_message(text: str, assistant: str, org: str, menu: str = "") -> str | None:
    """For a message the knowledge base can't answer: if it is a request for an action, say so clearly."""
    if ACTION.search(_norm(text)):
        return (f"I can't do that. I'm {assistant}, and I can only answer questions from {org}'s documents "
                f"(and show you the page I used)."
                + (f" Here's what I can help with:\n{menu}" if menu
                   else " Try asking about a policy, a deadline or whether you qualify for something."))
    return None
