import os
import time
import uuid
import logging
import datetime
import threading
import collections
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.graph import ask          # also loads .env
from app.db import q
from app.tools.registry import TOOLS

log = logging.getLogger("cricketiq")
DAILY_CAP = int(os.getenv("DAILY_CAP", "300"))

app = FastAPI(title="CricketIQ API")


# ---------- abuse protection ----------
_hits = collections.defaultdict(collections.deque)
_hits_lock = threading.Lock()

def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")      # set by the host's proxy
    return (fwd or request.client.host).split(",")[0].strip()

def check_ip_limit(ip: str, limit: int = 10, window: int = 60):
    """At most `limit` requests per `window` seconds for each IP address."""
    now = time.time()
    with _hits_lock:
        dq = _hits[ip]
        while dq and now - dq[0] > window:
            dq.popleft()
        if len(dq) >= limit:
            raise HTTPException(429, "Too many requests. Please wait a minute.")
        dq.append(now)
        if len(_hits) > 5000:                          # keep memory bounded
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > window]:
                del _hits[k]

_day, _count, _lock = None, 0, threading.Lock()

def check_daily_cap():
    """Global ceiling, so the worst case is bounded even if per-IP limits are bypassed."""
    global _day, _count
    today = datetime.date.today()
    with _lock:
        if _day != today:
            _day, _count = today, 0
        if _count >= DAILY_CAP:
            raise HTTPException(429, "Daily demo limit reached. Please try again tomorrow.")
        _count += 1

def safe_thread_id(tid):
    """Accept only UUIDs so visitors cannot share or guess a conversation."""
    try:
        return str(uuid.UUID(tid)) if tid else str(uuid.uuid4())
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())


# ---------- schemas ----------
class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    thread_id: str | None = None

class ChatResponse(BaseModel):
    answer: str
    tools_used: list[dict]
    thread_id: str
    latency_ms: int


# ---------- routes ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tools")
def tools():
    return [{"name": t.name, "description": t.description[:120]} for t in TOOLS]

@app.get("/players")
def players():
    batters = q("SELECT DISTINCT batter AS n FROM deliveries ORDER BY n")["n"].tolist()
    bowlers = q("SELECT DISTINCT bowler AS n FROM deliveries ORDER BY n")["n"].tolist()
    return {"batters": batters, "bowlers": bowlers}

_agent_slots = threading.BoundedSemaphore(int(os.getenv("MAX_CONCURRENT", "2")))

@app.post("/chat", response_model=ChatResponse)
def chat(request: Request, req: ChatRequest):
    check_ip_limit(client_ip(request), limit=5)
    check_daily_cap()
    tid = safe_thread_id(req.thread_id)
    t0 = time.time()
    if not _agent_slots.acquire(timeout=25):
        raise HTTPException(503, "The analyst is busy right now. Please try again in a few seconds.")
    try:
        answer, used = ask(req.question, tid)
    except groq.RateLimitError:
        raise HTTPException(503, "The demo is busy right now. Please try again in a few seconds.")
    except Exception:
        log.exception("chat failed")
        raise HTTPException(500, "The analyst hit an error. Please try again.")
    finally:
        _agent_slots.release()
    return ChatResponse(answer=answer, tools_used=used, thread_id=tid,
                        latency_ms=int((time.time() - t0) * 1000))


# ---------- static UI (keep this LAST) ----------
STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")