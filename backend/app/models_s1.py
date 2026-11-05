"""System 1 models: small, fast, local models that make specific decisions without an LLM.

- Embedder  : bge-small sentence embeddings (dense retrieval, policy-choice, question classifier)
- Reranker  : MiniLM cross-encoder (evidence-support *score* decision)
Both fall back to a deterministic hashing model when EMBED_BACKEND=hash (offline tests).
"""
import hashlib
import math
import re
import threading

import numpy as np

from .config import settings

_lock = threading.Lock()
_embedder = None
_reranker = None
TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an the of to in and or is are be for on at by with from that this it as do does can i my me what which how who when where".split())


def _stem(t: str) -> str:
    """Very light suffix stripping so 'remotely' matches 'remote' and 'scholarships' matches 'scholarship'."""
    for suf, keep in (("ies", "y"), ("ing", ""), ("ly", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(t) > len(suf) + 3 and t.endswith(suf) and not t.endswith("ss"):
            return t[: -len(suf)] + keep
    return t


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in TOKEN.findall(text.lower()) if t not in STOP]


def _hash_vec(text: str, dim: int = 384) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float32)
    for t in tokens(text):
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        v[h % dim] += 1.0 if (h >> 20) & 1 else -1.0
    n = np.linalg.norm(v)
    return v / n if n else v


def _get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            from fastembed import TextEmbedding
            _embedder = TextEmbedding(settings.embed_model)
    return _embedder


def _get_reranker():
    global _reranker
    with _lock:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _reranker = TextCrossEncoder(settings.rerank_model)
    return _reranker


def embed(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    if settings.embed_backend == "hash":
        return np.stack([_hash_vec(t) for t in texts])
    arr = np.array(list(_get_embedder().embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.where(norms == 0, 1, norms)


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 30), -30)))


def rerank(query: str, passages: list[str]) -> list[float]:
    """Return a 0..1 'how well does this passage support answering the query' score per passage."""
    if not passages:
        return []
    if settings.embed_backend == "hash":
        q = set(tokens(query))
        out = []
        for p in passages:
            pt = set(tokens(p))
            m = len(q & pt)
            cov = m / max(1, len(q))
            out.append(0.0 if (m < 2 or cov < 0.5) else min(1.0, cov * 1.5))
        return out
    logits = list(_get_reranker().rerank(query, passages))
    return [sigmoid(float(x)) for x in logits]


def warmup():
    embed(["warm up"])
    rerank("warm up", ["warm up"])
