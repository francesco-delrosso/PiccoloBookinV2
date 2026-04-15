"""
Mail router — poll, full import, reset/reimport, job status, credential tests.
"""

import threading
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Impostazione
from services.mail_poller import poll_emails, import_full_history, reset_and_reimport
from services.mail_sender import test_smtp, test_imap

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level job state + lock
# ---------------------------------------------------------------------------
_job_state: dict = {
    "job_id": None,
    "status": "idle",
    "total": 0,
    "processed": 0,
    "errors": [],
    "started_at": None,
}
_job_lock = threading.Lock()


def _load_settings(db: Session) -> dict:
    rows = db.query(Impostazione).all()
    return {r.chiave: r.valore for r in rows}


# ---------------------------------------------------------------------------
# Background task wrappers
# ---------------------------------------------------------------------------
def _run_import_full(mail_limit: int, ollama_limit: int):
    """Background task for full import."""
    global _job_state
    try:
        result = import_full_history(
            db=None,
            mail_limit=mail_limit,
            ollama_limit=ollama_limit,
            job_state=_job_state,
        )
        with _job_lock:
            _job_state["status"] = "done"
            if result.get("errors"):
                _job_state["errors"] = result["errors"][-10:]
    except Exception as e:
        with _job_lock:
            _job_state["status"] = "error"
            _job_state["errors"].append(str(e))


def _run_reset_reimport(ollama_limit: int):
    """Background task for reset + reimport."""
    global _job_state
    try:
        result = reset_and_reimport(
            db=None,
            ollama_limit=ollama_limit,
            job_state=_job_state,
        )
        with _job_lock:
            _job_state["status"] = "done"
            if result.get("errors"):
                _job_state["errors"] = result["errors"][-10:]
    except Exception as e:
        with _job_lock:
            _job_state["status"] = "error"
            _job_state["errors"].append(str(e))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/poll")
def trigger_poll(limit: int = 20, db: Session = Depends(get_db)):
    """Synchronous poll — calls poll_emails directly."""
    return poll_emails(db, limit=limit)


@router.post("/import-full")
def trigger_import_full(
    mail_limit: int = 0,
    ollama_limit: int = 100,
    background_tasks: BackgroundTasks = None,
):
    """Start full import in background. Returns immediately."""
    global _job_state
    with _job_lock:
        if _job_state["status"] not in ("idle", "done", "error"):
            return {
                "success": False,
                "message": "Un job e' gia' in esecuzione",
                "job_id": _job_state["job_id"],
            }
        _job_state = {
            "job_id": str(uuid4()),
            "status": "starting",
            "total": 0,
            "processed": 0,
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        job_id = _job_state["job_id"]

    if background_tasks is not None:
        background_tasks.add_task(_run_import_full, mail_limit, ollama_limit)
    else:
        t = threading.Thread(
            target=_run_import_full, args=(mail_limit, ollama_limit), daemon=True
        )
        t.start()

    return {
        "success": True,
        "message": "Import avviato in background",
        "job_id": job_id,
    }


@router.post("/reset-reimport")
def trigger_reset_reimport(
    ollama_limit: int = 100,
    background_tasks: BackgroundTasks = None,
):
    """Reset all data and reimport. Returns immediately."""
    global _job_state
    with _job_lock:
        if _job_state["status"] not in ("idle", "done", "error"):
            return {
                "success": False,
                "message": "Un job e' gia' in esecuzione",
                "job_id": _job_state["job_id"],
            }
        _job_state = {
            "job_id": str(uuid4()),
            "status": "starting",
            "total": 0,
            "processed": 0,
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        job_id = _job_state["job_id"]

    if background_tasks is not None:
        background_tasks.add_task(_run_reset_reimport, ollama_limit)
    else:
        t = threading.Thread(
            target=_run_reset_reimport, args=(ollama_limit,), daemon=True
        )
        t.start()

    return {
        "success": True,
        "message": "Reset e reimport avviato in background",
        "job_id": job_id,
    }


@router.get("/job-status")
def get_job_status():
    """Return current job state (last 10 errors)."""
    with _job_lock:
        state = dict(_job_state)
        # Limit errors to last 10
        if state.get("errors"):
            state["errors"] = state["errors"][-10:]
        return state


@router.post("/test-credenziali")
def test_credenziali(db: Session = Depends(get_db)):
    """Test IMAP + SMTP credentials from saved settings."""
    settings = _load_settings(db)
    imap_result = test_imap(settings)
    smtp_result = test_smtp(settings)
    return {
        "imap": imap_result,
        "smtp": smtp_result,
    }
