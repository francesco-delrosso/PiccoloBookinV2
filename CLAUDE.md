# CLAUDE.md

## Running the App

```bash
bash start.sh
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

**Backend only:**
```bash
cd backend && source venv/bin/activate && python3 -m uvicorn main:app --reload --port 8000
```

**Frontend only:**
```bash
cd frontend && npm run dev
```

No test suite exists.

## Architecture

**Stack:** FastAPI + SQLite (SQLAlchemy) backend, Vue 3 + Pinia + Vite + Tailwind CSS v4 frontend. All config stored in `impostazioni` SQLite table as key-value pairs (no .env file).

**Frontend -> Backend:** Vite proxies `/api/*` to `http://localhost:8000`.

**Email pipeline** (`backend/services/mail_poller.py`):
1. Level 1 spam filter: prefix/domain/subject blacklists (instant discard)
2. Level 2 fast-path: known client email or existing thread -> append, skip Ollama
3. Level 3: Ollama classifies remaining emails as prenotazione/contatto/spam

**Thread reconstruction:** batch-fetch IMAP headers (500/batch) from INBOX + Sent, group by References/In-Reply-To chain, fallback to normalized subject + sender.

**Background jobs:** FastAPI BackgroundTasks + ThreadPoolExecutor for parallel Ollama. Frontend polls `/api/mail/job-status` every 5s.

**Booking status flow:** Nuova -> In lavorazione -> Attesa Bonifico -> Confermata (or -> Rifiutata). Client reply auto-sets "Nuova Risposta".

## Key Settings Keys

| Key | Purpose |
|-----|---------|
| `imap_server/port/user/password` | IMAP credentials |
| `smtp_server/port/user/password` | SMTP credentials |
| `email_mittente` | From address for outbound |
| `email_form_sito` | Website contact form address |
| `ollama_url` / `ollama_model` | Ollama endpoint and model |
| `ollama_workers` | Parallel Ollama threads (default 4) |
| `filtro_domini_scarta` | Comma-separated domain fragments to discard |
| `filtro_oggetto_scarta` | Comma-separated subject fragments to discard |
| `poll_interval_minutes` | Auto-poll interval |
| `caparra_percentuale` | Deposit percentage |
| `listino_prezzi` | JSON blob for price list |
