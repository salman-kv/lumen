# Assignment requirements vs. what was built

Source: `AI_Knowledge_Decision_Assistant_Assignment.pdf` (20 sections). Status: **Done**, **Partial** (works, with a stated gap), **Yours** (needs the submitter).

## Product and accounts (sections 1, 2, 12)
| Requirement | Status | Where |
|---|---|---|
| Multi-tenant SaaS, isolated KB and assistant per org | Done | every table row has `org_id`; every query filters by it; the org is derived server-side from the token (`db.py`, `retrieval.py`, `security.py`) |
| Create account, log in, dashboard, logout | Done | `/api/auth/*`, `AuthPage.jsx`, `Dashboard.jsx` |
| Manage KB, generate/regenerate assistant URL, embed code | Done | Knowledge and Assistant tabs, `/api/assistant`, `/api/assistant/regenerate` |
| Usage counts: asked, answered, unable to answer | Done | Usage tab, `/api/usage` |

## Knowledge base (section 3)
| Requirement | Status | Where |
|---|---|---|
| Max 10 PDFs, 20 pages, 10 MB; meaningful errors | Done | `pdfproc.py`, `config.py`; `test_upload_rejections_have_meaningful_messages`, `test_max_ten_documents` |
| View, delete, replace documents with basic info | Done | Knowledge tab, `PUT /api/kb/documents/{id}` |
| Processing keeps source document and page | Done | page-bound chunks (`pdfproc.chunk_page`), hybrid BM25 + embeddings + rerank (`retrieval.py`) |
| Unique, secret assistant token; works without login | Done | `ast_` + random token, not a JWT, exposes nothing; `/a/{token}` |
| iframe or JS embed, code on dashboard, demo page | Done | `public/embed.js` (bubble), `public/demo.html` (`&mode=inline` for iframe) |

## Visitor experience and pipeline (sections 4, 5, 11)
| Requirement | Status | Where |
|---|---|---|
| Chat UI, no account, answers with page references | Done | `ChatPanel.jsx`, source chips show file and page, click for the snippet |
| Token -> org -> retrieval -> understanding -> decisions -> combine -> answer | Done | `engine.run` (SSE steps shown live as "How I decided") |
| `POST /api/ask` with token and question | Done | `/api/ask` and streaming `/api/ask/stream` |
| Greetings and small talk do not hit the "not found" guard | Done | `smalltalk.py` (added after testing) |
| Answering a "need more info" reply uses the earlier question | Done | `context` field, `ChatPanel.jsx` (added after testing) |

## AI architecture (sections 6, 7, 8, 20)
| Requirement | Status | Where |
|---|---|---|
| LLM understands the question | Done | `llm_facts` extracts the user's facts; grounded against the question text so a small model cannot invent values |
| Independent structured decisions evaluated separately, in parallel | Done | one Boolean check per rule card plus the evidence score, run with `asyncio.gather` |
| At least two decision types | Done, all four | Classification (logistic regression on embeddings), Choice (policy chooser), Boolean (rule evaluators), Score (cross-encoder) |
| Decisions combined into one result | Done | `combine()` in application logic (AND of conditions, with "need info" handling) |
| LLM turns the result into a natural answer | Done | `DECISION_SYSTEM` prompt; app-written reasons; `contradicts()` guard; deterministic fallback |
| Not a single LLM prompt | Done | three layers: LLM for language, System 1 models for decisions, app logic for routing and combining |

Honest notes for the reviewers:
- "System 1" here means small, fast, specialised components: sentence-embedding classifier, policy chooser, cross-encoder, and typed rule evaluators. The Boolean evaluators are deterministic comparators over rule cards mined from the PDFs, not a trained network. That is a deliberate choice (auditable, never hallucinates) and the README explains it.
- The assignment names example System 1 tools; it also says no specific framework is required, so none of those were used.
- Rule mining is pattern-based. An LLM rule-proposal pass exists but is off by default because a 3B local model produced noisy rules.
- Decisions combine with AND only (no OR / weights).

## Grounding and coverage (sections 9, 10)
| Requirement | Status | Where |
|---|---|---|
| No invented answers; clear "not in knowledge base" | Done | support threshold plus policy-choice guard; instant refusal, no references |
| Question types: direct, policy, procedural, multi-condition, comparison, no-answer | Done | `sample_data/test_questions.json` (19 questions), 19/19 pass live |

## Security (section 11)
| Requirement | Status | Where |
|---|---|---|
| Admin APIs need auth; assistant token cannot reach them | Done | `test_assistant_token_cannot_access_admin_api`, `test_admin_jwt_is_not_an_assistant_token` |
| Tokens validated server-side; regenerate invalidates old link | Done | `test_regenerating_token_invalidates_old_link` |
| Private documents not public | Done | uploads are not served statically; download needs the admin JWT (`test_documents_are_not_publicly_downloadable`) |
| Cross-org retrieval impossible, explicitly tested | Done | `tests/test_isolation.py` (8 tests), plus eval probes #12 and #17 |

## Error handling (section 13)
| Failure | Status | Test |
|---|---|---|
| Invalid PDF, size, pages, document count | Done | `test_upload_rejections_have_meaningful_messages`, `test_max_ten_documents` |
| Invalid token, empty question | Done | `test_empty_question_and_invalid_token` |
| No relevant knowledge | Done | `test_unknown_topic_is_not_invented` |
| LLM failure | Done | `test_llm_failure_degrades_to_a_grounded_answer` |
| Decision-model failure | Done | `test_decision_model_failure_gives_a_clear_error` |
| Document-processing failure | Done | `test_document_processing_failure_is_reported_not_crashed` |

## Submission (sections 15 to 18)
| Item | Status | Where |
|---|---|---|
| Source code, `.env.example`, schema setup, no secrets | Done | `backend/.env.example`; schema created on startup by `init_db`; `.gitignore` excludes `.env`, DB, uploads |
| README with setup, architecture diagram, KB, AI architecture, security, API, limitations | Done | `README.md` |
| Test data: 2 orgs, 2 to 3 PDFs each, 10+ questions, 2+ multi-condition, 1+ multi-decision, 1+ no-answer | Done | `sample_data/` (2 orgs, 3 PDFs each, 19 questions, 5 multi-condition, 3 with three decisions, 5 with no answer) |
| Working end-to-end app | Done | verified locally and in Docker with the Ollama container |
| Deployed app | Not done | optional |
| GitHub repository | Yours | repo is committed locally; add a remote and push |
| **Demo video, 8 to 15 min** | **Yours** | script in `docs/DEMO_SCRIPT.md`; mandatory, needs your voice |

## Conversation improvements (added after review)
| Feature | Where |
|---|---|
| Starter questions: the owner's own (up to 6) plus ones generated from the documents, shown before the visitor types | `suggest.py`, `/api/public/assistant/{token}`, `ChatPanel.jsx` |
| Follow-up chips under every answer ("Tell me more details", related questions); none while the assistant waits for the visitor's facts | `suggest.followups`, `final.followups` |
| Conversation history (last 4 turns) is sent with each question, so "what if I withdraw in week 3?" is understood from the earlier answer; history is context only, never a source of facts | `AskIn.history`, `engine._history_block` |
| "Tell me more / explain / give an example" retrieves more passages and asks for a fuller, still fully grounded answer | `DETAIL_SYSTEM`, `main.DETAIL` |
| Full question history (not just the latest few): every question with its answer and sources, search, filter by outcome, paging, expandable rows, CSV download; private to the organization | `GET /api/usage/history`, `/api/usage/history.csv`, `Usage.jsx` |
