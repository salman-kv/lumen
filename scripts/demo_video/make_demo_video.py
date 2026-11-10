"""Builds the Lumen demo video: a real recording of the app in a browser, narrated, with slides for the architecture.

  cd backend
  uv run --with playwright --with imageio-ffmpeg --with pypdfium2 --with pillow python ../scripts/demo_video/make_demo_video.py [--fast] [--no-tts]

What it does
  1. writes the narration, then turns each beat into a WAV file with the Windows built-in voice (System.Speech)
  2. writes the slides (HTML, shown in the same browser recording)
  3. records Microsoft Edge doing the demo against http://localhost:8000: typing, clicks, uploads, live answers
  4. mixes the narration onto the recording with ffmpeg and writes video_out/Lumen_Demo.mp4

Needs the app running on port 8000 with SEED_DEMO=true (the demo accounts), Edge, and Windows (for the voice).
--fast does a dry run of the actions without recording (to check selectors); --no-tts reuses the audio already made.
"""
import json
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_out"
AUDIO, SLIDES, ASSETS = OUT / "audio", OUT / "slides", OUT / "assets"
BASE = "http://localhost:8000"
VOICE, RATE = "Microsoft Zira Desktop", 0
FAST = "--fast" in sys.argv

ORG_NAME = "Demo University"
EMAIL = f"video-demo-{int(time.time())}@example.com"
PASSWORD = "demo-video-pass-1"

# ------------------------------------------------------------------------------------------ narration
# (id, caption shown on screen, narration). Live beats have an action function of the same id below.
BEATS = [
    ("title", "Lumen: AI Knowledge and Decision Assistant",
     "Hello. This video walks through Lumen, a multi-tenant AI knowledge and decision assistant. An organization uploads its "
     "policy PDFs and gets an assistant that it can share, or embed on any website. Visitors ask questions and get answers that "
     "point to the exact document and page. The key idea is that the language model does not do everything. Decisions are made "
     "by small models and plain code, and the language model only helps with wording."),
    ("arch_1", "1. Architecture",
     "Here is the architecture. The front end is a React app with two parts: the admin dashboard, and the visitor chat. Both talk "
     "to a single FastAPI back end. That one server exposes the API, serves the website, runs the PDF pipeline, and runs the "
     "question engine. All data lives in a SQLite database: accounts, documents, passages with their embeddings, rules, and the "
     "question history. Two small models run inside the server for search. A language model, Groq in the live setup, or Ollama on "
     "a local machine, is reached over HTTP."),
    ("arch_2", "Tenants and security",
     "Every organization is a tenant. Each table carries an organization id, and every query filters by it, so one tenant can never "
     "read another's data. Admins sign in with a signed login token. Visitors use a secret assistant token from the public link. "
     "That token is not a login, so it can never reach the admin APIs."),
    ("arch_3", "Three layers of intelligence",
     "The system has three layers. First, the language model. It understands the wording of a question, and writes the final "
     "sentence. Second, system one models: small, fast, specialized components that make the real decisions. They search the "
     "documents, classify the question, choose the policy, and check each rule. Third, application logic: plain code that routes "
     "the message, combines the decisions, finds missing information, and refuses to answer when there is no evidence."),
    ("arch_4", "The path of a question",
     "This is the path of a question. A router first handles greetings and unclear messages. A real question is searched, but only "
     "inside that organization's documents. If there is no real evidence, the assistant says so, and lists what it can help with. "
     "If the visitor states facts about themselves, those facts are extracted, one check runs per rule in parallel, the results "
     "are combined, and only then does the language model word the answer."),
    ("land", "2. Product walkthrough: sign up",
     "Now the product. This is the landing page. Let's create a new organization."),
    ("register", "Create an organization",
     "Registration asks for the organization name, an email, and a password. The form validates as you type, and shows the strength "
     "of the password. Each registration creates a new, private organization."),
    ("dash", "Dashboard and guided tour",
     "After sign up, the dashboard opens with a short guided tour, which can be skipped at any time. Let's skip it, and open the "
     "knowledge base."),
    ("upload_1", "Upload a PDF",
     "Here we upload the policy PDFs. A file is validated right away, and then processed in the background. Watch the stages: "
     "extracting, indexing, and reading rules."),
    ("upload_2", "Limits and clear errors",
     "Each PDF is split into passages that never cross a page, embedded as vectors, and scanned for rules, such as GPA at least "
     "three point five. The limits are ten documents, twenty pages, and ten megabytes, and errors are explained clearly. For "
     "example, a text file is rejected immediately."),
    ("rules", "What the assistant learned",
     "The section called what the assistant learned shows the rule cards found in the documents, each with its page. These are what "
     "the yes or no checks run on."),
    ("assistant_1", "Assistant settings and live preview",
     "In the assistant tab we can change the name, the color, the greeting, and the starter questions. The live preview on the "
     "right is the real assistant, and it updates as you type."),
    ("assistant_2", "Public link and embed code",
     "Here are the public link and the embed code. The link works without an account. Regenerating it would immediately stop the "
     "old link, so it asks for confirmation first."),
    ("embed", "Embedding in another web page",
     "To show embedding, this is a separate web page that stands in for a customer's site. One script tag adds the chat bubble. "
     "Clicking it opens the assistant."),
    ("qa_1", "3. Questions with references",
     "Let's ask some questions. Greetings are answered instantly by the app, with suggestion buttons that guide the visitor."),
    ("qa_2", "Answer with document and page",
     "A policy question gets an answer with the document and page. Clicking a source opens the exact passage."),
    ("qa_3", "Everyday wording",
     "People rarely use policy words, so everyday wording is mapped to them. Here, money back, and quit, still find the refund "
     "policy."),
    ("qa_4", "Follow-up buttons",
     "The follow-up buttons come from the same document, so the visitor always has a next step."),
    ("qa_5", "No answer: no guessing",
     "When the documents do not contain an answer, the assistant says so, shows no sources, and lists what it can help with, "
     "instead of guessing."),
    ("dec_1", "4. A question that needs several decisions",
     "Now the most important part: a question that needs several decisions. A student says: second year, GPA three point six, and "
     "already holds a sports scholarship. Are they eligible for the merit scholarship?"),
    ("dec_2", "The result and how it was decided",
     "The answer is no, and it explains why, using the rules from the document. Let's open how it decided, to see the steps."),
    ("dec_3", "Search, classify, choose, check, combine, answer",
     "First, search finds the merit scholarship passages, for this organization only. Second, a classifier labels the question as "
     "eligibility. Third, the policy chooser picks the merit scholarship. Fourth, the facts are extracted: year two, GPA three "
     "point six, and a sports scholarship held. Facts that the model invents are discarded unless they appear in the question. "
     "Fifth, one check per rule runs in parallel, together with an evidence score. Two checks pass, and one fails. Sixth, "
     "application code combines them: all must pass, so the result is not eligible. Finally, the language model only words the "
     "result, and a guard rejects wording that contradicts the verdict."),
    ("dec_4", "Missing facts: it asks, it does not guess",
     "If the student gives no facts, the assistant asks for the missing ones, instead of guessing."),
    ("dec_5", "All rules pass",
     "And for a third year student with a GPA of three point eight, and no sports scholarship, every rule passes."),
    ("iso_1", "5. Two organizations, fully isolated",
     "Now multi-tenant isolation. Signing out, and into a second organization, Acme Corp, which has completely different documents."),
    ("iso_2", "Acme: different documents and assistant",
     "Acme has leave, remote work, and expense policies, with its own assistant and its own link."),
    ("iso_3", "Acme cannot see Northfield's documents",
     "Asking Acme's assistant about the merit scholarship finds nothing, because that document belongs to another organization. "
     "A question about remote work, which Acme does have, is answered from its own policy."),
    ("tests", "Isolation is tested",
     "Isolation is also covered by automated tests: that organization B cannot read organization A's knowledge, that the "
     "assistant token cannot reach the admin API, and that regenerating the link invalidates the old one. In total, one hundred "
     "nineteen tests pass."),
    ("usage", "Usage and full question history",
     "Back in our own organization, the usage tab shows how many questions were asked and answered, a seven day chart, and the "
     "full question history. Each row opens to show the answer and its sources, and the history can be searched, filtered, and "
     "downloaded as a CSV file."),
    ("closing", "Summary",
     "To summarize: Lumen separates language from decisions. Small models and plain code decide, and the language model only words "
     "the answer. Each organization's data is isolated and tested. The limits are that rule mining is pattern based, rules combine "
     "with AND only, and the database is SQLite, so production would add Postgres, a job queue, and a review screen for rules. "
     "The code and the documentation are on GitHub. Thank you for watching."),
]

SAY = [("PDFs", "P D Fs"), ("PDF", "P D F"), ("APIs", "A P Is"), ("API", "A P I"), ("GPA", "G P A"), ("SQLite", "S Q Lite"),
       ("FastAPI", "Fast A P I"), ("CSV", "C S V"), ("HTTP", "H T T P"), ("Groq", "Grok"), ("Ollama", "Oh lama"),
       ("Postgres", "Post gress"), ("AI", "A I"), ("JWT", "J W T"), ("ID", "I D"), ("embed.js", "embed dot J S"),
       ("front end", "front end"), ("AND", "and")]


def spoken(text: str) -> str:
    for a, b in SAY:
        text = re.sub(rf"\b{re.escape(a)}\b", b, text)
    return text


# ------------------------------------------------------------------------------------------ audio
def make_audio():
    AUDIO.mkdir(parents=True, exist_ok=True)
    items = [{"id": i, "text": spoken(t)} for i, _, t in BEATS]
    (OUT / "narration.json").write_text(json.dumps(items, indent=1), encoding="utf-8")
    ps = OUT / "tts.ps1"
    ps.write_text(
        'param($Json, $OutDir, $Voice, $Rate)\nAdd-Type -AssemblyName System.Speech\n'
        '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n$s.SelectVoice($Voice); $s.Rate = [int]$Rate\n'
        '$beats = Get-Content -Raw -Encoding UTF8 $Json | ConvertFrom-Json\n'
        'foreach ($b in $beats) { $s.SetOutputToWaveFile((Join-Path $OutDir ($b.id + ".wav"))); $s.Speak($b.text); $s.SetOutputToNull() }\n',
        encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps), "-Json", str(OUT / "narration.json"),
                    "-OutDir", str(AUDIO), "-Voice", VOICE, "-Rate", str(RATE)], check=True)
    lengths = {}
    for i, _, _ in BEATS:
        with wave.open(str(AUDIO / f"{i}.wav")) as w:
            lengths[i] = w.getnframes() / w.getframerate()
    (OUT / "durations.json").write_text(json.dumps(lengths, indent=1), encoding="utf-8")
    print(f"audio: {len(lengths)} clips, {sum(lengths.values()) / 60:.1f} minutes of narration")
    return lengths


# ------------------------------------------------------------------------------------------ slides
CSS = """
*{box-sizing:border-box;margin:0}body{width:1280px;height:720px;overflow:hidden;font-family:'Segoe UI',Arial,sans-serif;color:#eaf3ef;
background:radial-gradient(circle at 85% 8%,#123a30 0,#0c1210 55%);padding:44px 64px}
.k{color:#2fc79e;font-weight:600;letter-spacing:.14em;text-transform:uppercase;font-size:15px}
h1{font-size:60px;letter-spacing:-.02em;line-height:1.05}h2{font-size:38px;letter-spacing:-.01em;margin:8px 0 18px}
p,li{font-size:23px;line-height:1.5;color:#c9d8d2}li{margin:12px 0}
.card{background:#fff;border-radius:18px;padding:14px;box-shadow:0 10px 40px rgba(0,0,0,.45)}
.card img{display:block;max-width:100%;max-height:100%}.row{display:flex;gap:46px;align-items:center;height:560px}
.ok{color:#2fc79e;font-weight:700;margin-right:10px}b{color:#fff}
"""


def page(body: str) -> str:
    return f"<!doctype html><meta charset=utf-8><style>{CSS}</style>{body}"


def write_slides():
    SLIDES.mkdir(parents=True, exist_ok=True)
    slides = {
        "title": page('<div style="margin-top:150px"><div class=k>Assignment demo</div><h1 style="font-size:104px;margin:14px 0">Lumen</h1>'
                      '<h2 style="font-weight:400;color:#c9d8d2">A multi-tenant AI Knowledge and Decision Assistant</h2>'
                      '<p style="margin-top:34px">Grounded answers with document and page references<br>Decisions made by small models and plain code<br>'
                      'Every organization isolated from every other</p></div>'),
        "arch_1": page('<div class=k>Architecture</div><h2>One server, two apps, one database</h2>'
                       '<div class=card style="height:560px;display:flex;justify-content:center"><img src="../assets/architecture.png"></div>'),
        "arch_2": page('<div class=k>Architecture</div><h2>Tenants and security</h2><ul style="list-style:none;padding:0;margin-top:30px">'
                       '<li><span class=ok>&#10003;</span>Every table has an <b>org_id</b>; every query filters by it</li>'
                       '<li><span class=ok>&#10003;</span>Admins: bcrypt password, <b>signed login token</b> (24 hours)</li>'
                       '<li><span class=ok>&#10003;</span>Visitors: a <b>secret assistant token</b> in the public link</li>'
                       '<li><span class=ok>&#10003;</span>The assistant token is <b>not a login</b>: it cannot reach admin APIs</li>'
                       '<li><span class=ok>&#10003;</span>Uploaded PDFs are private; regenerating the link kills the old one</li></ul>'),
        "arch_3": page('<div class=k>Architecture</div><h2>Three layers of intelligence</h2><ul style="list-style:none;padding:0;margin-top:26px">'
                       '<li><b style="color:#2fc79e">1. Language model</b> (Groq or Ollama): understands wording, writes the final sentence</li>'
                       '<li><b style="color:#2fc79e">2. System 1 models</b>: search, question type, policy choice, rule checks, evidence score</li>'
                       '<li><b style="color:#2fc79e">3. Application logic</b>: routing, combining decisions, missing facts, refusing without evidence</li></ul>'
                       '<p style="margin-top:30px"><b>The language model never decides.</b> It receives a finished verdict and explains it.</p>'),
        "arch_4": page('<div class=row><div style="flex:1"><div class=k>Architecture</div><h2>The path of a question</h2>'
                       '<ul style="padding-left:22px"><li>Search only this organization&rsquo;s documents</li><li>No evidence: refuse, never guess</li>'
                       '<li>Facts, rule checks and evidence score run in <b>parallel</b></li><li>Code combines the decisions</li>'
                       '<li>The language model words the result; guards check it</li></ul></div>'
                       '<div class=card style="height:610px;margin-top:-20px"><img style="height:582px" src="../assets/pipeline.png"></div></div>'),
        "tests": page('<div class=k>Quality</div><h2>Isolation is tested</h2><ul style="list-style:none;padding:0;margin-top:26px">'
                      '<li><span class=ok>&#10003;</span>Organization B cannot get organization A&rsquo;s knowledge</li>'
                      '<li><span class=ok>&#10003;</span>Retrieval is scoped to one organization at query level</li>'
                      '<li><span class=ok>&#10003;</span>The assistant token cannot reach the admin API</li>'
                      '<li><span class=ok>&#10003;</span>Regenerating the link invalidates the old one</li>'
                      '<li><span class=ok>&#10003;</span>Documents are not publicly downloadable</li></ul>'
                      '<p style="margin-top:28px"><b>119 automated tests</b> &middot; 19-question evaluation &middot; 44 extra scenarios</p>'),
        "closing": page('<div style="margin-top:130px"><div class=k>Summary</div><h1 style="font-size:70px;margin:12px 0 24px">Language is separate from decisions</h1>'
                        '<ul style="padding-left:24px"><li>Small models and plain code decide; the language model only words the answer</li>'
                        '<li>Every organization&rsquo;s data is isolated and tested</li>'
                        '<li>Next: Postgres, a job queue, and a rule review screen</li></ul>'
                        '<p style="margin-top:26px"><b>github.com/salman-kv/lumen</b> &nbsp;&middot;&nbsp; full documentation PDFs in the repository</p></div>'),
    }
    for name, html in slides.items():
        (SLIDES / f"{name}.html").write_text(html, encoding="utf-8")


# ------------------------------------------------------------------------------------------ browser actions
CURSOR_JS = """
(() => {
  if (window.top !== window) return;
  const make = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;width:26px;height:26px;border-radius:50%;background:rgba(47,199,158,.28);' +
      'border:2.5px solid #2fc79e;pointer-events:none;left:-60px;top:-60px;transform:translate(-50%,-50%);transition:transform .12s,background .12s';
    const k = document.createElement('div'); k.id = '__cap';
    k.style.cssText = 'position:fixed;z-index:2147483646;top:10px;left:50%;transform:translateX(-50%);background:rgba(8,14,12,.88);' +
      'color:#eaf3ef;font:600 15px Segoe UI,Arial,sans-serif;padding:7px 18px;border-radius:999px;border:1px solid #2fc79e;' +
      'pointer-events:none;display:none;white-space:nowrap;box-shadow:0 4px 18px rgba(0,0,0,.4)';
    document.documentElement.append(c, k);
    window.__mc = (x, y) => { c.style.left = x + 'px'; c.style.top = y + 'px'; };
    window.__fx = () => { c.style.transform = 'translate(-50%,-50%) scale(.55)'; c.style.background = 'rgba(47,199,158,.85)';
      setTimeout(() => { c.style.transform = 'translate(-50%,-50%) scale(1)'; c.style.background = 'rgba(47,199,158,.28)'; }, 160); };
    window.__cap = (t) => { k.textContent = t; k.style.display = t ? 'block' : 'none'; };
  };
  if (document.documentElement) make(); else addEventListener('DOMContentLoaded', make);
})();
"""


class Demo:
    def __init__(self, page, lengths):
        self.p, self.len = page, lengths
        self.x, self.y = 640, 360
        self.token = self.acme_token = None

    # ---- helpers
    def caption(self, text):
        try:
            self.p.evaluate("t => window.__cap && window.__cap(t)", text)
        except Exception:
            pass

    def goto(self, url, caption=None, wait="domcontentloaded"):
        self.p.goto(url, wait_until=wait)
        self.p.wait_for_timeout(250 if FAST else 700)
        if caption:
            self.caption(caption)

    def move(self, x, y, steps=22):
        for i in range(1, steps + 1):
            nx, ny = self.x + (x - self.x) * i / steps, self.y + (y - self.y) * i / steps
            self.p.mouse.move(nx, ny)
            try:
                self.p.evaluate("([a, b]) => window.__mc && window.__mc(a, b)", [nx, ny])
            except Exception:
                pass
            if not FAST:
                self.p.wait_for_timeout(11)
        self.x, self.y = x, y

    def click(self, loc, pause=0.35):
        loc.first.scroll_into_view_if_needed(timeout=8000)
        box = loc.first.bounding_box()
        self.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=8 if FAST else 22)
        self.p.evaluate("window.__fx && window.__fx()")
        self.p.mouse.click(self.x, self.y)
        self.p.wait_for_timeout(100 if FAST else int(pause * 1000))

    def type(self, loc, text, delay=55):
        self.click(loc, pause=0.15)
        self.p.keyboard.type(text, delay=0 if FAST else delay)

    def ask(self, input_loc, text, finish_pause=0.9):
        """Type a question, send it, and wait until the streamed answer has fully arrived."""
        self.type(input_loc, text)
        with self.p.expect_response(lambda r: "/api/ask/stream" in r.url, timeout=60000) as info:
            self.p.keyboard.press("Enter")
        try:
            info.value.finished()
        except Exception:
            pass
        self.p.wait_for_timeout(300 if FAST else int(finish_pause * 1000))

    def api_json(self, path):
        return self.p.evaluate("p => fetch(p, {headers:{Authorization:'Bearer '+localStorage.getItem('kda_token')}}).then(r => r.json())", path)

    def wait_documents_ready(self, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            docs = self.api_json("/api/kb/documents")["documents"]
            if docs and all(d["status"] != "processing" for d in docs):
                return docs
            self.p.wait_for_timeout(500)
        return docs

    def soft(self, label, fn):
        """Run an optional step; say so when it did not work (a silent skip would hide a problem in the video)."""
        try:
            fn()
        except Exception as e:
            print(f"  ~~ optional step '{label}' skipped: {type(e).__name__}: {str(e)[:120]}")

    def chat_input(self, frame=None):
        return (frame or self.p).locator("#ask")

    def pdf(self, org, name):
        return str(ROOT / "sample_data" / org / name)

    # ---- the beats
    def title(self):
        self.goto((SLIDES / "title.html").as_uri())

    def arch_1(self): self.goto((SLIDES / "arch_1.html").as_uri(), "1. Architecture")
    def arch_2(self): self.goto((SLIDES / "arch_2.html").as_uri())
    def arch_3(self): self.goto((SLIDES / "arch_3.html").as_uri())
    def arch_4(self): self.goto((SLIDES / "arch_4.html").as_uri())

    def land(self):
        self.goto(BASE + "/", "2. Product walkthrough")
        self.p.wait_for_timeout(1500 if not FAST else 100)
        self.click(self.p.get_by_role("link", name=re.compile("Start free", re.I)))
        self.p.wait_for_url("**/register", timeout=10000)

    def register(self):
        self.caption("Create an organization")
        self.type(self.p.locator("#org_name"), ORG_NAME)
        self.type(self.p.locator("#email"), EMAIL)
        self.type(self.p.locator("#password"), PASSWORD, delay=70)
        self.p.wait_for_timeout(600 if not FAST else 50)
        self.click(self.p.get_by_role("button", name=re.compile("Create account", re.I)))
        self.p.wait_for_url("**/app**", timeout=15000)

    def dash(self):
        self.caption("Dashboard and guided tour")
        def tour():
            self.p.locator("[role=dialog]").first.wait_for(timeout=6000)
            self.p.wait_for_timeout(2500 if not FAST else 100)
            self.click(self.p.get_by_role("button", name="Skip tour").first)
        self.soft("skip tour", tour)
        self.p.wait_for_timeout(600 if not FAST else 50)
        self.click(self.p.locator("nav a", has_text="Knowledge"))

    def _upload(self, path):
        with self.p.expect_file_chooser(timeout=10000) as fc:
            self.click(self.p.get_by_role("button", name=re.compile("Choose files", re.I)))
        fc.value.set_files(path)

    def upload_1(self):
        self.caption("Upload a PDF")
        self._upload(self.pdf("northfield", "Scholarship_Rules.pdf"))
        self.p.wait_for_timeout(2500 if not FAST else 200)
        self.wait_documents_ready()

    def upload_2(self):
        self.caption("Limits and clear errors")
        self._upload(self.pdf("northfield", "Fee_Policy.pdf"))
        self.wait_documents_ready()
        self.p.wait_for_timeout(2500 if not FAST else 100)
        txt = OUT / "notes.txt"
        txt.write_text("This is not a PDF.\n", encoding="utf-8")
        self._upload(str(txt))
        self.p.wait_for_timeout(2500 if not FAST else 100)

    def rules(self):
        self.caption("What the assistant learned")
        self.click(self.p.get_by_role("button", name=re.compile("What the assistant learned")))
        self.p.wait_for_timeout(1500 if not FAST else 100)
        self.p.mouse.wheel(0, 380)

    def assistant_1(self):
        self.caption("Assistant settings and live preview")
        self.click(self.p.locator("nav a", has_text="Assistant"))
        self.p.wait_for_selector("#aname", timeout=10000)
        self.token = self.api_json("/api/assistant")["token"]
        self.p.wait_for_timeout(1200 if not FAST else 50)
        self.p.locator("#aname").fill("")  # clear the old name first, or the new text is typed into the middle of it
        self.type(self.p.locator("#aname"), "Demo University Helper")
        self.click(self.p.locator('button[aria-label^="Use color"]').nth(3))
        self.p.wait_for_timeout(1500 if not FAST else 50)
        self.click(self.p.get_by_role("button", name=re.compile("Save changes")))

    def assistant_2(self):
        self.caption("Public link and embed code")
        self.p.locator('[data-tour="share"]').first.scroll_into_view_if_needed()
        self.p.wait_for_timeout(2500 if not FAST else 50)
        self.p.locator('[data-tour="embed"]').first.scroll_into_view_if_needed()
        self.p.wait_for_timeout(1500 if not FAST else 50)
        self.click(self.p.get_by_role("button", name=re.compile("Regenerate link")))
        self.p.wait_for_timeout(1800 if not FAST else 50)
        self.click(self.p.get_by_role("button", name="Keep current link"))
        a = self.api_json("/api/assistant")
        self.token = a["token"]

    def embed(self):
        self.goto(f"{BASE}/demo.html?token={self.token}", "Embedding in another web page")
        self.p.wait_for_selector(".lumen-btn", timeout=10000)
        self.p.wait_for_timeout(1800 if not FAST else 50)
        self.click(self.p.locator(".lumen-btn"))
        self.p.frame_locator(".lumen-panel iframe").locator("#ask").wait_for(timeout=15000)
        self.p.wait_for_timeout(1200 if not FAST else 50)

    @property
    def frame(self):
        return self.p.frame_locator(".lumen-panel iframe")

    def qa_1(self):
        self.caption("3. Questions with references")
        self.ask(self.frame.locator("#ask"), "hi")

    def qa_2(self):
        self.caption("Answer with document and page")
        self.ask(self.frame.locator("#ask"), "What is the refund policy?")
        self.soft("open source", lambda: self.click(self.frame.get_by_role("button", name=re.compile(r"\.pdf")), pause=0.6))
        self.p.wait_for_timeout(1500 if not FAST else 50)

    def qa_3(self):
        self.caption("Everyday wording")
        self.ask(self.frame.locator("#ask"), "can i get money back if i quit")

    def qa_4(self):
        self.caption("Follow-up buttons")
        def follow_up():
            with self.p.expect_response(lambda r: "/api/ask/stream" in r.url, timeout=60000) as info:
                self.click(self.frame.get_by_role("button", name=re.compile("^Tell me about")))
            info.value.finished()
        self.soft("follow-up button", follow_up)
        self.p.wait_for_timeout(1200 if not FAST else 50)

    def qa_5(self):
        self.caption("No answer: no guessing")
        self.ask(self.frame.locator("#ask"), "Does the university offer a PhD in astrophysics?", finish_pause=1.5)

    def _chat_page(self, token, caption):
        self.goto(f"{BASE}/a/{token}", caption)
        self.p.wait_for_selector("#ask", timeout=15000)

    def dec_1(self):
        self._chat_page(self.token, "4. A question that needs several decisions")
        self.p.wait_for_timeout(1000 if not FAST else 50)
        self.ask(self.chat_input(), "I'm a second-year student with a 3.6 GPA and I already have a sports scholarship. "
                                    "Am I eligible for the merit scholarship?", finish_pause=1.2)

    def dec_2(self):
        self.caption("The result and how it was decided")
        self.p.wait_for_timeout(2500 if not FAST else 50)
        self.soft("open How I decided", lambda: self.click(self.p.get_by_role("button", name=re.compile("How I decided")).last, pause=1.0))

    def dec_3(self):
        self.caption("Search, classify, choose, check, combine, answer")
        self.p.wait_for_timeout(2000 if not FAST else 50)
        for _ in range(4):
            self.p.mouse.wheel(0, 140)
            self.p.wait_for_timeout(6000 if not FAST else 50)

    def dec_4(self):
        self.caption("Missing facts: it asks, it does not guess")
        self.ask(self.chat_input(), "Am I eligible for the merit scholarship?", finish_pause=1.5)

    def dec_5(self):
        self.caption("All rules pass")
        self.ask(self.chat_input(), "I'm a third year student with a 3.8 GPA and no sports scholarship. Can I get the merit "
                                    "scholarship?", finish_pause=1.5)

    def iso_1(self):
        self.goto(BASE + "/app", "5. Two organizations, fully isolated")
        self.click(self.p.get_by_role("button", name=re.compile("Log out")))
        self.p.wait_for_url(re.compile(r"/(login)?$"), timeout=10000)
        self.goto(BASE + "/login", "5. Two organizations, fully isolated")
        self.click(self.p.get_by_role("button", name="Acme Corp"))
        self.p.wait_for_timeout(1000 if not FAST else 50)
        self.click(self.p.get_by_role("button", name=re.compile("^Sign in")))
        self.p.wait_for_url("**/app**", timeout=15000)
        def tour():  # the tour opens for a browser that has not seen it; skip it
            self.p.locator("[role=dialog]").first.wait_for(timeout=3000)
            self.click(self.p.get_by_role("button", name="Skip tour").first)
        self.soft("skip tour (Acme)", tour)

    def iso_2(self):
        self.caption("Acme: different documents and assistant")
        self.click(self.p.locator("nav a", has_text="Knowledge"))
        self.p.wait_for_timeout(3000 if not FAST else 50)
        self.click(self.p.locator("nav a", has_text="Assistant"))
        self.p.wait_for_timeout(2500 if not FAST else 50)
        self.acme_token = self.api_json("/api/assistant")["token"]

    def iso_3(self):
        self._chat_page(self.acme_token, "Acme cannot see Northfield's documents")
        self.p.wait_for_timeout(800 if not FAST else 50)
        self.ask(self.chat_input(), "Am I eligible for the Merit Scholarship?", finish_pause=2.0)
        self.ask(self.chat_input(), "Can I work remotely?", finish_pause=1.5)

    def tests(self):
        self.goto((SLIDES / "tests.html").as_uri())

    def usage(self):
        self.goto(BASE + "/app", "Usage and full question history")  # still signed in as Acme: sign out first
        self.click(self.p.get_by_role("button", name=re.compile("Log out")))
        self.p.wait_for_timeout(800 if not FAST else 50)
        self.goto(BASE + "/login", "Usage and full question history")
        self.type(self.p.locator("#email"), EMAIL)
        self.type(self.p.locator("#password"), PASSWORD, delay=70)
        self.click(self.p.get_by_role("button", name=re.compile("^Sign in")))
        self.p.wait_for_url("**/app**", timeout=15000)
        self.soft("skip tour (own org)", lambda: (self.p.locator("[role=dialog]").first.wait_for(timeout=3000),
                                                  self.click(self.p.get_by_role("button", name="Skip tour").first)))
        self.goto(BASE + "/app/usage", "Usage and full question history")
        self.p.wait_for_timeout(3500 if not FAST else 50)
        self.p.locator('[data-tour="history"]').first.scroll_into_view_if_needed()
        self.p.wait_for_timeout(2500 if not FAST else 50)
        self.click(self.p.locator("section[data-tour=history] ul li button").first, pause=1.0)
        self.p.wait_for_timeout(3000 if not FAST else 50)
        self.type(self.p.get_by_placeholder("Search questions and answers"), "refund")
        self.p.wait_for_timeout(3000 if not FAST else 50)

    def closing(self):
        self.goto((SLIDES / "closing.html").as_uri())


# ------------------------------------------------------------------------------------------ record and mix
def record(lengths):
    from playwright.sync_api import sync_playwright
    vid_dir = OUT / "rec"
    for f in vid_dir.glob("*.webm") if vid_dir.exists() else []:
        f.unlink()
    marks = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1,
                                  **({} if FAST else {"record_video_dir": str(vid_dir), "record_video_size": {"width": 1280, "height": 720}}))
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.monotonic()
        demo = Demo(page, lengths)
        for beat_id, _, _ in BEATS:
            start = time.monotonic() - t0
            try:
                getattr(demo, beat_id)()
            except Exception as e:
                print(f"  !! beat {beat_id} failed: {type(e).__name__}: {str(e)[:200]}")
                try:
                    page.screenshot(path=str(OUT / f"fail_{beat_id}.png"))
                except Exception:
                    pass
            need = (0.3 if FAST else lengths[beat_id] + 0.7)
            spent = time.monotonic() - t0 - start
            if spent < need:
                page.wait_for_timeout(int((need - spent) * 1000))
            marks.append((beat_id, start, time.monotonic() - t0))
            print(f"  beat {beat_id:<12} start {start:6.1f}s  length {marks[-1][2] - start:5.1f}s  (speech {lengths[beat_id]:.1f}s)")
        total = time.monotonic() - t0
        ctx.close()
        browser.close()
    if FAST:
        print(f"dry run finished in {total:.0f}s")
        return None
    vids = sorted(vid_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    return vids[-1], marks, total


def mix(video: Path, marks, total):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs, filters, labels = ["-i", str(video)], [], []
    for n, (beat_id, start, _) in enumerate(marks, start=1):
        inputs += ["-i", str(AUDIO / f"{beat_id}.wav")]
        ms = int((start + 0.35) * 1000)
        filters.append(f"[{n}:a]aresample=48000,adelay={ms}:all=1[a{n}]")
        labels.append(f"[a{n}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,volume=1.15[aout]")
    out = OUT / "Lumen_Demo.mp4"
    cmd = [ff, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "27", "-pix_fmt", "yuv420p", "-r", "25",
           "-c:a", "aac", "-b:a", "56k", "-ac", "1", "-t", f"{total + 0.5:.2f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {total / 60:.1f} minutes)")


def main():
    OUT.mkdir(exist_ok=True)
    lengths = json.loads((OUT / "durations.json").read_text()) if (OUT / "durations.json").exists() and "--no-tts" in sys.argv else make_audio()
    write_slides()
    result = record(lengths)
    if result:
        mix(*result)


if __name__ == "__main__":
    main()
