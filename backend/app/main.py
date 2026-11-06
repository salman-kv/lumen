import asyncio
import json
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import classifier, engine, llm, models_s1
from .config import BASE_DIR, settings
from .db import Chunk, Document, Organization, QuestionLog, Rule, get_db, init_db, new_token
from .ingest import process_document
from .pdfproc import PdfError, validate_and_read
from .security import current_org, hash_password, make_jwt, verify_password

@asynccontextmanager
async def lifespan(_):
    init_db()
    warm = [asyncio.create_task(llm.warmup()), asyncio.create_task(asyncio.to_thread(models_s1.warmup))]
    yield
    for t in warm:
        t.cancel()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
# Public endpoints (/api/ask, /api/public/*) are meant to be called from embedding pages; admin endpoints
# are protected by bearer JWT (not cookies), so permissive CORS does not expose them.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(_, exc):
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


# ------------------------------------------------------------------ helpers

def base_url(request: Request) -> str:
    return (settings.public_url or str(request.base_url)).rstrip("/")


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(key: str):
    q, nowt = _hits[key], time.time()
    while q and q[0] < nowt - 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_minute:
        raise HTTPException(429, "You're asking too quickly. Please wait a moment and try again.")
    q.append(nowt)


def doc_out(d: Document) -> dict:
    return {"id": d.id, "filename": d.filename, "pages": d.pages, "size_bytes": d.size_bytes, "status": d.status,
            "stage": d.stage, "error": d.error, "chunks": d.chunk_count, "rules": d.rule_count,
            "created_at": d.created_at.isoformat()}


# ------------------------------------------------------------------ auth

class RegisterIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str


def org_out(o: Organization) -> dict:
    return {"id": o.id, "name": o.name, "email": o.email}


@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(422, "Please enter a valid email address.")
    if db.query(Organization).filter(Organization.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    name = body.org_name.strip()
    org = Organization(name=name, email=email, password_hash=hash_password(body.password),
                       assistant_name=f"{name} Assistant")
    db.add(org)
    db.commit()
    return {"token": make_jwt(org.id), "org": org_out(org)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.email == body.email.strip().lower()).first()
    if not org or not verify_password(body.password, org.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return {"token": make_jwt(org.id), "org": org_out(org)}


@app.get("/api/auth/me")
def me(org: Organization = Depends(current_org)):
    return org_out(org)


# ------------------------------------------------------------------ knowledge base (admin)

def limits() -> dict:
    return {"max_docs": settings.max_docs, "max_pages": settings.max_pages, "max_pdf_mb": settings.max_pdf_mb}


@app.get("/api/kb/documents")
def list_documents(org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.org_id == org.id).order_by(Document.created_at.desc()).all()
    return {"documents": [doc_out(d) for d in docs], "limits": limits()}


async def _accept_upload(org: Organization, file: UploadFile, db: Session, replacing: Document | None):
    count = db.query(Document).filter(Document.org_id == org.id).count() - (1 if replacing else 0)
    if count >= settings.max_docs:
        raise HTTPException(409, f"Your knowledge base is full ({settings.max_docs} documents). "
                                 "Delete a document before uploading another.")
    data = await file.read(settings.max_pdf_mb * 1024 * 1024 + 1)
    name = (file.filename or "document.pdf").replace("\\", "/").split("/")[-1][:200]
    try:
        pages = validate_and_read(data, name)  # synchronous validation: instant, meaningful errors
    except PdfError as e:
        code = 413 if "MB" in str(e) else 422
        raise HTTPException(code, str(e))
    stored = uuid.uuid4().hex + ".pdf"
    (settings.upload_dir / stored).write_bytes(data)
    doc = Document(org_id=org.id, filename=name, stored_name=stored, pages=len(pages), size_bytes=len(data),
                   status="processing", stage="Extracting text")
    db.add(doc)
    if replacing:
        (settings.upload_dir / replacing.stored_name).unlink(missing_ok=True)
        db.delete(replacing)
    db.commit()
    return doc


@app.post("/api/kb/documents", status_code=201)
async def upload_document(background: BackgroundTasks, file: UploadFile = File(...),
                          org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    doc = await _accept_upload(org, file, db, None)
    background.add_task(process_document, doc.id)
    return doc_out(doc)


@app.put("/api/kb/documents/{doc_id}")
async def replace_document(doc_id: int, background: BackgroundTasks, file: UploadFile = File(...),
                           org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    old = db.query(Document).filter(Document.id == doc_id, Document.org_id == org.id).first()
    if not old:
        raise HTTPException(404, "Document not found.")
    doc = await _accept_upload(org, file, db, old)
    background.add_task(process_document, doc.id)
    return doc_out(doc)


@app.delete("/api/kb/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.org_id == org.id).first()
    if not doc:
        raise HTTPException(404, "Document not found.")
    db.query(Chunk).filter(Chunk.doc_id == doc.id).delete()
    db.query(Rule).filter(Rule.doc_id == doc.id).delete()
    (settings.upload_dir / doc.stored_name).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()


@app.get("/api/kb/documents/{doc_id}/file")
def download_document(doc_id: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.org_id == org.id).first()
    if not doc:
        raise HTTPException(404, "Document not found.")
    return FileResponse(settings.upload_dir / doc.stored_name, media_type="application/pdf", filename=doc.filename)


@app.get("/api/kb/rules")
def list_rules(org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    rows = (db.query(Rule, Document.filename).join(Document, Document.id == Rule.doc_id)
            .filter(Rule.org_id == org.id).order_by(Rule.benefit, Rule.id).all())
    return {"rules": [{"id": r.id, "benefit": r.benefit, "label": r.label, "operator": r.operator, "value": r.value,
                       "document": fn, "page": r.page, "source": r.source, "evidence": r.evidence}
                      for r, fn in rows]}


# ------------------------------------------------------------------ assistant (admin)

class AssistantIn(BaseModel):
    assistant_name: str | None = Field(default=None, min_length=1, max_length=80)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    welcome_message: str | None = Field(default=None, max_length=300)
    suggestions: list[str] | None = None


def assistant_out(o: Organization, request: Request) -> dict:
    origin = base_url(request)
    url = f"{origin}/a/{o.assistant_token}"
    return {"token": o.assistant_token, "url": url, "assistant_name": o.assistant_name,
            "brand_color": o.brand_color, "welcome_message": o.welcome_message, "suggestions": o.suggestions or [],
            "embed_iframe": f'<iframe src="{url}?embed=1" title="{o.assistant_name}" width="400" height="640" '
                            f'style="border:0;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.18)" '
                            f'allow="clipboard-write"></iframe>',
            "embed_script": f'<script src="{origin}/embed.js" data-token="{o.assistant_token}" async></script>'}


@app.get("/api/assistant")
def get_assistant(request: Request, org: Organization = Depends(current_org)):
    return assistant_out(org, request)


@app.patch("/api/assistant")
def update_assistant(body: AssistantIn, request: Request, org: Organization = Depends(current_org),
                     db: Session = Depends(get_db)):
    if body.assistant_name is not None:
        org.assistant_name = body.assistant_name.strip()
    if body.brand_color is not None:
        org.brand_color = body.brand_color
    if body.welcome_message is not None:
        org.welcome_message = body.welcome_message.strip()
    if body.suggestions is not None:
        org.suggestions = [s.strip()[:140] for s in body.suggestions if s.strip()][:4]
    db.merge(org)
    db.commit()
    return assistant_out(org, request)


@app.post("/api/assistant/regenerate")
def regenerate(request: Request, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    org.assistant_token = new_token()
    db.merge(org)
    db.commit()
    return assistant_out(org, request)


@app.get("/api/usage")
def usage(org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    q = db.query(QuestionLog).filter(QuestionLog.org_id == org.id)
    total = q.count()
    by = dict(db.query(QuestionLog.outcome, func.count()).filter(QuestionLog.org_id == org.id)
              .group_by(QuestionLog.outcome).all())
    since = datetime.now(timezone.utc) - timedelta(days=6)
    days = {(since + timedelta(days=i)).date().isoformat(): 0 for i in range(7)}
    for (ts,) in db.query(QuestionLog.created_at).filter(QuestionLog.org_id == org.id,
                                                          QuestionLog.created_at >= since.replace(hour=0, minute=0)):
        days[ts.date().isoformat()] = days.get(ts.date().isoformat(), 0) + 1
    avg = db.query(func.avg(QuestionLog.latency_ms)).filter(QuestionLog.org_id == org.id).scalar() or 0
    return {"asked": total, "answered": by.get("answered", 0) + by.get("needs_info", 0),
            "unable": by.get("no_knowledge", 0) + by.get("error", 0),
            "decision_questions": q.filter(QuestionLog.used_decisions.is_(True)).count(),
            "avg_latency_ms": round(avg), "daily": [{"date": k, "count": v} for k, v in days.items()],
            "recent": [{"question": r.question, "outcome": r.outcome, "type": r.qtype,
                        "at": r.created_at.isoformat()}
                       for r in q.order_by(QuestionLog.id.desc()).limit(8)]}


# ------------------------------------------------------------------ public assistant

class AskIn(BaseModel):
    token: str
    question: str
    context: str = ""  # earlier question, when the user is answering a "more information needed" reply


def _with_context(body: AskIn) -> str:
    q = _clean_question(body.question)
    prev = (body.context or "").strip()[:1000]
    return f"{prev} {q}" if prev else q


def _org_by_token(db: Session, token: str) -> Organization:
    org = db.query(Organization).filter(Organization.assistant_token == token.strip()).first() if token else None
    if not org:
        raise HTTPException(401, "This assistant link is invalid or has been replaced. "
                                 "Please ask the organization for a new link.")
    return org


def _clean_question(q: str) -> str:
    q = (q or "").strip()
    if not q:
        raise HTTPException(422, "Please type a question first.")
    if len(q) > 1000:
        raise HTTPException(422, "That question is too long. Please keep it under 1000 characters.")
    return q


@app.get("/api/public/assistant/{token}")
def public_assistant(token: str, db: Session = Depends(get_db)):
    org = _org_by_token(db, token)
    return {"name": org.assistant_name, "org": org.name, "color": org.brand_color, "welcome": org.welcome_message,
            "suggestions": org.suggestions or []}


@app.post("/api/ask")
async def ask(body: AskIn, request: Request, db: Session = Depends(get_db)):
    org = _org_by_token(db, body.token)
    question = _with_context(body)
    org_id = org.id
    db.close()
    rate_limit(f"{body.token}:{request.client.host if request.client else ''}")
    final = None
    async for ev in engine.run(org_id, question):
        if ev["type"] == "final":
            final = ev["data"]
    return final


@app.post("/api/ask/stream")
async def ask_stream(body: AskIn, request: Request, db: Session = Depends(get_db)):
    org = _org_by_token(db, body.token)
    question = _with_context(body)
    org_id = org.id
    db.close()
    rate_limit(f"{body.token}:{request.client.host if request.client else ''}")

    async def gen():
        try:
            async for ev in engine.run(org_id, question):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong while answering. Please try again.'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/health")
async def health():
    return {"status": "ok", "llm": await llm.health(), "embeddings": settings.embed_backend}


# ------------------------------------------------------------------ frontend (built SPA)

DIST = BASE_DIR.parent / "frontend" / "dist"
if DIST.exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
