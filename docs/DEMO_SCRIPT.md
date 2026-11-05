# Demo video script (target 11 to 12 minutes)

Record the screen with voice narration. Do not read private reasoning aloud: explain architecture and data flow.
Before recording: `ollama` running, server up, `seed_and_eval.py --seed-only` already run, demo accounts logged in
two browser profiles (A = Northfield, B = Acme). Open the README architecture diagram in a tab.

## 0:00 Intro and the idea (1 min)
- "Organizations upload PDFs and get an embeddable assistant. The point: an LLM should not do everything."
- Show the README diagram. Three layers: **LLM** for language, **System 1 models** for decisions, **application logic** to combine them.

## 1:00 Product walkthrough (4 min)
1. **Register** a brand-new organization on the landing page (show inline validation and password strength). Land on the dashboard onboarding.
2. **Knowledge**: drag in `Scholarship_Rules.pdf`. Point out the live stages (Extracting, Indexing, Reading rules), then the confetti.
3. Show **limits**: try a `.txt` file and a 21-page PDF to show the meaningful errors; show the 3/10 ring.
4. Open **"What the assistant learned"**: rule cards with page numbers (`GPA >= 3.5, p.1`).
5. **Assistant** tab: change color and greeting, show the live preview update; copy the **link** and the **embed code**; click **Regenerate** to show the confirm dialog (cancel it).
6. **Embed**: open `/demo.html?token=...`, click the chat bubble (the external site). Mention `&mode=inline` for the iframe variant.

## 5:00 Questions and grounding (2 min)
Ask in the widget, expanding "How I decided" once:
- Direct: "What is the application deadline for undergraduate admissions?" (cites Admissions_FAQ.pdf p.1; click the source chip to show the snippet)
- Procedural: "How do I apply for a scholarship and appeal a decision?"
- Comparison: "What is the difference between the Merit Scholarship and the Sports Scholarship?"
- **No answer**: "Does the university offer a PhD in astrophysics?" -> clear refusal, no references, instant (no LLM call). Mention the Usage tab counts it as "unable to answer".

## 7:00 AI decision flow (3 min) (the most important part)
Ask: *"I'm a second-year student with a 3.6 GPA and I already have a sports scholarship. Am I eligible for the merit scholarship?"*
Walk the animated pipeline:
1. **Search** (System 1): hybrid BM25 + embeddings, reranked, only this organization's chunks.
2. **Classify** (System 1): logistic regression on embeddings says "eligibility".
3. **Choose policy** (System 1): Merit Scholarship.
4. **Understand facts** (LLM + patterns): year=2, GPA=3.6, holds sports scholarship. Explain facts are grounded: invented values are discarded.
5. **Check conditions** (System 1, parallel): three Boolean checks plus the evidence score at the same time. Two met, one failed.
6. **Combine** (application logic): AND of all conditions gives "Not eligible".
7. **Answer** (LLM): phrases app-written reasons; a guard prevents contradicting the verdict.
Then ask the same without facts ("Am I eligible for the merit scholarship?") to show it **asks for the missing facts instead of guessing**. Finally the passing case: third-year, 3.8 GPA, no sports scholarship.

## 10:00 Multi-tenant isolation (1.5 min)
- Switch to Acme (profile B): different documents, different assistant URL and color.
- Ask Acme's assistant the scholarship question -> "couldn't find anything". Ask Northfield's assistant about annual leave -> same.
- Run `uv run pytest tests/test_isolation.py -v` on screen and read the test names (cross-tenant retrieval, assistant token cannot reach admin API, regenerate invalidates old link).
- Run `seed_and_eval.py --eval-only` (or show the saved results): 19/19.

## 11:30 Wrap-up (30 s)
Limits and next steps: rule mining is pattern-based (LLM proposals are gated), AND-only combination, SQLite for the MVP; production would add Postgres + pgvector, a job queue and review of rule cards.
