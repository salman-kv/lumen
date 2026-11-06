import io

import pytest
from reportlab.pdfgen import canvas

from app import rules
from app.engine import combine
from tests.conftest import SAMPLES, register, upload


def ask(client, token, q):
    r = client.post("/api/ask", json={"token": token, "question": q})
    assert r.status_code == 200, r.text
    return r.json()


def make_pdf(pages: int) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i in range(pages):
        c.drawString(72, 700, f"Page {i + 1} sample text about policies and rules.")
        c.showPage()
    c.save()
    return buf.getvalue()


# ----------------------------------------------------------------- upload validation & errors
def test_register_login_and_validation(client):
    r = client.post("/api/auth/register", json={"org_name": "X Org", "email": "bad", "password": "supersecret1"})
    assert r.status_code == 422
    h, _ = register(client, "Login Org", "login@example.com")
    assert client.post("/api/auth/register", json={"org_name": "Dup", "email": "login@example.com",
                                                   "password": "supersecret1"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "login@example.com", "password": "wrong-pass"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "login@example.com", "password": "supersecret1"})
    assert ok.status_code == 200 and ok.json()["org"]["name"] == "Login Org"


def test_upload_rejections_have_meaningful_messages(client):
    h, _ = register(client, "Limits Org", "limits@example.com")
    f = lambda name, data: client.post("/api/kb/documents", headers=h, files={"file": (name, data, "application/pdf")})
    assert "not a PDF" in f("notes.txt", b"hello").json()["detail"]
    assert "valid PDF" in f("fake.pdf", b"this is not a pdf at all").json()["detail"]
    r = f("long.pdf", make_pdf(21))
    assert r.status_code == 422 and "21 pages" in r.json()["detail"] and "20" in r.json()["detail"]
    r = f("big.pdf", b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 10))
    assert r.status_code == 413 and "10 MB" in r.json()["detail"]
    assert f("ok.pdf", make_pdf(20)).status_code == 201  # exactly 20 pages is allowed


def test_max_ten_documents(client):
    h, _ = register(client, "Full Org", "full@example.com")
    for i in range(10):
        r = client.post("/api/kb/documents", headers=h, files={"file": (f"d{i}.pdf", make_pdf(1), "application/pdf")})
        assert r.status_code == 201
    r = client.post("/api/kb/documents", headers=h, files={"file": ("d11.pdf", make_pdf(1), "application/pdf")})
    assert r.status_code == 409 and "10 documents" in r.json()["detail"]
    docs = client.get("/api/kb/documents", headers=h).json()["documents"]
    assert client.delete(f"/api/kb/documents/{docs[0]['id']}", headers=h).status_code == 204
    assert client.post("/api/kb/documents", headers=h,
                       files={"file": ("again.pdf", make_pdf(1), "application/pdf")}).status_code == 201


def test_replace_document(client):
    h, _ = register(client, "Replace Org", "replace@example.com")
    first = client.post("/api/kb/documents", headers=h, files={"file": ("a.pdf", make_pdf(2), "application/pdf")}).json()
    r = client.put(f"/api/kb/documents/{first['id']}", headers=h, files={"file": ("b.pdf", make_pdf(3), "application/pdf")})
    assert r.status_code == 200
    docs = client.get("/api/kb/documents", headers=h).json()["documents"]
    assert [d["filename"] for d in docs] == ["b.pdf"] and docs[0]["status"] == "ready"


def test_processed_document_has_pages_chunks_rules(client, org_a):
    ha, _ = org_a
    docs = {d["filename"]: d for d in client.get("/api/kb/documents", headers=ha).json()["documents"]}
    sr = docs["Scholarship_Rules.pdf"]
    assert sr["status"] == "ready" and sr["pages"] == 3 and sr["chunks"] > 0 and sr["rules"] >= 6


# ----------------------------------------------------------------- question handling
def test_empty_question_and_invalid_token(client, org_a):
    _, ta = org_a
    assert client.post("/api/ask", json={"token": ta, "question": "   "}).status_code == 422
    r = client.post("/api/ask", json={"token": "ast_nope", "question": "hi"})
    assert r.status_code == 401 and "invalid" in r.json()["detail"]


def test_unknown_topic_is_not_invented(client, org_a):
    _, ta = org_a
    r = ask(client, ta, "What time does the cafeteria close on Fridays?")
    assert r["status"] == "no_knowledge" and r["references"] == []


def test_multi_condition_not_eligible_due_to_sports_scholarship(client, org_a):
    _, ta = org_a
    r = ask(client, ta, "I'm a second-year student with a 3.6 GPA and I already have a sports scholarship. "
                        "Am I eligible for the merit scholarship?")
    d = r["decisions"]
    assert d["path"] == "decision" and d["benefit"] == "Merit Scholarship"
    assert d["verdict"] == "not_eligible"
    res = {b["field"]: b["result"] for b in d["booleans"]}
    assert res == {"year": "pass", "gpa": "pass", "holds_sports_scholarship": "fail"}
    assert any(r_["page"] == 1 and r_["document"] == "Scholarship_Rules.pdf" for r_ in r["references"])
    assert [s["id"] for s in r["steps"] if s["status"] == "done"][:3] == ["retrieve", "classify", "choose"]


def test_multi_condition_eligible(client, org_a):
    _, ta = org_a
    r = ask(client, ta, "I am a third year student with a GPA of 3.8 and no sports scholarship. "
                        "Can I get the merit scholarship?")
    assert r["decisions"]["verdict"] == "eligible"


def test_missing_facts_triggers_followup_not_a_guess(client, org_a):
    _, ta = org_a
    r = ask(client, ta, "Am I eligible for the merit scholarship if I have a 3.9 GPA?")
    assert r["status"] == "needs_info"
    assert set(r["decisions"]["missing"]) == {"Year of study", "Holds a Sports Scholarship"}


def test_acme_remote_work_decision(client, org_b):
    _, tb = org_b
    r = ask(client, tb, "I've worked here for 8 months and I have an approved remote work agreement. "
                        "Can I qualify for remote work 2 days per week?")
    assert r["decisions"]["verdict"] == "eligible"
    r = ask(client, tb, "I joined 3 months ago and have an approved remote work agreement. Do I qualify for "
                        "remote work?")
    assert r["decisions"]["verdict"] == "not_eligible"


def test_usage_counts(client, org_a):
    ha, ta = org_a
    u = client.get("/api/usage", headers=ha).json()
    assert u["asked"] >= 1 and u["asked"] == u["answered"] + u["unable"]


# ----------------------------------------------------------------- units
class R:  # minimal rule stand-in
    def __init__(self, field, operator, value):
        self.field, self.operator, self.value = field, operator, value


@pytest.mark.parametrize("rule,facts,expected", [
    (R("gpa", ">=", "3.5"), {"gpa": 3.5}, "pass"), (R("gpa", ">=", "3.5"), {"gpa": 3.49}, "fail"),
    (R("gpa", ">=", "3.5"), {}, "unknown"), (R("x", "is_false", "false"), {"x": True}, "fail"),
    (R("x", "is_false", "false"), {"x": False}, "pass"), (R("d", "<=", "3"), {"d": 4}, "fail"),
])
def test_boolean_evaluator(rule, facts, expected):
    assert rules.evaluate(rule, facts)[0] == expected


def test_combiner():
    assert combine([{"result": "pass", "label": "a"}, {"result": "fail", "label": "b"}])[0] == "not_eligible"
    assert combine([{"result": "pass", "label": "a"}, {"result": "unknown", "label": "b"}]) == ("need_info", ["b"])
    assert combine([{"result": "pass", "label": "a"}])[0] == "eligible"
    # a hard failure wins even when other facts are still missing
    assert combine([{"result": "unknown", "label": "a"}, {"result": "fail", "label": "b"}])[0] == "not_eligible"


# ----------------------------------------------------------------- LLM fact grounding (regression)
def test_llm_hallucinated_facts_are_dropped():
    from app.engine import ground_facts
    q = "Can I work remotely?"  # the user stated nothing
    assert ground_facts(q, {"tenure_months": 0, "days_per_week": 3, "has_approved_remote_work_agreement": False}) == {}


def test_llm_facts_kept_only_when_verifiable():
    from app.engine import ground_facts
    q = "I have worked here for two years and want 3 days remotely"
    got = ground_facts(q, {"tenure_months": 24, "days_per_week": 3, "gpa": 3.9, "holds_x": True})
    assert got == {"tenure_months": 24, "days_per_week": 3}  # 24 = 2 years, 3 appears, 3.9 invented, bool dropped


def test_question_with_no_facts_asks_for_information_not_a_verdict(client, org_b, monkeypatch):
    from app import classifier
    monkeypatch.setattr(classifier, "classify", lambda q: ("eligibility", 0.9))  # hash embeddings cannot classify
    _, tb = org_b
    r = ask(client, tb, "Can I work remotely?")
    assert r["status"] == "needs_info" and r["decisions"]["verdict"] == "need_info"
    assert r["decisions"]["facts"] == {}


def test_follow_up_negation_not_hidden_by_earlier_question():
    from app.engine import pattern_facts
    fields = {"holds_sports_scholarship": "holds a sports scholarship"}
    q = "Am I eligible for the Merit Scholarship? I am a third year student with 3.8 GPA and no sports scholarship"
    assert pattern_facts(q, fields)["holds_sports_scholarship"] is False


def test_follow_up_answer_uses_previous_question(client, org_a):
    _, token = org_a
    r = client.post("/api/ask", json={"token": token, "question": "I am a third year student with 3.8 GPA and no sports scholarship",
                                      "context": "Am I eligible for the Merit Scholarship?"})
    assert r.status_code == 200
    assert r.json()["status"] == "answered" and r.json()["decisions"]["verdict"] == "eligible"


@pytest.mark.parametrize("msg", ["hi", "Hello!", "hey there", "thanks", "what can you do?", "who are you", "Good morning",
                                 "helo", "hellooo", "thankyou", "whats up"])
def test_small_talk_is_answered_without_search(client, org_a, msg):
    _, token = org_a
    r = ask(client, token, msg)
    assert r["status"] == "answered" and r["question_type"]["label"] == "small_talk"
    assert r["references"] == [] and "couldn't find" not in r["answer"]


def test_real_questions_are_not_small_talk(client, org_a):
    _, token = org_a
    r = ask(client, token, "hi what is the refund policy")
    assert r["question_type"]["label"] != "small_talk"


# ---- error handling: the failure modes the assignment lists (LLM down, decision model down, processing failure)

ELIGIBILITY_Q = "I'm a second-year student with a 3.6 GPA and I already have a sports scholarship. Am I eligible for the merit scholarship?"


def test_llm_failure_degrades_to_a_grounded_answer(client, org_a, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")  # nothing listens here
    _, token = org_a
    r = ask(client, token, ELIGIBILITY_Q)
    assert r["status"] == "answered" and r["degraded"] is True
    assert r["decisions"]["verdict"] == "not_eligible"  # the decision does not need the LLM
    assert r["answer"] and r["references"]


def test_decision_model_failure_gives_a_clear_error(client, org_a, monkeypatch):
    from app import engine

    async def boom(*a, **k):
        raise RuntimeError("model crashed")
    monkeypatch.setattr(engine, "decide_boolean", boom)
    _, token = org_a
    r = ask(client, token, ELIGIBILITY_Q)
    assert r["status"] == "error" and "trouble" in r["answer"]


def test_document_processing_failure_is_reported_not_crashed(client, monkeypatch):
    from app import models_s1
    h, _ = register(client, "Failing Org", "failing@example.com")

    def boom(_):
        raise RuntimeError("embedding model crashed")
    monkeypatch.setattr(models_s1, "embed", boom)
    r = client.post("/api/kb/documents", headers=h, files={"file": ("a.pdf", make_pdf(1), "application/pdf")})
    assert r.status_code == 201
    doc = client.get("/api/kb/documents", headers=h).json()["documents"][0]
    assert doc["status"] == "failed" and "couldn't process" in doc["error"]


def test_documents_are_not_publicly_downloadable(client, org_a):
    (h, token) = org_a
    doc_id = client.get("/api/kb/documents", headers=h).json()["documents"][0]["id"]
    assert client.get(f"/api/kb/documents/{doc_id}/file").status_code == 401           # no login
    assert client.get(f"/api/kb/documents/{doc_id}/file",
                      headers={"Authorization": f"Bearer {token}"}).status_code == 401  # assistant token
    assert client.get(f"/api/kb/documents/{doc_id}/file", headers=h).status_code == 200
