"""Optional demo seeding for a hosted copy (SEED_DEMO=true): creates the two sample organizations and uploads their
PDFs through the app's own API once the server is up, so reviewers can sign in and try it straight away.
Safe to run on every start: existing accounts and documents are reused."""
import asyncio
import json
import logging

import httpx

from .config import settings

log = logging.getLogger("demo_seed")


def demo_spec() -> dict:
    p = settings.sample_dir / "test_questions.json"
    return json.loads(p.read_text(encoding="utf-8"))["organizations"] if p.exists() else {}


def demo_accounts() -> list[dict]:
    if not settings.seed_demo:
        return []
    return [{"org": o["name"], "email": o["email"], "password": o["password"]} for o in demo_spec().values()]


async def _wait_ready(c: httpx.AsyncClient) -> None:
    for _ in range(120):
        try:
            if (await c.get("/api/health")).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(1)
    raise RuntimeError("server did not become ready")


async def seed_demo() -> None:
    if not settings.seed_demo:
        return
    try:
        async with httpx.AsyncClient(base_url=settings.seed_base, timeout=120) as c:
            await _wait_ready(c)
            for key, o in demo_spec().items():
                r = await c.post("/api/auth/login", json={"email": o["email"], "password": o["password"]})
                if r.status_code != 200:
                    r = await c.post("/api/auth/register",
                                     json={"org_name": o["name"], "email": o["email"], "password": o["password"]})
                    r.raise_for_status()
                h = {"Authorization": f"Bearer {r.json()['token']}"}
                have = {d["filename"] for d in (await c.get("/api/kb/documents", headers=h)).json()["documents"]}
                for pdf in sorted((settings.sample_dir / key).glob("*.pdf")):
                    if pdf.name not in have:
                        up = await c.post("/api/kb/documents", headers=h,
                                          files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")})
                        up.raise_for_status()
                await c.patch("/api/assistant", headers=h, json={
                    "assistant_name": o["assistant_name"], "brand_color": o["brand_color"],
                    "welcome_message": o["welcome"], "suggestions": o["suggestions"]})
                log.info("demo organization ready: %s", o["name"])
    except Exception:
        log.exception("demo seeding failed")
