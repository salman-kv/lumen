"""Small talk: greetings, thanks, "who are you", "what can you do". Answered by the app (no retrieval, no LLM),
so "hi" never falls into the "not found in the knowledge base" guard and replies are instant.
Only whole messages that are small talk match; anything with real content goes through the normal pipeline."""
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


def _norm(text: str) -> str:
    t = re.sub(r"[^\w\s']", " ", text.lower())
    return re.sub(r"\s+", " ", t).strip()


def _topics(docs: list[str]) -> str:
    names = [re.sub(r"[_-]+", " ", d.rsplit(".", 1)[0]).strip() for d in docs[:6]]
    return ", ".join(names)


def reply(text: str, assistant: str, org: str, suggestions: list[str], docs: list[str]) -> str | None:
    t = _norm(text)
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
