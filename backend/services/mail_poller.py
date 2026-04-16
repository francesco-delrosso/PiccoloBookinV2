"""
Mail Poller Service — simplified approach.

Only imports:
  1. Form emails from contatti@piccolocamping.com (website form)
  2. Client replies to existing threads (by email match or In-Reply-To)

No Ollama classification. Conversations built from the app (Accetta/Rifiuta/Info).

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
from datetime import datetime, timezone
from html.parser import HTMLParser

import json

from database import SessionLocal
from models import Prenotazione, StoricoMessaggio, Impostazione, ModelloMail
from services.smart_parser import parse_email as ollama_parse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------
class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"[ \t]+", " ", "\n".join(self._parts)).strip()


def _strip_html(html_text: str) -> str:
    try:
        s = _HTMLStripper()
        s.feed(html_text)
        return s.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html_text).strip()


# ---------------------------------------------------------------------------
# Quote / signature stripping
# ---------------------------------------------------------------------------
_QUOTE_PATTERNS = [
    re.compile(r"^On .{5,150} wrote:\s*$", re.IGNORECASE),
    re.compile(r"^Il .{5,150} ha scritto:\s*$", re.IGNORECASE),
    re.compile(r"^Am .{5,150} schrieb\s?.*:\s*$", re.IGNORECASE),
    re.compile(r"^Le .{5,150} a .crit\s?.*:\s*$", re.IGNORECASE),
    re.compile(r"^Op .{5,150} schreef\s?.*:\s*$", re.IGNORECASE),
    re.compile(r"^El .{5,150} escribi.:\s*$", re.IGNORECASE),
    re.compile(r"^(Da|From|Von|De|Van)\s*:", re.IGNORECASE),
    re.compile(r"^_{10,}$"),
    re.compile(r"^-{3,}\s*(Original Message|Messaggio originale|Urspr.ngliche Nachricht)", re.IGNORECASE),
    re.compile(r"^Sent from (my )?(iPhone|iPad|Samsung|Galaxy|Huawei)", re.IGNORECASE),
    re.compile(r"^Inviato da (iPhone|iPad|il mio)", re.IGNORECASE),
    re.compile(r"^Gesendet von (mein|meine)", re.IGNORECASE),
    re.compile(r"^Envoy.+ de(puis)? (mon |ma )", re.IGNORECASE),
]

_SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$"),
    re.compile(r"^Marinita\s+Alietti", re.IGNORECASE),
    re.compile(r"^PICCOLO\s+CAMPING", re.IGNORECASE),
    re.compile(r"^Tel[\./:]", re.IGNORECASE),
    re.compile(r"^(Cordiali saluti|Distinti saluti|Cordialmente)", re.IGNORECASE),
    re.compile(r"^(Best regards|Kind regards|Regards|Sincerely)", re.IGNORECASE),
    re.compile(r"^(Mit freundlichen Gr|Mit besten Gr|Viele Gr)", re.IGNORECASE),
    re.compile(r"^(Cordialement|Bien . vous)", re.IGNORECASE),
    re.compile(r"^(Met vriendelijke groet)", re.IGNORECASE),
]


def _strip_quoted_text(text: str) -> str:
    lines = text.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if any(p.match(stripped) for p in _QUOTE_PATTERNS):
            break
        if any(p.match(stripped) for p in _SIGNATURE_PATTERNS):
            break
        clean.append(line)
    while clean and not clean[-1].strip():
        clean.pop()
    return "\n".join(clean)


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------
def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result).strip()


def _extract_email_addr(raw: str | None) -> str:
    if not raw:
        return ""
    decoded = _decode_header(raw)
    _, addr = email.utils.parseaddr(decoded)
    return addr.lower()


def _parse_date(raw: str | None) -> datetime:
    if raw:
        try:
            dt = email.utils.parsedate_to_datetime(raw)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_message_id(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().strip("<>").strip()
    return cleaned if cleaned else None


_SUBJECT_STRIP_RE = re.compile(
    r"^(re|fwd|fw|aw|ri|i|sv|vs|tr|wg)\s*(\[\d+\])?\s*:\s*",
    re.IGNORECASE,
)


def _normalize_subject(subject: str) -> str:
    s = subject.strip()
    prev = None
    while s != prev:
        prev = s
        s = _SUBJECT_STRIP_RE.sub("", s).strip()
    return s.lower()


# ---------------------------------------------------------------------------
# Website form parser
# ---------------------------------------------------------------------------
_FORM_EMAIL_RE = re.compile(r"Email:\s*(\S+@\S+)")
_FORM_TELEFONO_RE = re.compile(r"Telefono:\s*(\S+)")
_FORM_ARRIVO_RE = re.compile(r"Arrivo:\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})")
_FORM_PARTENZA_RE = re.compile(r"Partenza:\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{4})")
_FORM_POSTO_RE = re.compile(r"Posto per:\s*(.+)", re.IGNORECASE)
_FORM_ADULTI_RE = re.compile(r"Adulti:\s*(\d+)")
_FORM_BAMBINI_RE = re.compile(r"Bambini:\s*(\d+)")
_FORM_MESSAGGIO_RE = re.compile(r"Messaggio:\s*(.*)", re.DOTALL)
_FORM_NAME_LINE_RE = re.compile(
    r"dati inseriti dal cliente:\s*\n\s*(.+?)\s*-\s*Email:",
    re.IGNORECASE | re.DOTALL,
)


def _convert_form_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _map_posto_per(raw: str | None) -> str | None:
    if not raw:
        return None
    low = raw.lower()
    if "tenda" in low:
        return "tenda"
    if "camper" in low:
        return "camper"
    if any(k in low for k in ("caravan", "roulotte")):
        return "caravan"
    if "bungalow" in low:
        return "bungalow"
    return raw.strip()


def _parse_form_body(body: str, subject: str) -> dict | None:
    """Parse website form email. Returns dict with client_email + booking data, or None."""
    if "dati inseriti dal cliente" not in body.lower():
        return None

    em = _FORM_EMAIL_RE.search(body)
    if not em:
        return None

    client_email = em.group(1).strip().lower().rstrip(".")

    nome = None
    cognome = None
    nm = _FORM_NAME_LINE_RE.search(body)
    if nm:
        name_parts = nm.group(1).strip().split()
        if len(name_parts) >= 2:
            nome = name_parts[0]
            cognome = " ".join(name_parts[1:])
        elif name_parts:
            nome = name_parts[0]

    tel = _FORM_TELEFONO_RE.search(body)
    arr = _FORM_ARRIVO_RE.search(body)
    dep = _FORM_PARTENZA_RE.search(body)
    posto = _FORM_POSTO_RE.search(body)
    adu = _FORM_ADULTI_RE.search(body)
    bam = _FORM_BAMBINI_RE.search(body)
    msg = _FORM_MESSAGGIO_RE.search(body)

    subj_low = subject.lower()
    is_prenotazione = "prenotazione" in subj_low or (arr is not None)

    lingua = "IT"
    msg_text = msg.group(1).strip() if msg else ""
    if msg_text:
        for word, lang in [("dear", "EN"), ("please", "EN"), ("would like", "EN"),
                           ("lieber", "DE"), ("möchten", "DE"), ("gerne", "DE"),
                           ("cher", "FR"), ("nous", "FR"), ("voudrions", "FR"),
                           ("graag", "NL"), ("hebben", "NL"), ("zouden", "NL")]:
            if word in msg_text.lower():
                lingua = lang
                break

    bambini_val = None
    if bam:
        try:
            bambini_val = int(bam.group(1))
        except ValueError:
            pass

    return {
        "client_email": client_email,
        "tipo": "Prenotazione" if is_prenotazione else "Contatto",
        "nome": nome,
        "cognome": cognome,
        "telefono": tel.group(1).strip() if tel else None,
        "data_arrivo": _convert_form_date(arr.group(1)) if arr else None,
        "data_partenza": _convert_form_date(dep.group(1)) if dep else None,
        "adulti": int(adu.group(1)) if adu else None,
        "bambini": bambini_val,
        "posto_per": _map_posto_per(posto.group(1)) if posto else None,
        "lingua": lingua,
        "_messaggio": msg_text,  # raw message text for Ollama enrichment
    }


# ---------------------------------------------------------------------------
# IMAP operations
# ---------------------------------------------------------------------------
def _load_settings(db) -> dict:
    rows = db.query(Impostazione).all()
    return {r.chiave: r.valore for r in rows}


def _connect_imap(settings: dict) -> imaplib.IMAP4:
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
    return conn


def _find_sent_folder(conn: imaplib.IMAP4) -> str | None:
    try:
        _, folder_list = conn.list()
        for item in (folder_list or []):
            decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            m = re.search(r'"([^"]+)"\s*$', decoded) or re.search(r"(\S+)\s*$", decoded)
            if m:
                name = m.group(1).strip('"')
                if re.search(r"sent|invia|envoy|verzonden|gesendet|outbox", name, re.IGNORECASE):
                    for preferred in ("Sent", "INBOX.Sent", "Posta inviata"):
                        if preferred == name:
                            return preferred
                    return name
    except Exception:
        pass
    return None


_HEADER_FETCH_CMD = (
    "(BODY.PEEK[HEADER.FIELDS "
    "(FROM TO SUBJECT MESSAGE-ID DATE IN-REPLY-TO REFERENCES)])"
)


def _batch_fetch_headers(conn, folder, limit=0, batch_size=500):
    result = {}
    try:
        conn.select(folder, readonly=True)
        _, data = conn.search(None, "ALL")
        ids = data[0].split() if data[0] else []
        if limit and limit > 0:
            ids = ids[-limit:]

        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            try:
                _, hdr_data = conn.fetch(b",".join(batch), _HEADER_FETCH_CMD)
                j = 0
                for item in hdr_data:
                    if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                        uid = batch[j] if j < len(batch) else b"?"
                        j += 1
                        hdr = _parse_header_bytes(item[1], uid, folder)
                        if hdr:
                            key = hdr["message_id"] or f"_no_mid_{folder}_{uid}"
                            hdr["message_id"] = key
                            result[key] = hdr
            except Exception:
                pass
    except Exception as ex:
        logger.warning("Cannot read folder %r: %s", folder, ex)
    return result


def _parse_header_bytes(raw, uid, folder):
    try:
        msg = email.message_from_bytes(raw)
        return {
            "from_addr": _extract_email_addr(msg.get("From")),
            "to": _extract_email_addr(msg.get("To")),
            "date": _parse_date(msg.get("Date")),
            "subject": _decode_header(msg.get("Subject", "")),
            "message_id": _clean_message_id(msg.get("Message-ID")),
            "in_reply_to": _clean_message_id(msg.get("In-Reply-To")),
            "references": msg.get("References", "").strip(),
            "folder": folder,
            "uid": uid,
        }
    except Exception:
        return None


def _fetch_body(conn, uid, folder):
    conn.select(folder, readonly=True)
    _, raw_data = conn.fetch(uid, "(RFC822)")
    msg = email.message_from_bytes(raw_data[0][1])
    plain = html = None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if "attachment" in str(part.get("Content-Disposition", "")):
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
    return ""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _already_processed(db, message_id: str) -> bool:
    if not message_id or message_id.startswith("_no_mid_"):
        return False
    if db.query(Prenotazione).filter_by(message_id=message_id).first():
        return True
    if db.query(StoricoMessaggio).filter_by(message_id=message_id).first():
        return True
    return False


def _find_pren_by_message_id(db, message_id: str) -> Prenotazione | None:
    if not message_id:
        return None
    p = db.query(Prenotazione).filter_by(message_id=message_id).first()
    if p:
        return p
    m = db.query(StoricoMessaggio).filter_by(message_id=message_id).first()
    if m:
        return db.query(Prenotazione).filter_by(id=m.id_prenotazione).first()
    return None


def _known_client(db, email_addr: str) -> Prenotazione | None:
    return (
        db.query(Prenotazione)
        .filter(Prenotazione.email.ilike(email_addr))
        .order_by(Prenotazione.data_ricezione.desc())
        .first()
    )


def _campsite_addrs(settings: dict) -> set[str]:
    addrs = {
        settings.get("imap_user", "").lower(),
        settings.get("email_mittente", "").lower(),
        settings.get("smtp_user", "").lower(),
        settings.get("email_form_sito", "").lower(),
    }
    addrs.discard("")
    return addrs


def _enrich_with_ollama(db, pren: Prenotazione, message_text: str, settings: dict):
    """If prenotazione is missing key fields, use Ollama to extract them from the message.
    Only called for 'Contatto' type where regex couldn't extract structured data."""
    # Skip if we already have dates (structured form had them)
    if pren.data_arrivo and pren.data_partenza:
        return

    try:
        parsed = ollama_parse(pren.email or "", "", message_text, settings)
    except Exception as ex:
        logger.warning("Ollama enrich failed for #%d: %s", pren.id, ex)
        return

    if not parsed:
        return

    # Only fill fields that are currently empty
    updated = []
    if not pren.nome and parsed.get("nome"):
        pren.nome = parsed["nome"]
        updated.append("nome")
    if not pren.cognome and parsed.get("cognome"):
        pren.cognome = parsed["cognome"]
        updated.append("cognome")
    if not pren.telefono and parsed.get("telefono"):
        pren.telefono = parsed["telefono"]
        updated.append("telefono")
    if not pren.data_arrivo and parsed.get("data_arrivo"):
        pren.data_arrivo = parsed["data_arrivo"]
        updated.append("data_arrivo")
    if not pren.data_partenza and parsed.get("data_partenza"):
        pren.data_partenza = parsed["data_partenza"]
        updated.append("data_partenza")
    if not pren.adulti and parsed.get("adulti"):
        pren.adulti = parsed["adulti"]
        updated.append("adulti")
    if not pren.bambini and parsed.get("bambini"):
        pren.bambini = parsed["bambini"]
        updated.append("bambini")
    if not pren.posto_per and parsed.get("posto_per"):
        pren.posto_per = parsed["posto_per"]
        updated.append("posto_per")
    if not pren.lingua_suggerita and parsed.get("lingua"):
        pren.lingua_suggerita = parsed["lingua"]
        updated.append("lingua")

    # Upgrade to Prenotazione if Ollama found dates
    if pren.data_arrivo and pren.data_partenza and pren.tipo_richiesta == "Contatto":
        if parsed.get("tipo") == "prenotazione":
            pren.tipo_richiesta = "Prenotazione"
            updated.append("tipo→Prenotazione")

    if updated:
        db.commit()
        logger.info("Ollama enriched #%d: %s", pren.id, ", ".join(updated))


def _is_form_email(from_addr: str, settings: dict) -> bool:
    form = settings.get("email_form_sito", "").lower()
    return bool(form) and from_addr.lower() == form


# ---------------------------------------------------------------------------
# Auto-reject for closed dates
# ---------------------------------------------------------------------------
def _check_auto_reject(db, pren: Prenotazione, settings: dict) -> bool:
    """Check if prenotazione dates overlap with closed dates.
    If yes, auto-send rifiuta email and set stato=Rifiutata.
    Returns True if auto-rejected."""
    if not pren.data_arrivo or not pren.data_partenza:
        return False

    # Load closed dates
    row = db.query(Impostazione).filter_by(chiave="date_chiuse").first()
    if not row or not row.valore:
        return False

    try:
        closed_dates = set(json.loads(row.valore))
    except (json.JSONDecodeError, TypeError):
        return False

    if not closed_dates:
        return False

    # Check overlap: any night of the stay falls on a closed date?
    try:
        from datetime import date, timedelta
        arr = date.fromisoformat(pren.data_arrivo)
        dep = date.fromisoformat(pren.data_partenza)
        current = arr
        has_overlap = False
        while current < dep:
            if current.isoformat() in closed_dates:
                has_overlap = True
                break
            current += timedelta(days=1)

        if not has_overlap:
            return False
    except (ValueError, TypeError):
        return False

    # Auto-reject: find rifiuta template for the booking's language
    lingua = pren.lingua_suggerita or "IT"
    template = (
        db.query(ModelloMail)
        .filter_by(lingua=lingua, tipo="rifiuta")
        .first()
    )
    if not template:
        template = db.query(ModelloMail).filter_by(tipo="rifiuta").first()
    if not template:
        logger.warning("Auto-reject: no rifiuta template found for %s", pren.email)
        return False

    # Build email
    replacements = {
        "nome": pren.nome or "",
        "cognome": pren.cognome or "",
        "data_arrivo": pren.data_arrivo or "",
        "data_partenza": pren.data_partenza or "",
        "adulti": str(pren.adulti) if pren.adulti is not None else "",
        "bambini": str(pren.bambini) if pren.bambini is not None else "",
        "posto_per": pren.posto_per or "",
        "costo_totale": "",
        "caparra": "",
        "caparra_percentuale": settings.get("caparra_percentuale", "30"),
        "testo_aggiuntivo": "",
    }

    try:
        corpo = template.corpo
        soggetto = template.soggetto or ""
        for key, val in replacements.items():
            corpo = corpo.replace("{" + key + "}", val)
            soggetto = soggetto.replace("{" + key + "}", val)
    except Exception:
        return False

    # Send email
    try:
        from services.mail_sender import send_email

        # Find last message for In-Reply-To
        last_msg = (
            db.query(StoricoMessaggio)
            .filter_by(id_prenotazione=pren.id)
            .order_by(StoricoMessaggio.data_ora.desc())
            .first()
        )
        reply_to = last_msg.message_id if last_msg else None

        new_mid = send_email(
            to_addr=pren.email,
            subject=soggetto,
            body=corpo,
            settings=settings,
            reply_to_message_id=reply_to,
        )

        # Save sent message
        db.add(StoricoMessaggio(
            id_prenotazione=pren.id,
            mittente="Campeggio",
            testo=corpo,
            message_id=new_mid,
            data_ora=datetime.now(timezone.utc).replace(tzinfo=None),
        ))
        pren.stato = "Rifiutata"
        db.commit()

        logger.info("Auto-reject: %s (%s → %s) → sent rifiuta in %s",
                     pren.email, pren.data_arrivo, pren.data_partenza, lingua)
        return True

    except Exception as ex:
        logger.error("Auto-reject send failed for %s: %s", pren.email, ex)
        db.rollback()
        return False


# ---------------------------------------------------------------------------
# Public API — poll_emails
# ---------------------------------------------------------------------------
def poll_emails(db, limit: int = 20) -> dict:
    """Quick poll: fetch last N emails from INBOX.

    Only processes:
      1. Form emails from contatti@ → create Prenotazione
      2. Replies from known clients → append to thread
    """
    settings = _load_settings(db)
    if not all([settings.get("imap_server"), settings.get("imap_user"), settings.get("imap_password")]):
        return {"success": False, "message": "Credenziali IMAP non configurate", "processed": 0}

    conn = None
    processed = 0
    errors = []
    camping = _campsite_addrs(settings)

    try:
        conn = _connect_imap(settings)
        headers = _batch_fetch_headers(conn, "INBOX", limit=limit)
        logger.info("Poll: %d headers from INBOX", len(headers))

        for mid, hdr in headers.items():
            if _already_processed(db, mid):
                continue

            from_addr = hdr["from_addr"]
            subject = hdr["subject"]

            try:
                # 1. Form email from contatti@
                if _is_form_email(from_addr, settings):
                    body = _fetch_body(conn, hdr["uid"], hdr["folder"])
                    parsed = _parse_form_body(body, subject)
                    if not parsed:
                        continue

                    client_email = parsed.pop("client_email")

                    # Check if client already exists
                    existing = _known_client(db, client_email)
                    if existing:
                        if not _already_processed(db, mid):
                            db.add(StoricoMessaggio(
                                id_prenotazione=existing.id,
                                mittente="Cliente",
                                testo=body,
                                message_id=mid if not mid.startswith("_no_mid_") else None,
                                data_ora=hdr["date"],
                            ))
                            db.commit()
                            processed += 1
                        continue

                    # Create new Prenotazione
                    pren = Prenotazione(
                        tipo_richiesta=parsed["tipo"],
                        nome=parsed.get("nome"),
                        cognome=parsed.get("cognome"),
                        telefono=parsed.get("telefono"),
                        email=client_email,
                        data_arrivo=parsed.get("data_arrivo"),
                        data_partenza=parsed.get("data_partenza"),
                        adulti=parsed.get("adulti"),
                        bambini=parsed.get("bambini"),
                        posto_per=parsed.get("posto_per"),
                        stato="Nuova",
                        message_id=mid,
                        lingua_suggerita=parsed.get("lingua", "IT"),
                    )
                    db.add(pren)
                    db.flush()
                    db.add(StoricoMessaggio(
                        id_prenotazione=pren.id,
                        mittente="Cliente",
                        testo=body,
                        message_id=mid if not mid.startswith("_no_mid_") else None,
                        data_ora=hdr["date"],
                    ))
                    db.commit()
                    processed += 1
                    logger.info("Poll: new %s from %s (%s)", parsed["tipo"], client_email, subject[:50])

                    # Enrich with Ollama if Contatto (extract dates/info from free text)
                    msg_text = parsed.get("_messaggio") or body
                    _enrich_with_ollama(db, pren, msg_text, settings)

                    # Auto-reject if dates overlap with closed dates
                    _check_auto_reject(db, pren, settings)
                    continue

                # 2. Skip campsite's own emails
                if from_addr in camping:
                    continue

                # 3. Reply from known client → append to thread
                # Check In-Reply-To / References first
                pren = None
                if hdr["in_reply_to"]:
                    pren = _find_pren_by_message_id(db, hdr["in_reply_to"])
                if not pren and hdr["references"]:
                    for ref in hdr["references"].split():
                        ref_clean = _clean_message_id(ref)
                        if ref_clean:
                            pren = _find_pren_by_message_id(db, ref_clean)
                            if pren:
                                break
                # Fallback: check by email address
                if not pren:
                    pren = _known_client(db, from_addr)

                if pren:
                    body = _fetch_body(conn, hdr["uid"], hdr["folder"])
                    db.add(StoricoMessaggio(
                        id_prenotazione=pren.id,
                        mittente="Cliente",
                        testo=body,
                        message_id=mid if not mid.startswith("_no_mid_") else None,
                        data_ora=hdr["date"],
                    ))
                    # Auto-set status to "Nuova Risposta"
                    if pren.stato not in ("Nuova", "Nuova Risposta"):
                        pren.stato = "Nuova Risposta"
                    db.commit()
                    processed += 1
                    logger.info("Poll: reply from %s → prenotazione #%d", from_addr, pren.id)

                # 4. Unknown sender, not a form email → IGNORE

            except Exception as ex:
                logger.error("Poll error for %s: %s", mid, ex)
                errors.append(str(ex))
                try:
                    db.rollback()
                except Exception:
                    pass

    except Exception as ex:
        logger.error("Poll connection error: %s", ex)
        errors.append(str(ex))
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass

    return {"success": True, "processed": processed, "errors": errors}


# ---------------------------------------------------------------------------
# Public API — import_full_history
# ---------------------------------------------------------------------------
def import_full_history(
    db=None,
    mail_limit: int = 0,
    ollama_limit: int = 100,  # kept for API compat, unused now
    job_state: dict | None = None,
) -> dict:
    """Full import: scan INBOX + Sent. Only form emails + known client replies."""
    own_session = db is None
    if own_session:
        db = SessionLocal()

    def _update(**kw):
        if job_state:
            job_state.update(kw)

    conn = None
    processed = 0
    errors = []

    try:
        settings = _load_settings(db)
        if not all([settings.get("imap_server"), settings.get("imap_user"), settings.get("imap_password")]):
            _update(status="error")
            return {"success": False, "message": "Credenziali IMAP non configurate", "processed": 0}

        _update(status="scanning")
        camping = _campsite_addrs(settings)

        conn = _connect_imap(settings)

        # Fetch all headers
        inbox_headers = _batch_fetch_headers(conn, "INBOX", limit=mail_limit)
        logger.info("[FULL] INBOX: %d headers", len(inbox_headers))

        sent_folder = _find_sent_folder(conn)
        sent_headers = {}
        if sent_folder:
            sent_headers = _batch_fetch_headers(conn, sent_folder, limit=0)
            logger.info("[FULL] Sent: %d headers", len(sent_headers))

        all_headers = {**sent_headers, **inbox_headers}
        _update(total=len(all_headers), status="processing")

        # Pass 1: Process form emails → create Prenotazioni
        form_count = 0
        for mid, hdr in all_headers.items():
            if _already_processed(db, mid):
                _update(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                continue

            if not _is_form_email(hdr["from_addr"], settings):
                continue

            try:
                body = _fetch_body(conn, hdr["uid"], hdr["folder"])
                parsed = _parse_form_body(body, hdr["subject"])
                if not parsed:
                    continue

                client_email = parsed.pop("client_email")
                existing = _known_client(db, client_email)
                if existing:
                    db.add(StoricoMessaggio(
                        id_prenotazione=existing.id, mittente="Cliente",
                        testo=body, message_id=mid, data_ora=hdr["date"],
                    ))
                    db.commit()
                else:
                    pren = Prenotazione(
                        tipo_richiesta=parsed["tipo"],
                        nome=parsed.get("nome"), cognome=parsed.get("cognome"),
                        telefono=parsed.get("telefono"), email=client_email,
                        data_arrivo=parsed.get("data_arrivo"),
                        data_partenza=parsed.get("data_partenza"),
                        adulti=parsed.get("adulti"), bambini=parsed.get("bambini"),
                        posto_per=parsed.get("posto_per"), stato="Nuova",
                        message_id=mid, lingua_suggerita=parsed.get("lingua", "IT"),
                    )
                    db.add(pren)
                    db.flush()
                    db.add(StoricoMessaggio(
                        id_prenotazione=pren.id, mittente="Cliente",
                        testo=body, message_id=mid, data_ora=hdr["date"],
                    ))
                    db.commit()
                    _enrich_with_ollama(db, pren, body, settings)
                    _check_auto_reject(db, pren, settings)

                form_count += 1
                processed += 1
            except Exception as ex:
                db.rollback()
                errors.append(str(ex))

            _update(processed=job_state.get("processed", 0) + 1 if job_state else 0)

        logger.info("[FULL] Pass 1: %d form emails processed", form_count)

        # Pass 2: Process replies (both client and campsite) → append to threads
        reply_count = 0
        for mid, hdr in all_headers.items():
            if _already_processed(db, mid):
                _update(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                continue

            from_addr = hdr["from_addr"]
            if _is_form_email(from_addr, settings):
                continue  # already handled in pass 1

            try:
                # Find matching prenotazione
                pren = None

                # By In-Reply-To
                if hdr["in_reply_to"]:
                    pren = _find_pren_by_message_id(db, hdr["in_reply_to"])
                # By References
                if not pren and hdr["references"]:
                    for ref in hdr["references"].split():
                        ref_clean = _clean_message_id(ref)
                        if ref_clean:
                            pren = _find_pren_by_message_id(db, ref_clean)
                            if pren:
                                break
                # By sender email (client or campsite replying to client)
                if not pren and from_addr not in camping:
                    pren = _known_client(db, from_addr)
                # By recipient email (campsite sent TO client)
                if not pren and from_addr in camping:
                    to_addr = hdr.get("to", "")
                    if to_addr and to_addr not in camping:
                        pren = _known_client(db, to_addr)

                if not pren:
                    _update(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                    continue

                body = _fetch_body(conn, hdr["uid"], hdr["folder"])
                mittente = "Campeggio" if from_addr in camping else "Cliente"

                db.add(StoricoMessaggio(
                    id_prenotazione=pren.id,
                    mittente=mittente,
                    testo=body,
                    message_id=mid if not mid.startswith("_no_mid_") else None,
                    data_ora=hdr["date"],
                ))

                if mittente == "Cliente" and pren.stato not in ("Nuova", "Nuova Risposta"):
                    pren.stato = "Nuova Risposta"

                db.commit()
                reply_count += 1
                processed += 1

            except Exception as ex:
                db.rollback()
                errors.append(str(ex))

            _update(processed=job_state.get("processed", 0) + 1 if job_state else 0)

        logger.info("[FULL] Pass 2: %d replies linked", reply_count)
        _update(status="done")

    except Exception as ex:
        logger.error("[FULL] Fatal: %s", ex)
        errors.append(str(ex))
        _update(status="error")
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass
        if own_session:
            db.close()

    return {"success": True, "processed": processed, "errors": errors}


# ---------------------------------------------------------------------------
# Public API — reset_and_reimport
# ---------------------------------------------------------------------------
def reset_and_reimport(
    db=None,
    ollama_limit: int = 100,
    job_state: dict | None = None,
) -> dict:
    own_session = db is None
    if own_session:
        db = SessionLocal()

    try:
        db.query(StoricoMessaggio).delete()
        db.query(Prenotazione).delete()
        db.commit()
        logger.info("Reset: all data deleted")
    except Exception:
        db.rollback()

    result = import_full_history(db=db, mail_limit=0, job_state=job_state)

    if own_session:
        db.close()
    return result
