"""Hybrid retrieval (BM25 + dense, fused with RRF) followed by cross-encoder reranking.

EVERY query is scoped by org_id at the database level; nothing else is ever loaded.
"""
import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from . import models_s1
from .config import settings
from .db import Chunk, Document


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    document: str
    page: int
    text: str
    score: float  # reranker support score 0..1


def to_blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def _bm25(query: list[str], docs: list[list[str]], k1=1.5, b=0.75) -> list[float]:
    n = len(docs)
    avg = sum(len(d) for d in docs) / max(1, n)
    df = Counter(t for d in docs for t in set(d))
    scores = []
    for d in docs:
        tf = Counter(d)
        s = 0.0
        for t in query:
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / max(1, avg)))
        scores.append(s)
    return scores


def retrieve(db: Session, org_id: int, question: str, top_k: int | None = None) -> list[Hit]:
    top_k = top_k or settings.top_k
    rows = (db.query(Chunk, Document.filename)
            .join(Document, Document.id == Chunk.doc_id)
            .filter(Chunk.org_id == org_id, Document.org_id == org_id, Document.status == "ready")
            .all())
    if not rows:
        return []
    chunks = [r[0] for r in rows]
    names = {c.id: r[1] for c, r in zip(chunks, rows)}
    toks = [models_s1.tokens(c.text) for c in chunks]
    bm = _bm25(models_s1.tokens(question), toks)
    qv = models_s1.embed([question])[0]
    mat = np.stack([from_blob(c.embedding) for c in chunks])
    dense = mat @ qv

    def ranks(scores):
        order = np.argsort(-np.array(scores))
        r = np.empty(len(scores), dtype=int)
        r[order] = np.arange(len(scores))
        return r

    rb, rd = ranks(bm), ranks(dense)
    rrf = [1 / (60 + rb[i]) + 1 / (60 + rd[i]) for i in range(len(chunks))]
    cand = np.argsort(-np.array(rrf))[: max(top_k * 3, 10)]
    supports = models_s1.rerank(question, [chunks[i].text for i in cand])
    hits = [Hit(chunks[i].id, chunks[i].doc_id, names[chunks[i].id], chunks[i].page, chunks[i].text, s)
            for i, s in zip(cand, supports)]
    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]
