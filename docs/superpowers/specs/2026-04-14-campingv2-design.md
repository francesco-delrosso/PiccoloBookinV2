# CampingV2 — Design Spec

**Date:** 2026-04-14
**Status:** Approved
**Target:** /Users/francescodelrosso/Desktop/CampingV2/

## Overview

Booking management app for Piccolo Camping (small family campsite, Lake Como). Manages email-based reservations: ingest emails via IMAP, classify with Ollama, display as threaded conversations, reply via SMTP with multilingual templates.

Rebuild from scratch. V1 abandoned due to: poor spam filtering, slow email import, unsatisfying UI.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + Python 3 |
| Database | SQLite + SQLAlchemy ORM |
| Frontend | Vue 3 + Vite + Pinia |
| CSS | Tailwind CSS |
| AI | Ollama (default: phi3:mini) |
| Email | imaplib (IMAP) + smtplib (SMTP) |

No authentication. Desktop-only. Single-user local app. All config stored in DB `impostazioni` table (no .env file).

## Color Palette

Nature palette — green, brown, blue. Lake/forest/earth camping feel.

| Token | Role | Hex |
|-------|------|-----|
| primary | Main actions, active states | #2B6B4F (forest green) |
| secondary | Headers, accents | #4A7C9B (lake blue) |
| warm | Highlights, badges | #8B6914 (earth brown) |
| bg | Page background | #F8F6F2 (warm white) |
| surface | Cards, panels | #FFFFFF |
| border | Dividers | #E2DED6 (warm gray) |
| text | Body text | #2C2C2C |
| text-muted | Secondary text | #6B7280 |
| danger | Delete, reject | #DC2626 |
| success | Confirm | #16A34A |
| warning | Pending states | #D97706 |

Defined as Tailwind theme extensions in `tailwind.config.js`.

## Architecture

```
Browser (Vue 3 + Tailwind)
  -> Vite proxy /api/*
    -> FastAPI (uvicorn, port 8000)
      -> SQLite (SQLAlchemy ORM)
      -> IMAP/SMTP (imaplib/smtplib)
      -> Ollama (HTTP, localhost:11434)
```

Single-process. Background email import via FastAPI BackgroundTasks + ThreadPoolExecutor (N workers, default 4) for parallel Ollama calls. Job status tracked in module-level dict, exposed via polling endpoint.

APScheduler runs automatic poll every N minutes (configurable, default 10).

## Data Model

### Prenotazione (one per email thread)

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| tipo_richiesta | String | "Prenotazione" or "Contatto" |
| nome | String | Nullable |
| cognome | String | Nullable |
| telefono | String | Nullable |
| email | String | Nullable |
| data_arrivo | String | YYYY-MM-DD, nullable |
| data_partenza | String | YYYY-MM-DD, nullable |
| adulti | Integer | Nullable |
| bambini | Integer | Nullable |
| posto_per | String | tenda/camper/caravan/bungalow, nullable |
| stato | String | Default "Nuova" |
| costo_totale | Float | Nullable |
| data_ricezione | DateTime | Auto-set |
| message_id | String | Unique, thread root Message-ID |
| lingua_suggerita | String | IT/EN/DE/FR/NL, nullable |

### StoricoMessaggio (one per email in thread)

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| id_prenotazione | Integer FK | Cascade delete |
| mittente | String | "Cliente" or "Campeggio" |
| testo | Text | Email body |
| testo_tradotto | Text | Ollama translation, nullable |
| data_ora | DateTime | Email date |
| message_id | String | Unique, that email's Message-ID |

### Impostazione (key-value config)

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| chiave | String | Unique |
| valore | Text | Nullable |

Price list stored as JSON blob under key `listino_prezzi`.

### ModelloMail (email templates)

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| lingua | String | IT/EN/DE/FR/NL |
| tipo | String | accetta/rifiuta/info |
| soggetto | String | Subject template |
| corpo | Text | Body template |

Template variables: `{nome}`, `{cognome}`, `{data_arrivo}`, `{data_partenza}`, `{adulti}`, `{bambini}`, `{posto_per}`, `{costo_totale}`, `{caparra}`, `{testo_aggiuntivo}`.

## API Endpoints (prefix /api)

### Prenotazioni

| Method | Path | Purpose |
|--------|------|---------|
| GET | /prenotazioni/ | List all bookings |
| GET | /prenotazioni/{id} | Get booking + messaggi |
| PATCH | /prenotazioni/{id} | Update booking fields |
| DELETE | /prenotazioni/{id} | Delete booking + cascade |
| POST | /prenotazioni/{id}/messaggi | Add manual message |
| POST | /prenotazioni/{id}/invia-mail | Send email via SMTP |
| POST | /prenotazioni/{id}/traduci | Translate thread via Ollama |

### Mail

| Method | Path | Purpose |
|--------|------|---------|
| POST | /mail/poll?limit=20 | Quick poll last N emails |
| POST | /mail/import-full?ollama_limit=100&mail_limit=0 | Full history import (background) |
| POST | /mail/reset-reimport?ollama_limit=100 | Delete all + reimport (background) |
| GET | /mail/job-status | Poll background job progress |
| POST | /mail/test-credenziali | Test IMAP/SMTP connection |

### Impostazioni

| Method | Path | Purpose |
|--------|------|---------|
| GET | /impostazioni/ | Get all settings |
| PUT | /impostazioni/ | Update single setting |
| PUT | /impostazioni/batch | Update multiple settings |

### Modelli

| Method | Path | Purpose |
|--------|------|---------|
| GET | /modelli/ | List all templates |
| PUT | /modelli/{id} | Update template |
| GET | /modelli/preview/{id} | Preview with sample data |

### Prezzi

| Method | Path | Purpose |
|--------|------|---------|
| GET | /prezzi/ | Get price list JSON |
| PUT | /prezzi/ | Update price list JSON |

## Email Ingestion Pipeline

### Spam Filter (3 levels)

**Level 1 — Blacklist (instant, before Ollama):**
- Prefix blacklist: noreply@, newsletter@, marketing@, billing@, fatture@, no-reply@, mailer-daemon@, postmaster@, notifications@, alert@, info@ (from known spam domains)
- Domain keyword blacklist: nexi, aruba (configurable via `filtro_domini_scarta`)
- Subject keyword blacklist: Fattura, Rinnovo, Scadenza (configurable via `filtro_oggetto_scarta`)
- Discard immediately. No Ollama call.

**Level 2 — Known client fast-path:**
- If sender email exists in any `Prenotazione.email` → append to that thread, skip Ollama.
- If `In-Reply-To`/`References` match existing `StoricoMessaggio.message_id` → append to thread.

**Level 3 — Ollama classification:**
- Only reached if L1 and L2 don't match.
- Ollama classifies as prenotazione/contatto/spam with confidenza score.
- spam + confidenza >= 0.5 → discard.
- Otherwise create new Prenotazione.

### Thread Reconstruction

1. Batch-fetch IMAP headers (500 at a time) from INBOX + auto-detected Sent folder.
2. Build header map: `{message_id: {from, to, date, subject, in_reply_to, references}}`.
3. `_find_root(message_id)`: walk References chain (first element = root). Fallback: In-Reply-To graph traversal with cycle detection.
4. Group messages by root message_id → each group = one thread.
5. Secondary fallback: normalized subject (strip Re:/Fwd:/AW:/Ri:) + sender email.
6. Fetch bodies only for messages in relevant threads (not all messages).
7. Sent folder emails → `mittente = "Campeggio"`, INBOX → `mittente = "Cliente"`.
8. Deduplication via unique constraint on `StoricoMessaggio.message_id`.

### IMAP Connection Management

- One connection per job (poll/import/reset). No global state.
- Connection opened at job start, closed in finally block.
- `_fetch_body_msg()` handles folder switching (INBOX vs Sent) within single connection.
- Aruba-specific: Sent folder is `INBOX.Sent` (auto-detected via `conn.list()`).

### Background Job Pattern

- `/mail/import-full` and `/mail/reset-reimport` return immediately with `{job_id, status: "running"}`.
- Job runs in BackgroundTasks.
- ThreadPoolExecutor (N workers from `ollama_workers` setting, default 4) for parallel Ollama calls.
- Each worker creates own `SessionLocal()` DB session, closes in finally.
- Job progress tracked in module-level dict: `{job_id: {status, total, processed, errors, started_at}}`.
- Frontend polls `/api/mail/job-status` every 5 seconds until complete.

## Frontend

### Pages

**Dashboard (/):**
- Left sidebar (300px fixed): booking list with search (nome/email), filter by stato dropdown, filter by tipo (Prenotazione/Contatto), status badges with colors.
- Main panel: selected booking detail — all fields editable inline, action buttons (Accetta, Rifiuta, Info, Elimina).
- Below detail: chat-style message history (bubbles left=cliente, right=campeggio).
- Toolbar: Poll button, Import button (with numeric input for limit), Reset button (with confirmation modal).
- Toast notifications for feedback.

**Impostazioni (/impostazioni):**
- Sections: IMAP credentials, SMTP credentials, Ollama config (URL, model, workers), spam filters (domains, subjects), email identity (mittente, form sito), caparra percentage.
- Test connection button for IMAP/SMTP.
- Email template editor: select lingua + tipo, edit soggetto + corpo, preview with sample data.

**Prezzi (/prezzi):**
- Season editor: name, color tag, date ranges.
- Line item editor: category, name, price per season.
- Preloaded with real campsite data.
- Saved as JSON blob.

### State Management (Pinia)

Single store `prenotazioni.js`:
- `list`: all bookings
- `selected`: current booking ID
- `filters`: {stato, tipo, searchText}
- `filtered`: computed — list filtered by active filters
- `jobStatus`: background job polling state
- `selectPrenotazione(id)`: re-fetches from API (fresh messaggi)
- `fetchAll()`: GET /api/prenotazioni

### Routing

| Path | View | Description |
|------|------|-------------|
| / | Dashboard.vue | Main booking view |
| /impostazioni | Impostazioni.vue | Settings page |
| /prezzi | Prezzi.vue | Price list editor |

### Status Badges

| Stato | Color |
|-------|-------|
| Nuova | Blue |
| Nuova Risposta | Blue (pulsing) |
| In lavorazione | Yellow |
| Attesa Bonifico | Orange |
| Confermata | Green |
| Rifiutata | Red |

### Booking Status Flow

```
Nuova -> In lavorazione -> Attesa Bonifico -> Confermata
                       \-> Rifiutata
```

New client reply on any status -> "Nuova Risposta" (auto-set by mail_poller when appending to existing thread).

### Translation Feature

- "Traduci" button on chat panel → POST /prenotazioni/{id}/traduci.
- Ollama translates each message to Italian.
- Stored in `testo_tradotto` column — not recalculated.
- Toggle button switches between original/translated text.

## Folder Structure

```
CampingV2/
  backend/
    main.py              # FastAPI app, CORS, scheduler, migration
    database.py          # SQLite engine, SessionLocal, get_db
    models.py            # SQLAlchemy models
    schemas.py           # Pydantic DTOs
    routers/
      prenotazioni.py
      mail.py
      impostazioni.py
      modelli.py
      prezzi.py
    services/
      mail_poller.py     # IMAP scan, thread reconstruction, spam filter
      mail_sender.py     # SMTP send
      smart_parser.py    # Ollama: parse_email() + translate_to_italian()
  frontend/
    index.html
    package.json
    vite.config.js
    tailwind.config.js
    postcss.config.js
    src/
      main.js
      App.vue
      api/index.js
      router/index.js
      stores/prenotazioni.js
      views/
        Dashboard.vue
        Impostazioni.vue
        Prezzi.vue
      components/
        PrenotazioniList.vue
        DettaglioPrenotazione.vue
        ChatStorico.vue
        ModalAccetta.vue
        ModalRifiuta.vue
        ModalInfo.vue
  start.sh
  CLAUDE.md
```

## Preloaded Settings

| Key | Value |
|-----|-------|
| imap_server | imaps.aruba.it |
| imap_port | 993 |
| imap_user | info@piccolocamping.com |
| imap_password | *(empty)* |
| smtp_server | smtps.aruba.it |
| smtp_port | 587 |
| smtp_user | info@piccolocamping.com |
| smtp_password | *(empty)* |
| email_mittente | info@piccolocamping.com |
| email_form_sito | contatti@piccolocamping.com |
| ollama_url | http://localhost:11434 |
| ollama_model | phi3:mini |
| ollama_workers | 4 |
| caparra_percentuale | 30 |
| filtro_domini_scarta | aruba.it |
| filtro_oggetto_scarta | Fattura,Rinnovo,Scadenza |
| poll_interval_minutes | 10 |

## Technical Notes

- **SQLite migration**: `main.py` runs `ALTER TABLE ... ADD COLUMN` for columns added after initial `create_all`. Wrapped in try/except (column already exists = no-op).
- **IMAP Aruba**: `imaps.aruba.it:993`, Sent folder is `INBOX.Sent`. Auto-detect via `conn.list()`.
- **Ollama JSON safety**: phi3:mini returns lists/dicts for string fields sometimes. Guard with `_str_or_none()` and `_int_or_none()` helpers.
- **SQLAlchemy sessions**: `db.rollback()` in every except handler inside processing loops. ThreadPoolExecutor workers create own sessions.
- **Ollama prompt**: dynamic year (use current year), explicit spam examples, multilingual support. Temperature 0.1, num_predict 512.
- **Vite proxy**: `/api` → `http://localhost:8000` in `vite.config.js`.
- **Axios timeouts**: import endpoints use timeout 0 (no timeout) since backend responds immediately with background=true.
- **HTML stripping**: custom HTMLParser-based stripper for email bodies. Strip quoted text ("> " prefix and "On ... wrote:" patterns in 6 languages).
