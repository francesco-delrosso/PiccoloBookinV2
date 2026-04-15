"""
Mail Poller Service — IMAP scanning, thread reconstruction, spam filtering,
parallel Ollama classification.

Public API:
  poll_emails(db, limit=20)          — quick sync poll
  import_full_history(db, ...)       — full background import
  reset_and_reimport(db, ...)        — wipe + re-import
"""

import email
import email.utils
import email.header
import imaplib
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser

from database import SessionLocal
from models import Prenotazione, StoricoMessaggio, Impostazione
from services.smart_parser import parse_email

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_NOREPLY_PREFIXES = [
    "noreply", "no-reply", "no.reply", "donotreply", "do-not-reply",
    "newsletter", "marketing", "billing", "fatture", "invoice",
    "mailer-daemon", "postmaster", "notifications", "notification",
    "alert", "alerts", "bounce", "support@nexi", "noreply@nexi",
    "automailer", "daemon", "system",
]

_SPAM_DOMAIN_KEYWORDS = [
    "nexi.", "paypal.", "stripe.", "sendgrid.", "mailchimp.",
    "constantcontact.", "hubspot.", "salesforce.",
]

_QUOTE_PATTERNS = [
    # English: "On ... wrote:"
    re.compile(r"^On .{5,150} wrote:\s*$", re.IGNORECASE),
    # Italian: "Il ... ha scritto:"
    re.compile(r"^Il .{5,150} ha scritto:\s*$", re.IGNORECASE),
    # German: "Am ... schrieb:"
    re.compile(r"^Am .{5,150} schrieb\s?.*:\s*$", re.IGNORECASE),
    # French: "Le ... a écrit:"
    re.compile(r"^Le .{5,150} a .crit\s?.*:\s*$", re.IGNORECASE),
    # Dutch: "Op ... schreef:"
    re.compile(r"^Op .{5,150} schreef\s?.*:\s*$", re.IGNORECASE),
    # Spanish: "El ... escribió:"
    re.compile(r"^El .{5,150} escribi.:\s*$", re.IGNORECASE),
    # Generic "From:" / "Da:" / "Von:" / "De:" / "Van:" header in quoted text
    re.compile(r"^(Da|From|Von|De|Van)\s*:", re.IGNORECASE),
]

_SUBJECT_STRIP_RE = re.compile(
    r"^(re|fwd|fw|aw|ri|i|sv|vs|tr|wg)\s*(\[\d+\])?\s*:\s*",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------
class _HTMLStripper(HTMLParser):
    """Subclass that collects text fragments from HTML."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"[ \t]+", " ", "\n".join(self._parts)).strip()


def _strip_html(html_text: str) -> str:
    """Strip HTML tags, return plain text."""
    try:
        stripper = _HTMLStripper()
        stripper.feed(html_text)
        return stripper.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html_text).strip()


def _strip_quoted_text(text: str) -> str:
    """Remove quoted text from an email body."""
    lines = text.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Lines starting with ">"
        if stripped.startswith(">"):
            continue
        # Check quote patterns — if matched, stop collecting
        if any(pat.match(stripped) for pat in _QUOTE_PATTERNS):
            break
        clean.append(line)
    # Trim trailing blank lines
    while clean and not clean[-1].strip():
        clean.pop()
    return "\n".join(clean)


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------
def _decode_header(raw: str | None) -> str:
    """Decode a MIME-encoded header string."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    result: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result).strip()


def _extract_email_addr(raw: str | None) -> str:
    """Extract just the email address from a header, lowercased."""
    if not raw:
        return ""
    decoded = _decode_header(raw)
    _, addr = email.utils.parseaddr(decoded)
    return addr.lower()


def _parse_date(raw: str | None) -> datetime:
    """Parse an email Date header to datetime (UTC). Falls back to now."""
    if raw:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            pass
        try:
            from email.utils import parsedate
            t = parsedate(raw)
            if t:
                return datetime(*t[:6])
        except Exception:
            pass
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd:/AW:/etc. prefixes recursively, lowercase."""
    s = subject.strip()
    prev = None
    while s != prev:
        prev = s
        s = _SUBJECT_STRIP_RE.sub("", s).strip()
    return s.lower()


def _clean_message_id(raw: str | None) -> str | None:
    """Strip angle brackets, return clean message-id or None."""
    if not raw:
        return None
    cleaned = raw.strip().strip("<>").strip()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Spam filter (Level 1)
# ---------------------------------------------------------------------------
def _discard(from_addr: str, subject: str, settings: dict) -> bool:
    """Level 1 spam filter. Returns True to discard the message."""
    addr = from_addr.lower()
    local_part = addr.split("@")[0] if "@" in addr else addr

    # Prefix blacklist
    for prefix in _NOREPLY_PREFIXES:
        if "@" in prefix:
            # Full prefix like "support@nexi"
            if addr.startswith(prefix):
                logger.info("L1 scartata (prefix): %s", from_addr)
                return True
        else:
            if local_part == prefix or local_part.startswith(prefix):
                logger.info("L1 scartata (prefix): %s", from_addr)
                return True

    # Built-in domain keywords
    for kw in _SPAM_DOMAIN_KEYWORDS:
        if kw in addr:
            logger.info("L1 scartata (domain kw): %s", from_addr)
            return True

    # User-configurable domain filter
    filtro_domini = settings.get("filtro_domini_scarta", "")
    for d in [x.strip().lower() for x in filtro_domini.split(",") if x.strip()]:
        if d in addr:
            logger.info("L1 scartata (dominio utente): %s", from_addr)
            return True

    # User-configurable subject filter
    filtro_oggetti = settings.get("filtro_oggetto_scarta", "")
    subj_lower = subject.lower()
    for o in [x.strip().lower() for x in filtro_oggetti.split(",") if x.strip()]:
        if o in subj_lower:
            logger.info("L1 scartata (oggetto '%s'): %s", o, subject)
            return True

    return False


# ---------------------------------------------------------------------------
# IMAP operations
# ---------------------------------------------------------------------------
def _connect_imap(settings: dict) -> imaplib.IMAP4:
    """Create a new IMAP4_SSL connection and login."""
    server = settings.get("imap_server", "")
    port = int(settings.get("imap_port", "993"))
    user = settings.get("imap_user", "")
    password = settings.get("imap_password", "")

    if port == 993:
        conn = imaplib.IMAP4_SSL(server, port, timeout=30)
    else:
        conn = imaplib.IMAP4(server, port, timeout=30)
        conn.starttls()
    conn.login(user, password)
    logger.info("IMAP connesso: %s:%d", server, port)
    return conn


def _find_sent_folder(conn: imaplib.IMAP4) -> str | None:
    """Auto-detect the Sent folder from IMAP LIST response."""
    try:
        _, folder_list = conn.list()
        candidates: list[str] = []
        for item in (folder_list or []):
            decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            m = re.search(r'"([^"]+)"\s*$', decoded) or re.search(r"(\S+)\s*$", decoded)
            if m:
                name = m.group(1).strip('"')
                if re.search(r"sent|invia|envoy|verzonden|gesendet|outbox", name, re.IGNORECASE):
                    candidates.append(name)
        if candidates:
            for preferred in ("Sent", "INBOX.Sent", "Posta inviata"):
                if preferred in candidates:
                    return preferred
            return candidates[0]
    except Exception as e:
        logger.debug("_find_sent_folder error: %s", e)
    return None


_HEADER_FETCH_CMD = (
    "(BODY.PEEK[HEADER.FIELDS "
    "(FROM TO SUBJECT MESSAGE-ID DATE IN-REPLY-TO REFERENCES)])"
)


def _batch_fetch_headers(
    conn: imaplib.IMAP4, folder: str, limit: int = 0, batch_size: int = 500
) -> dict[str, dict]:
    """Fetch headers in batches using BODY.PEEK.

    Returns dict keyed by message_id:
    {message_id: {from_addr, from_raw, to, date, subject, message_id,
                  in_reply_to, references, folder, uid}}
    """
    result: dict[str, dict] = {}
    try:
        conn.select(folder, readonly=True)
        _, data = conn.search(None, "ALL")
        ids = data[0].split() if data[0] else []
        if limit and limit > 0:
            ids = ids[-limit:]
        total = len(ids)

        for i in range(0, total, batch_size):
            batch = ids[i : i + batch_size]
            id_set = b",".join(batch)
            try:
                _, hdr_data = conn.fetch(id_set, _HEADER_FETCH_CMD)
                j = 0
                for item in hdr_data:
                    if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                        uid = batch[j] if j < len(batch) else b"?"
                        j += 1
                        hdr = _parse_header_bytes(item[1], uid, folder)
                        if hdr and hdr["message_id"]:
                            result[hdr["message_id"]] = hdr
                        elif hdr:
                            # No message_id — use a synthetic key
                            synth = f"_no_mid_{folder}_{uid}"
                            hdr["message_id"] = synth
                            result[synth] = hdr
            except Exception as ex:
                logger.debug("Batch header error %s [%d:%d]: %s", folder, i, i + batch_size, ex)
                # Fallback: one-by-one
                for uid in batch:
                    try:
                        _, hd = conn.fetch(uid, _HEADER_FETCH_CMD)
                        if hd and isinstance(hd[0], tuple):
                            hdr = _parse_header_bytes(hd[0][1], uid, folder)
                            if hdr and hdr["message_id"]:
                                result[hdr["message_id"]] = hdr
                    except Exception:
                        pass

            if total > batch_size and (i // batch_size) % 5 == 0:
                logger.info("%s: %d/%d headers scanned", folder, min(i + batch_size, total), total)

    except Exception as ex:
        logger.warning("Cannot read folder %r: %s", folder, ex)
    return result


def _parse_header_bytes(raw: bytes, uid, folder: str) -> dict | None:
    """Parse raw header bytes into a structured dict."""
    try:
        msg = email.message_from_bytes(raw)
        mid_raw = msg.get("Message-ID", "")
        mid = _clean_message_id(mid_raw)

        return {
            "from_addr": _extract_email_addr(msg.get("From")),
            "from_raw": _decode_header(msg.get("From")),
            "to": _extract_email_addr(msg.get("To")),
            "date": _parse_date(msg.get("Date")),
            "subject": _decode_header(msg.get("Subject", "")),
            "message_id": mid,
            "in_reply_to": _clean_message_id(msg.get("In-Reply-To")),
            "references": msg.get("References", "").strip(),
            "folder": folder,
            "uid": uid,
        }
    except Exception:
        return None


def _fetch_body(conn: imaplib.IMAP4, uid, folder: str) -> str:
    """Fetch full email body, handle multipart, strip HTML/quoted text."""
    conn.select(folder, readonly=True)
    _, raw_data = conn.fetch(uid, "(RFC822)")
    msg = email.message_from_bytes(raw_data[0][1])

    plain = None
    html = None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            try:
                decoded = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                ).strip()
            except Exception:
                continue
            if ct == "text/plain" and plain is None:
                plain = decoded
            elif ct == "text/html" and html is None:
                html = decoded
    else:
        try:
            decoded = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            ).strip()
            if msg.get_content_type() == "text/html":
                html = decoded
            else:
                plain = decoded
        except Exception:
            pass

    if plain:
        return _strip_quoted_text(plain)
    if html:
        return _strip_quoted_text(_strip_html(html))
    return str(msg.get_payload())


# ---------------------------------------------------------------------------
# Thread reconstruction
# ---------------------------------------------------------------------------
def _find_root(msg_id: str, header_map: dict[str, dict]) -> str:
    """Walk References chain to find the thread root. First ref = root."""
    visited: set[str] = set()
    current = msg_id

    while current not in visited:
        if current not in header_map:
            return current
        visited.add(current)
        hdr = header_map[current]

        # References: first element is the root
        refs = hdr["references"].split()
        cleaned_refs = [_clean_message_id(r) for r in refs]
        cleaned_refs = [r for r in cleaned_refs if r]
        if cleaned_refs:
            return cleaned_refs[0]

        # Fallback: In-Reply-To
        irt = hdr["in_reply_to"]
        if irt and irt in header_map:
            current = irt
            continue

        return current

    return current  # cycle detected


def _group_threads(header_map: dict[str, dict]) -> dict[str, list[str]]:
    """Group all messages into threads.

    Returns {root_id: [msg_id1, msg_id2, ...]}.
    Secondary fallback: merge orphan threads with same normalized subject + sender.
    Sort each thread chronologically.
    """
    threads: dict[str, list[str]] = {}
    msg_to_root: dict[str, str] = {}

    for msg_id in header_map:
        root = _find_root(msg_id, header_map)
        msg_to_root[msg_id] = root
        threads.setdefault(root, []).append(msg_id)

    # Secondary fallback: merge single-message orphan threads by subject+sender
    subject_groups: dict[str, list[str]] = {}
    for root_id, members in list(threads.items()):
        if len(members) == 1:
            hdr = header_map[members[0]]
            norm_subj = _normalize_subject(hdr["subject"])
            if norm_subj:
                sender = hdr["from_addr"]
                key = f"{sender}:{norm_subj}"
                subject_groups.setdefault(key, []).append(root_id)

    for key, root_ids in subject_groups.items():
        if len(root_ids) > 1:
            # Merge into the first root
            primary = root_ids[0]
            for other in root_ids[1:]:
                threads[primary].extend(threads.pop(other))

    # Sort each thread chronologically
    fallback_dt = datetime(1970, 1, 1)
    for root_id, members in threads.items():
        members.sort(key=lambda mid: header_map[mid]["date"] or fallback_dt)

    return threads


# ---------------------------------------------------------------------------
# Settings helper
# ---------------------------------------------------------------------------
def _load_settings(db) -> dict:
    """Query all Impostazione rows, return dict."""
    rows = db.query(Impostazione).all()
    return {r.chiave: r.valore for r in rows}


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------
def _determine_mittente(from_addr: str, settings: dict) -> str:
    """Returns 'Campeggio' if from campsite emails, else 'Cliente'."""
    camping_addrs = {
        settings.get("imap_user", "").lower(),
        settings.get("email_mittente", "").lower(),
        settings.get("smtp_user", "").lower(),
        settings.get("email_form_sito", "").lower(),
    }
    camping_addrs.discard("")
    return "Campeggio" if from_addr.lower() in camping_addrs else "Cliente"


def _str_or_none(v):
    """Coerce LLM output to str | None — guards against list/dict."""
    if v is None:
        return None
    if isinstance(v, list):
        return " ".join(str(x) for x in v) if v else None
    if isinstance(v, dict):
        return None
    s = str(v).strip()
    return s if s else None


def _int_or_none(v):
    """Coerce to int | None."""
    if v is None:
        return None
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return None
    return None


def _fix_dates(parsed: dict) -> dict:
    """If arrivo > partenza, swap them."""
    arr = parsed.get("data_arrivo")
    dep = parsed.get("data_partenza")
    if arr and dep:
        try:
            from datetime import date
            arr_d = date.fromisoformat(str(arr))
            dep_d = date.fromisoformat(str(dep))
            if arr_d > dep_d:
                parsed["data_arrivo"], parsed["data_partenza"] = dep, arr
        except Exception:
            pass
    return parsed


def _process_thread_with_ollama(
    root_id: str,
    thread_msgs: list[str],
    header_map: dict[str, dict],
    bodies: dict[str, str],
    settings: dict,
) -> dict | None:
    """Call parse_email on the first message body.

    Returns parsed dict or None if spam (confidenza >= 0.5).
    """
    # Find first customer message
    first_msg_id = None
    for mid in thread_msgs:
        hdr = header_map[mid]
        if _determine_mittente(hdr["from_addr"], settings) == "Cliente":
            first_msg_id = mid
            break
    if not first_msg_id or first_msg_id not in bodies:
        return None

    hdr = header_map[first_msg_id]
    body = bodies[first_msg_id]
    full_text = f"Oggetto: {hdr['subject']}\n\n{body}"

    try:
        parsed = parse_email(hdr["from_addr"], hdr["subject"], body, settings)
    except Exception as ex:
        logger.error("Ollama error for %s: %s", root_id, ex)
        return None

    if parsed.get("tipo") == "spam" and parsed.get("confidenza", 0) >= 0.5:
        logger.info("L2/Ollama spam: %s (%.2f)", hdr["from_addr"], parsed.get("confidenza", 0))
        return None

    return _fix_dates(parsed)


def _already_processed(db, message_id: str) -> bool:
    """Check if this message_id already exists in Prenotazione or StoricoMessaggio."""
    if not message_id or message_id.startswith("_no_mid_"):
        return False
    if db.query(Prenotazione).filter_by(message_id=message_id).first():
        return True
    if db.query(StoricoMessaggio).filter_by(message_id=message_id).first():
        return True
    return False


def _save_thread(
    db,
    root_id: str,
    thread_msgs: list[str],
    header_map: dict[str, dict],
    bodies: dict[str, str],
    parsed: dict,
    settings: dict,
) -> Prenotazione | None:
    """Create Prenotazione + StoricoMessaggio rows for a new thread.

    Normalize tipo_richiesta to 'Prenotazione' or 'Contatto'.
    Skip if StoricoMessaggio.message_id already exists.
    """
    # Find first customer message for the Prenotazione
    first_cust_id = None
    first_cust_addr = ""
    for mid in thread_msgs:
        hdr = header_map[mid]
        if _determine_mittente(hdr["from_addr"], settings) == "Cliente":
            first_cust_id = mid
            first_cust_addr = hdr["from_addr"]
            break

    if not first_cust_id:
        return None
    if _already_processed(db, first_cust_id):
        return None

    tipo = "Prenotazione" if parsed.get("tipo") == "prenotazione" else "Contatto"

    pren = Prenotazione(
        tipo_richiesta=tipo,
        nome=_str_or_none(parsed.get("nome")),
        cognome=_str_or_none(parsed.get("cognome")),
        telefono=_str_or_none(parsed.get("telefono")),
        email=first_cust_addr,
        data_arrivo=_str_or_none(parsed.get("data_arrivo")),
        data_partenza=_str_or_none(parsed.get("data_partenza")),
        adulti=_int_or_none(parsed.get("adulti")),
        bambini=_int_or_none(parsed.get("bambini")),
        posto_per=_str_or_none(parsed.get("posto_per")),
        stato="Nuova",
        message_id=first_cust_id,
        lingua_suggerita=_str_or_none(parsed.get("lingua")) or "IT",
    )
    db.add(pren)
    db.flush()

    # Add all messages
    for mid in thread_msgs:
        if _already_processed(db, mid):
            continue
        if mid not in bodies:
            continue
        hdr = header_map[mid]
        mitt = _determine_mittente(hdr["from_addr"], settings)
        db.add(StoricoMessaggio(
            id_prenotazione=pren.id,
            mittente=mitt,
            testo=bodies[mid],
            message_id=mid if not mid.startswith("_no_mid_") else None,
            data_ora=hdr["date"],
        ))

    db.commit()
    return pren


def _append_to_thread(
    db,
    pren: Prenotazione,
    msg_ids: list[str],
    header_map: dict[str, dict],
    bodies: dict[str, str],
    settings: dict,
) -> int:
    """Append new messages to an existing thread.

    Auto-set stato to 'Nuova Risposta' if a client replies.
    Returns number of messages added.
    """
    added = 0
    client_replied = False
    for mid in msg_ids:
        if _already_processed(db, mid):
            continue
        if mid not in bodies:
            continue
        hdr = header_map[mid]
        mitt = _determine_mittente(hdr["from_addr"], settings)
        if mitt == "Cliente":
            client_replied = True
        db.add(StoricoMessaggio(
            id_prenotazione=pren.id,
            mittente=mitt,
            testo=bodies[mid],
            message_id=mid if not mid.startswith("_no_mid_") else None,
            data_ora=hdr["date"],
        ))
        added += 1

    if added:
        if client_replied:
            pren.stato = "Nuova Risposta"
        db.commit()
    return added


# ---------------------------------------------------------------------------
# DB lookup helpers
# ---------------------------------------------------------------------------
def _find_pren_by_message_id(db, message_id: str) -> Prenotazione | None:
    """Return Prenotazione that contains this message_id (own or in storico)."""
    if not message_id:
        return None
    p = db.query(Prenotazione).filter_by(message_id=message_id).first()
    if p:
        return p
    m = db.query(StoricoMessaggio).filter_by(message_id=message_id).first()
    if m:
        return db.query(Prenotazione).filter_by(id=m.id_prenotazione).first()
    return None


def _known_client(db, from_email: str) -> Prenotazione | None:
    """Find the most recent Prenotazione from this email address."""
    return (
        db.query(Prenotazione)
        .filter(Prenotazione.email.ilike(from_email))
        .order_by(Prenotazione.data_ricezione.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Public API — poll_emails
# ---------------------------------------------------------------------------
def poll_emails(db, limit: int = 20) -> dict:
    """Quick synchronous poll: fetch last N messages from INBOX + Sent,
    group into threads, process each.

    Levels:
      L1 — spam filter (_discard)
      L2 — known thread / known client
      L3 — Ollama classification
    """
    settings = _load_settings(db)

    imap_server = settings.get("imap_server", "")
    imap_user = settings.get("imap_user", "")
    imap_password = settings.get("imap_password", "")

    if not all([imap_server, imap_user, imap_password]):
        return {"success": False, "message": "Credenziali IMAP non configurate", "processed": 0}

    conn = None
    processed = 0
    errors: list[str] = []

    try:
        conn = _connect_imap(settings)

        # Fetch headers from INBOX (limited)
        header_map = _batch_fetch_headers(conn, "INBOX", limit=limit)
        logger.info("Poll: INBOX %d headers", len(header_map))

        # Fetch headers from Sent (limited)
        sent_folder = _find_sent_folder(conn)
        if sent_folder:
            sent_headers = _batch_fetch_headers(conn, sent_folder, limit=limit)
            logger.info("Poll: %s %d headers", sent_folder, len(sent_headers))
            header_map.update(sent_headers)

        # Group into threads
        threads = _group_threads(header_map)
        logger.info("Poll: %d threads identified", len(threads))

        for root_id, members in threads.items():
            try:
                # Find first customer message
                first_cust_id = None
                for mid in members:
                    hdr = header_map[mid]
                    if _determine_mittente(hdr["from_addr"], settings) == "Cliente":
                        first_cust_id = mid
                        break
                if not first_cust_id:
                    continue

                first_hdr = header_map[first_cust_id]
                customer_email = first_hdr["from_addr"]
                subject = first_hdr["subject"]

                # All messages already known?
                all_known = all(_already_processed(db, mid) for mid in members)
                if all_known:
                    continue

                # L1 — spam filter
                if _discard(customer_email, subject, settings):
                    continue

                # L2 — check if any message belongs to a known thread
                pren = None
                for mid in members:
                    pren = _find_pren_by_message_id(db, mid)
                    if pren:
                        break
                if not pren:
                    pren = _known_client(db, customer_email)

                if pren is not None:
                    # Append new messages
                    new_mids = [mid for mid in members if not _already_processed(db, mid)]
                    if new_mids:
                        bodies = {}
                        for mid in new_mids:
                            try:
                                hdr = header_map[mid]
                                bodies[mid] = _fetch_body(conn, hdr["uid"], hdr["folder"])
                            except Exception as ex:
                                logger.error("Poll body fetch error: %s", ex)
                        added = _append_to_thread(db, pren, new_mids, header_map, bodies, settings)
                        if added:
                            processed += 1
                            logger.info("Poll L2: +%d msgs to thread #%d", added, pren.id)
                    continue

                # L3 — Ollama classification for unknown sender
                if _already_processed(db, first_cust_id):
                    continue

                # Fetch bodies for the thread
                bodies = {}
                for mid in members:
                    if not _already_processed(db, mid):
                        try:
                            hdr = header_map[mid]
                            bodies[mid] = _fetch_body(conn, hdr["uid"], hdr["folder"])
                        except Exception as ex:
                            logger.error("Poll body fetch error: %s", ex)

                parsed = _process_thread_with_ollama(root_id, members, header_map, bodies, settings)
                if parsed is None:
                    continue  # spam or error

                pren = _save_thread(db, root_id, members, header_map, bodies, parsed, settings)
                if pren:
                    processed += 1
                    logger.info("Poll L3: new thread #%d from %s", pren.id, customer_email)

            except Exception as ex:
                logger.error("Poll thread error: %s", ex)
                errors.append(str(ex))
                try:
                    db.rollback()
                except Exception:
                    pass

        return {
            "success": True,
            "message": f"Poll completato: {processed} thread processati",
            "processed": processed,
            "errors": errors,
        }

    except imaplib.IMAP4.error as e:
        return {"success": False, "message": f"Errore IMAP: {e}", "processed": 0}
    except Exception as e:
        logger.error("Poll error: %s", e)
        return {"success": False, "message": str(e), "processed": 0}
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public API — import_full_history
# ---------------------------------------------------------------------------
def import_full_history(
    db=None,
    mail_limit: int = 0,
    ollama_limit: int = 100,
    job_state: dict | None = None,
) -> dict:
    """Full background import.

    Creates own session if db is None. Fetches all headers, groups threads,
    categorizes (skip existing, L1 filter, L2 known, queue for Ollama).
    Processes Ollama queue in parallel with ThreadPoolExecutor.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()

    def _update_state(**kwargs):
        if job_state is not None:
            job_state.update(kwargs)

    conn = None
    try:
        settings = _load_settings(db)

        imap_server = settings.get("imap_server", "")
        imap_user = settings.get("imap_user", "")
        imap_password = settings.get("imap_password", "")

        if not all([imap_server, imap_user, imap_password]):
            _update_state(status="error")
            return {"success": False, "message": "Credenziali IMAP non configurate", "processed": 0}

        _update_state(status="scanning")

        # Phase 1: fetch all headers
        conn = _connect_imap(settings)

        header_map = _batch_fetch_headers(conn, "INBOX", limit=mail_limit)
        logger.info("[FULL] INBOX: %d headers%s", len(header_map),
                     f" (last {mail_limit})" if mail_limit else "")

        sent_folder = _find_sent_folder(conn)
        if sent_folder:
            sent_headers = _batch_fetch_headers(conn, sent_folder, limit=0)
            logger.info("[FULL] Sent (%s): %d headers", sent_folder, len(sent_headers))
            header_map.update(sent_headers)
        else:
            logger.info("[FULL] Sent folder not found — INBOX only")

        # Phase 2: group threads
        threads = _group_threads(header_map)
        logger.info("[FULL] Threads identified: %d", len(threads))

        _update_state(total=len(threads), status="processing")

        # Phase 3: categorize threads
        ollama_queue: list[tuple] = []  # (root_id, members, bodies, customer_email)
        processed_threads = 0
        processed_msgs = 0
        ollama_used = 0
        errors: list[str] = []

        for root_id, members in threads.items():
            try:
                # Find first customer message
                first_cust_id = None
                customer_email = ""
                subject = ""
                for mid in members:
                    hdr = header_map[mid]
                    if _determine_mittente(hdr["from_addr"], settings) == "Cliente":
                        first_cust_id = mid
                        customer_email = hdr["from_addr"]
                        subject = hdr["subject"]
                        break

                if not first_cust_id:
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                # L1 — spam filter
                if _discard(customer_email, subject, settings):
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                # Check if any message belongs to a known thread
                pren = None
                for mid in members:
                    pren = _find_pren_by_message_id(db, mid)
                    if pren:
                        break
                if not pren:
                    pren = _known_client(db, customer_email)

                if pren is not None:
                    # L2 — append new messages to existing thread (sequential, needs IMAP)
                    new_mids = [mid for mid in members if not _already_processed(db, mid)]
                    if new_mids:
                        bodies = {}
                        for mid in new_mids:
                            try:
                                hdr = header_map[mid]
                                bodies[mid] = _fetch_body(conn, hdr["uid"], hdr["folder"])
                            except Exception as ex:
                                logger.error("[FULL-L2] body error: %s", ex)
                        added = _append_to_thread(db, pren, new_mids, header_map, bodies, settings)
                        if added:
                            processed_threads += 1
                            processed_msgs += added
                            logger.info("[FULL-L2] %s: +%d msgs to #%d", customer_email, added, pren.id)
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                # New thread — queue for Ollama
                if ollama_used >= ollama_limit:
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue
                if _already_processed(db, first_cust_id):
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                # Pre-fetch bodies (IMAP is not thread-safe — sequential)
                bodies: dict[str, str] = {}
                for mid in members:
                    if not _already_processed(db, mid):
                        try:
                            hdr = header_map[mid]
                            bodies[mid] = _fetch_body(conn, hdr["uid"], hdr["folder"])
                        except Exception as ex:
                            logger.error("[FULL] body fetch error: %s", ex)

                if first_cust_id not in bodies:
                    _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                ollama_queue.append((root_id, members, bodies, customer_email))
                ollama_used += 1

            except Exception as ex:
                logger.error("[FULL] thread prep error: %s", ex)
                errors.append(str(ex))
                try:
                    db.rollback()
                except Exception:
                    pass

        # Close IMAP before Ollama processing (no longer needed)
        if conn:
            try:
                conn.logout()
            except Exception:
                pass
            conn = None

        logger.info("[FULL] %d threads queued for Ollama", len(ollama_queue))
        _update_state(status="classifying", total=len(ollama_queue), processed=0)

        # Phase 4: parallel Ollama classification
        ollama_workers = int(settings.get("ollama_workers", "4"))

        def _classify_and_save(item: tuple):
            r_id, mids, bods, cust_email = item
            worker_db = SessionLocal()
            try:
                w_settings = _load_settings(worker_db)

                parsed = _process_thread_with_ollama(r_id, mids, header_map, bods, w_settings)
                if parsed is None:
                    return 0, 0, None

                pren = _save_thread(worker_db, r_id, mids, header_map, bods, parsed, w_settings)
                if pren:
                    msg_count = len([m for m in mids if m in bods and not m.startswith("_no_mid_")])
                    logger.info("[FULL-L3] %s: %d msgs in new thread #%d", cust_email, msg_count, pren.id)
                    return 1, msg_count, None
                return 0, 0, None
            except Exception as ex:
                logger.error("[FULL-L3] %s: %s", cust_email, ex)
                try:
                    worker_db.rollback()
                except Exception:
                    pass
                return 0, 0, str(ex)
            finally:
                worker_db.close()

        with ThreadPoolExecutor(max_workers=ollama_workers) as pool:
            futures = {pool.submit(_classify_and_save, item): item for item in ollama_queue}
            done_count = 0
            for future in as_completed(futures):
                try:
                    threads_n, msgs_n, err = future.result()
                    processed_threads += threads_n
                    processed_msgs += msgs_n
                    if err:
                        errors.append(err)
                except Exception as ex:
                    errors.append(str(ex))
                done_count += 1
                _update_state(processed=done_count)

        _update_state(status="done")
        result = {
            "success": True,
            "message": (
                f"Import: {processed_threads} thread, {processed_msgs} messaggi "
                f"(Ollama: {ollama_used})"
            ),
            "processed": processed_threads,
            "errors": errors,
        }
        return result

    except imaplib.IMAP4.error as e:
        _update_state(status="error")
        return {"success": False, "message": f"Errore IMAP: {e}", "processed": 0}
    except Exception as e:
        logger.error("[FULL] Error: %s", e)
        _update_state(status="error")
        return {"success": False, "message": str(e), "processed": 0}
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass
        if own_session:
            db.close()


# ---------------------------------------------------------------------------
# Public API — reset_and_reimport
# ---------------------------------------------------------------------------
def reset_and_reimport(
    db=None,
    ollama_limit: int = 100,
    job_state: dict | None = None,
) -> dict:
    """Delete all Prenotazione + StoricoMessaggio, then call import_full_history."""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        logger.info("[RESET] Deleting all prenotazioni...")
        count = db.query(Prenotazione).count()
        db.query(StoricoMessaggio).delete()
        db.query(Prenotazione).delete()
        db.commit()
        logger.info("[RESET] Deleted %d prenotazioni. Starting reimport...", count)

        result = import_full_history(
            db=db, ollama_limit=ollama_limit, job_state=job_state
        )
        result["deleted"] = count
        result["message"] = f"Reset: {count} eliminati. {result.get('message', '')}"
        return result
    except Exception as e:
        logger.error("[RESET] Error: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(e), "processed": 0}
    finally:
        if own_session:
            db.close()
