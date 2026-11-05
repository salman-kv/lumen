"""Background document processing: chunk -> embed -> extract rule cards. Reports stages to the UI."""
import asyncio
import logging

from . import models_s1, rules
from .config import settings
from .db import Chunk, Document, Rule, SessionLocal
from .pdfproc import PdfError, chunk_page, validate_and_read
from .retrieval import to_blob

log = logging.getLogger("ingest")


def process_document(doc_id: int) -> None:
    db = SessionLocal()
    doc = db.get(Document, doc_id)
    if not doc:
        db.close()
        return
    try:
        data = (settings.upload_dir / doc.stored_name).read_bytes()
        pages = validate_and_read(data, doc.filename)

        doc.stage = "Indexing passages"
        db.commit()
        rows = []
        for p in pages:
            for i, text in enumerate(chunk_page(p.text)):
                rows.append((p.page, i, text))
        vecs = models_s1.embed([r[2] for r in rows])
        for (page, idx, text), v in zip(rows, vecs):
            db.add(Chunk(org_id=doc.org_id, doc_id=doc.id, page=page, idx=idx, text=text, embedding=to_blob(v)))
        doc.chunk_count = len(rows)
        db.commit()

        doc.stage = "Reading policy rules"
        db.commit()
        cards = []
        for p in pages:
            cards += rules.mine_page(p.text, p.page)
        if settings.rules_llm and settings.llm_provider != "mock":
            cue_pages = [p for p in pages if rules.RULE_CUES.search(p.text)][: settings.rules_llm_max_pages]
            proposed = []
            for p in cue_pages:
                try:
                    proposed += asyncio.run(rules.llm_rules(p.text, p.page))
                except Exception:  # LLM trouble must never fail the upload
                    log.exception("llm rule extraction failed")
            cards += rules.gate_llm_rules(cards, proposed)
        cards = rules.dedupe(cards)
        for c in cards:
            db.add(Rule(org_id=doc.org_id, doc_id=doc.id, page=c.page, benefit=c.benefit, field=c.field,
                        label=c.label, operator=c.operator, value=c.value, evidence=c.evidence, source=c.source))
        doc.rule_count = len(cards)
        doc.pages = len(pages)
        doc.status, doc.stage, doc.error = "ready", "Ready", None
        db.commit()
    except PdfError as e:
        db.rollback()
        _fail(db, doc_id, str(e))
    except Exception as e:  # document-processing failure -> meaningful message, never a crash
        log.exception("document processing failed")
        db.rollback()
        _fail(db, doc_id, "We couldn't process this document. Please try again or upload a different file.")
    finally:
        db.close()


def _fail(db, doc_id, message):
    doc = db.get(Document, doc_id)
    if doc:
        db.query(Chunk).filter(Chunk.doc_id == doc_id).delete()
        db.query(Rule).filter(Rule.doc_id == doc_id).delete()
        doc.status, doc.stage, doc.error = "failed", "Failed", message
        db.commit()
