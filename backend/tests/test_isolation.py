"""Multi-tenant isolation: the mandatory security tests."""
from app import retrieval
from app.db import Organization, SessionLocal

Q_SCHOLAR = "What is the GPA requirement for the Merit Scholarship?"
Q_LEAVE = "How many days of annual leave do employees get?"


def ask(client, token, q):
    return client.post("/api/ask", json={"token": token, "question": q})


def test_each_org_answers_from_its_own_documents(client, org_a, org_b):
    (_, ta), (_, tb) = org_a, org_b
    a = ask(client, ta, Q_SCHOLAR).json()
    assert a["status"] == "answered"
    assert {r["document"] for r in a["references"]} <= {"Scholarship_Rules.pdf", "Admissions_FAQ.pdf", "Fee_Policy.pdf"}
    b = ask(client, tb, Q_LEAVE).json()
    assert b["status"] == "answered"
    assert any(r["document"] == "Leave_Policy.pdf" for r in b["references"])


def test_org_b_cannot_get_org_a_knowledge(client, org_a, org_b):
    (_, ta), (_, tb) = org_a, org_b
    r = ask(client, tb, Q_SCHOLAR).json()  # Org A's content, asked on Org B's assistant
    assert r["status"] == "no_knowledge"
    assert r["references"] == []
    # the reply may repeat the visitor's own words, but must list only this organization's documents
    assert not any(x in r["answer"] for x in ("Scholarship Rules", "Fee Policy", "Admissions FAQ", "Northfield", "3.5"))
    assert "Leave Policy" in r["answer"] and "Expense Policy" in r["answer"]
    r = ask(client, ta, Q_LEAVE).json()  # and vice versa
    assert r["status"] == "no_knowledge"
    assert not any(x in r["answer"] for x in ("Leave Policy", "Expense Policy", "Remote Work", "Acme"))
    assert "Scholarship Rules" in r["answer"]


def test_retrieval_is_tenant_scoped_at_query_level(client, org_a, org_b):
    db = SessionLocal()
    try:
        oa = db.query(Organization).filter(Organization.email == "a@example.com").one()
        ob = db.query(Organization).filter(Organization.email == "b@example.com").one()
        hits_b = retrieval.retrieve(db, ob.id, "Merit Scholarship GPA second year sports scholarship")
        assert all(h.document in {"Leave_Policy.pdf", "Remote_Work_Policy.pdf", "Expense_Policy.pdf"} for h in hits_b)
        hits_a = retrieval.retrieve(db, oa.id, "annual leave carry over days")
        assert all(h.document in {"Scholarship_Rules.pdf", "Admissions_FAQ.pdf", "Fee_Policy.pdf"} for h in hits_a)
    finally:
        db.close()


def test_org_cannot_see_or_delete_other_orgs_documents(client, org_a, org_b):
    (ha, _), (hb, _) = org_a, org_b
    docs_a = client.get("/api/kb/documents", headers=ha).json()["documents"]
    docs_b = client.get("/api/kb/documents", headers=hb).json()["documents"]
    assert docs_a and docs_b
    assert not ({d["id"] for d in docs_a} & {d["id"] for d in docs_b})
    victim = docs_a[0]["id"]
    assert client.delete(f"/api/kb/documents/{victim}", headers=hb).status_code == 404
    assert client.get(f"/api/kb/documents/{victim}/file", headers=hb).status_code == 404
    assert client.put(f"/api/kb/documents/{victim}", headers=hb,
                      files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 404


def test_assistant_token_cannot_access_admin_api(client, org_a):
    _, ta = org_a
    for path in ("/api/kb/documents", "/api/assistant", "/api/usage", "/api/auth/me", "/api/kb/rules"):
        assert client.get(path, headers={"Authorization": f"Bearer {ta}"}).status_code == 401
        assert client.get(path).status_code == 401
    assert client.post("/api/assistant/regenerate", headers={"Authorization": f"Bearer {ta}"}).status_code == 401


def test_admin_jwt_is_not_an_assistant_token(client, org_a):
    ha, _ = org_a
    jwt_token = ha["Authorization"].split()[1]
    assert ask(client, jwt_token, Q_SCHOLAR).status_code == 401


def test_regenerating_token_invalidates_old_link(client):
    from tests.conftest import register
    h, old = register(client, "Regen Org", "regen@example.com")
    assert client.get(f"/api/public/assistant/{old}").status_code == 200
    new = client.post("/api/assistant/regenerate", headers=h).json()["token"]
    assert new != old
    assert client.get(f"/api/public/assistant/{old}").status_code == 404 or \
        client.get(f"/api/public/assistant/{old}").status_code == 401
    assert ask(client, old, "hello there").status_code == 401
    assert client.get(f"/api/public/assistant/{new}").status_code == 200


def test_public_config_exposes_no_secrets(client, org_a):
    _, ta = org_a
    cfg = client.get(f"/api/public/assistant/{ta}").json()
    assert set(cfg) == {"name", "org", "color", "welcome", "suggestions"}
