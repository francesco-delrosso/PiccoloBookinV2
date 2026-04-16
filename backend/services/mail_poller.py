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
    # Generic auto-senders
    "noreply", "no-reply", "no.reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "automailer", "daemon", "system",
    "bounce", "bounced", "return", "root", "abuse", "webmaster",
    # Marketing/commercial
    "newsletter", "marketing", "promo", "promozioni", "offerte",
    "news", "info@newsletter", "comunicazioni", "commerciale",
    # Billing/finance
    "billing", "fatture", "invoice", "invoicing", "payment", "pagamenti",
    "receipt", "ricevuta", "order", "orders", "ordini",
    # Notifications
    "notifications", "notification", "notifiche", "alert", "alerts",
    "avviso", "avvisi", "update", "updates", "aggiornamenti",
    # Support/tickets/admin
    "support@nexi", "noreply@nexi", "helpdesk", "ticket", "feedback",
    "survey", "sondaggio", "customerservice",
    # Sales/services
    "sales", "vendite", "commerciale", "assistenza",
    "aggiornamentodati", "clienti", "nazionale",
    # Social media
    "facebookmail", "twittermail", "linkedin", "instagram",
    # Tech services
    "jira", "github", "gitlab", "bitbucket", "slack", "teams",
    "wordpress", "wix",
]

_SPAM_DOMAIN_KEYWORDS = [
    # Payment/finance
    "nexi.", "paypal.", "stripe.", "klarna.", "sumup.", "satispay.",
    # Email marketing
    "sendgrid.", "mailchimp.", "constantcontact.", "hubspot.", "salesforce.",
    "sendinblue.", "brevo.", "mailjet.", "getresponse.", "activecampaign.",
    "mailgun.", "sparkpost.", "mandrillapp.", "campaign-archive.",
    # Social
    "facebook.", "twitter.", "linkedin.", "instagram.", "tiktok.",
    "pinterest.", "youtube.",
    # Tech platforms
    # google.com removed — would match googlemail.com (European Gmail users)
    "amazonaws.com", "azure.", "cloudflare.",
    # E-commerce/services
    "shopify.", "amazon.", "ebay.", "aliexpress.",
    "booking.com", "airbnb.", "expedia.", "tripadvisor.",
    # Common spam sources for Italian businesses
    # aruba.it — NOT hardcoded because campsite uses Aruba for email
    # User can add it to filtro_domini_scarta if needed
    "register.it", "godaddy.", "ovh.", "siteground.",
    "iubenda.", "cookiebot.",
    # Bulk mailers
    "smtpout.", "bulk.", "mass.", "broadcast.",
    # Italian industry / portals / associations (not personal customers)
    "confcommercio", "faita.it", "mondocamping.", "camping.it",
    "dacos.it", "passportscan.",
    "maggengo.",  # local supplier
]

# Subject keywords that indicate spam (checked case-insensitive)
_SPAM_SUBJECT_KEYWORDS = [
    # Italian
    "fattura", "rinnovo", "scadenza", "pagamento", "ricevuta",
    "ordine", "spedizione", "consegna", "abbonamento",
    "preventivo", "offerta commerciale", "promozione",
    "newsletter", "comunicazione di servizio",
    # English
    "invoice", "renewal", "payment", "receipt", "subscription",
    "order confirmation", "shipping", "delivery", "unsubscribe",
    "promotional", "special offer", "limited time",
    # German
    "rechnung", "zahlung", "lieferung", "bestellung",
    # Commercial/vendor
    "lavatrici", "asciugatrici", "pannelli solari", "fotovoltaico",
    "noleggio", "fornitura", "preventivo", "listino",
    "agenzia", "marketing digitale", "seo", "social media",
    "sito web", "website", "e-commerce",
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
    # Outlook/Webmail style: "________________________________" separator
    re.compile(r"^_{10,}$"),
    # "----- Original Message -----" etc.
    re.compile(r"^-{3,}\s*(Original Message|Messaggio originale|Urspr.ngliche Nachricht)", re.IGNORECASE),
    # "Sent from my iPhone/iPad"
    re.compile(r"^Sent from (my |)?(iPhone|iPad|Samsung|Galaxy|Huawei)", re.IGNORECASE),
    # "Inviato da" (Italian mobile signature)
    re.compile(r"^Inviato da (iPhone|iPad|il mio)", re.IGNORECASE),
    # "Gesendet von" (German)
    re.compile(r"^Gesendet von (mein|meine)", re.IGNORECASE),
    # "Envoyé de" (French)
    re.compile(r"^Envoy.+ de(puis)? (mon |ma )", re.IGNORECASE),
]

# Signature patterns — if a line matches, everything from that line onward is signature
_SIGNATURE_PATTERNS = [
    # Standard signature separator
    re.compile(r"^--\s*$"),
    # Campsite signature (Piccolo Camping specific)
    re.compile(r"^Marinita\s+Alietti", re.IGNORECASE),
    re.compile(r"^PICCOLO\s+CAMPING", re.IGNORECASE),
    # Generic signature starts: "Tel.", "Tel:", "Tel/Fax", phone number lines
    re.compile(r"^Tel[\./:]", re.IGNORECASE),
    # "Cordiali saluti" / "Best regards" / "Mit freundlichen Grüßen" etc.
    re.compile(r"^(Cordiali saluti|Distinti saluti|Cordialmente)", re.IGNORECASE),
    re.compile(r"^(Best regards|Kind regards|Regards|Sincerely)", re.IGNORECASE),
    re.compile(r"^(Mit freundlichen Gr|Mit besten Gr|Viele Gr)", re.IGNORECASE),
    re.compile(r"^(Cordialement|Bien . vous)", re.IGNORECASE),
    re.compile(r"^(Met vriendelijke groet)", re.IGNORECASE),
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
    """Remove quoted text, signatures, and email headers from body."""
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
        # Check signature patterns — if matched, stop collecting
        if any(pat.match(stripped) for pat in _SIGNATURE_PATTERNS):
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

    # Built-in subject keywords
    subj_lower = subject.lower()
    for kw in _SPAM_SUBJECT_KEYWORDS:
        if kw in subj_lower:
            logger.info("L1 scartata (subject kw '%s'): %s", kw, subject)
            return True

    # User-configurable subject filter
    filtro_oggetti = settings.get("filtro_oggetto_scarta", "")
    for o in [x.strip().lower() for x in filtro_oggetti.split(",") if x.strip()]:
        if o in subj_lower:
            logger.info("L1 scartata (oggetto utente '%s'): %s", o, subject)
            return True

    return False


# ---------------------------------------------------------------------------
# Content filter (L1.5) — camping keyword check
# ---------------------------------------------------------------------------
_CAMPING_KEYWORDS = {
    # Accommodation types
    "camping", "campeggio", "campingplatz", "campingplace",
    "tent", "tenda", "zelt", "tente",
    "camper", "motorhome", "wohnmobil", "camping-car", "kastenwagen", "van",
    "caravan", "roulotte", "wohnwagen",
    "bungalow", "chalet", "mobilhome", "mobile home",
    "pitch", "piazzola", "stellplatz", "emplacement", "standplaats",
    # Stay/booking
    "holiday", "holidays", "vacation", "vacanza", "vacanze", "ferie",
    "urlaub", "ferien", "vacances", "vakantie",
    "booking", "book", "prenotazione", "prenotare", "prenota",
    "reservation", "reservierung", "réservation", "reservering",
    "disponibilità", "availability", "verfügbarkeit", "disponibilité",
    # Dates/stay
    "arrive", "arrivo", "ankunft", "arrivée", "aankomst",
    "depart", "partenza", "abreise", "départ", "vertrek",
    "check-in", "check-out", "notte", "notti", "night", "nights",
    "nacht", "nächte", "nuit", "nuits",
    # Location
    "lago", "lake", "see", "lac", "meer", "como",
    "piccolo camping",
    # People
    "adulti", "adults", "erwachsene", "adultes", "volwassenen",
    "bambini", "children", "kinder", "enfants", "kinderen",
    # Form emails
    "dati inseriti dal cliente", "richiesta dal sito", "form di contatti",
}


def _has_camping_content(subject: str, body: str) -> bool:
    """L1.5: check if email mentions any camping-related keywords.
    If not, it's almost certainly not a camping inquiry."""
    text = f"{subject} {body}".lower()
    return any(kw in text for kw in _CAMPING_KEYWORDS)


# ---------------------------------------------------------------------------
# Website form email parser (Level 0 — regex, no Ollama)
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


def _is_form_email(from_addr: str, settings: dict) -> bool:
    """Check if sender is the website contact form."""
    form_addr = settings.get("email_form_sito", "").lower()
    return bool(form_addr) and from_addr.lower() == form_addr


def _convert_form_date(date_str: str | None) -> str | None:
    """Convert DD-MM-YYYY or DD/MM/YYYY to YYYY-MM-DD."""
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def _map_posto_per(raw: str | None) -> str | None:
    """Map free-text accommodation to standard key."""
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
    """Parse structured body from website contact form.

    Returns dict with same keys as Ollama parse_email output,
    plus 'client_email' with the real customer email.
    Returns None if body doesn't look like a form submission.
    """
    if "dati inseriti dal cliente" not in body.lower():
        return None

    em = _FORM_EMAIL_RE.search(body)
    if not em:
        return None

    client_email = em.group(1).strip().lower().rstrip(".")

    # Extract name from body: "Name Surname - Email: ..."
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

    # Determine tipo from subject
    subj_low = subject.lower()
    is_prenotazione = "prenotazione" in subj_low or (arr is not None)
    tipo = "prenotazione" if is_prenotazione else "contatto"

    # Detect language from message text
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
        "tipo": tipo,
        "nome": nome,
        "cognome": cognome,
        "telefono": tel.group(1).strip() if tel else None,
        "data_arrivo": _convert_form_date(arr.group(1)) if arr else None,
        "data_partenza": _convert_form_date(dep.group(1)) if dep else None,
        "adulti": int(adu.group(1)) if adu else None,
        "bambini": bambini_val,
        "posto_per": _map_posto_per(posto.group(1)) if posto else None,
        "lingua": lingua,
        "confidenza": 1.0,
    }


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

    tipo = parsed.get("tipo", "")
    conf = parsed.get("confidenza", 0)

    # Discard spam
    if tipo == "spam" and conf >= 0.5:
        logger.info("Ollama spam: %s (%.2f)", hdr["from_addr"], conf)
        return None

    # If Ollama returned fallback (conf=0, no classification) — don't import blindly
    if conf == 0.0 and not parsed.get("nome") and not parsed.get("data_arrivo"):
        logger.info("Ollama inconclusive (fallback?), skipping: %s", hdr["from_addr"])
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
                # ── L0 — Website form fast-path ──
                # Emails from email_form_sito (contatti@...) contain structured
                # booking data. Parse with regex, extract real client email, skip Ollama.
                form_msg_id = None
                for mid in members:
                    hdr = header_map[mid]
                    if _is_form_email(hdr["from_addr"], settings):
                        form_msg_id = mid
                        break

                if form_msg_id and not _already_processed(db, form_msg_id):
                    form_hdr = header_map[form_msg_id]
                    form_body = _fetch_body(conn, form_hdr["uid"], form_hdr["folder"])
                    form_parsed = _parse_form_body(form_body, form_hdr["subject"])

                    if form_parsed:
                        client_email = form_parsed.pop("client_email")
                        logger.info("L0 form: %s → client %s", form_hdr["subject"], client_email)

                        # Check if client already has a prenotazione
                        existing = _known_client(db, client_email)
                        if existing:
                            # Append form message to existing thread
                            bodies = {form_msg_id: form_body}
                            _append_to_thread(db, existing, [form_msg_id], header_map, bodies, settings)
                            processed += 1
                            continue

                        # Create new prenotazione with REAL client email
                        pren = Prenotazione(
                            tipo_richiesta="Prenotazione" if form_parsed["tipo"] == "prenotazione" else "Contatto",
                            nome=form_parsed.get("nome"),
                            cognome=form_parsed.get("cognome"),
                            telefono=form_parsed.get("telefono"),
                            email=client_email,
                            data_arrivo=form_parsed.get("data_arrivo"),
                            data_partenza=form_parsed.get("data_partenza"),
                            adulti=form_parsed.get("adulti"),
                            bambini=form_parsed.get("bambini"),
                            posto_per=form_parsed.get("posto_per"),
                            stato="Nuova",
                            message_id=form_msg_id,
                            lingua_suggerita=form_parsed.get("lingua", "IT"),
                        )
                        db.add(pren)
                        db.flush()

                        # Add the form message
                        db.add(StoricoMessaggio(
                            id_prenotazione=pren.id,
                            mittente="Cliente",
                            testo=form_body,
                            message_id=form_msg_id if not form_msg_id.startswith("_no_mid_") else None,
                            data_ora=form_hdr["date"],
                        ))

                        # Also fetch+add any other thread messages (replies)
                        for mid in members:
                            if mid == form_msg_id or _already_processed(db, mid):
                                continue
                            try:
                                hdr = header_map[mid]
                                body = _fetch_body(conn, hdr["uid"], hdr["folder"])
                                mitt = _determine_mittente(hdr["from_addr"], settings)
                                db.add(StoricoMessaggio(
                                    id_prenotazione=pren.id,
                                    mittente=mitt,
                                    testo=body,
                                    message_id=mid if not mid.startswith("_no_mid_") else None,
                                    data_ora=hdr["date"],
                                ))
                            except Exception:
                                pass

                        db.commit()
                        processed += 1
                        logger.info("L0 form: new prenotazione #%d for %s", pren.id, client_email)
                        continue

                # ── Find first customer message ──
                first_cust_id = None
                for mid in members:
                    hdr = header_map[mid]
                    if _determine_mittente(hdr["from_addr"], settings) == "Cliente":
                        first_cust_id = mid
                        break
                if not first_cust_id:
                    # All messages are from campsite — check if form email that
                    # didn't match the regex parser (use Ollama as fallback)
                    for mid in members:
                        hdr = header_map[mid]
                        if _is_form_email(hdr["from_addr"], settings):
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

                # L1 — spam filter (skip for form emails)
                if not _is_form_email(customer_email, settings) and _discard(customer_email, subject, settings):
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

                # L1.5 — camping content check (before wasting Ollama call)
                first_body = bodies.get(first_cust_id, "")
                if not _has_camping_content(subject, first_body):
                    logger.info("L1.5 scartata (no camping keywords): %s — %s", customer_email, subject[:60])
                    continue

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
                # ── L0 — Website form fast-path ──
                form_msg_id = None
                for mid in members:
                    hdr = header_map[mid]
                    if _is_form_email(hdr["from_addr"], settings):
                        form_msg_id = mid
                        break

                if form_msg_id and not _already_processed(db, form_msg_id):
                    form_hdr = header_map[form_msg_id]
                    form_body = _fetch_body(conn, form_hdr["uid"], form_hdr["folder"])
                    form_parsed = _parse_form_body(form_body, form_hdr["subject"])

                    if form_parsed:
                        client_email = form_parsed.pop("client_email")
                        existing = _known_client(db, client_email)
                        if existing:
                            bodies = {form_msg_id: form_body}
                            _append_to_thread(db, existing, [form_msg_id], header_map, bodies, settings)
                        else:
                            pren = Prenotazione(
                                tipo_richiesta="Prenotazione" if form_parsed["tipo"] == "prenotazione" else "Contatto",
                                nome=form_parsed.get("nome"),
                                cognome=form_parsed.get("cognome"),
                                telefono=form_parsed.get("telefono"),
                                email=client_email,
                                data_arrivo=form_parsed.get("data_arrivo"),
                                data_partenza=form_parsed.get("data_partenza"),
                                adulti=form_parsed.get("adulti"),
                                bambini=form_parsed.get("bambini"),
                                posto_per=form_parsed.get("posto_per"),
                                stato="Nuova",
                                message_id=form_msg_id,
                                lingua_suggerita=form_parsed.get("lingua", "IT"),
                            )
                            db.add(pren)
                            db.flush()
                            db.add(StoricoMessaggio(
                                id_prenotazione=pren.id, mittente="Cliente",
                                testo=form_body, message_id=form_msg_id,
                                data_ora=form_hdr["date"],
                            ))
                            # Add other thread messages (replies)
                            for mid in members:
                                if mid == form_msg_id or _already_processed(db, mid):
                                    continue
                                try:
                                    h = header_map[mid]
                                    b = _fetch_body(conn, h["uid"], h["folder"])
                                    db.add(StoricoMessaggio(
                                        id_prenotazione=pren.id,
                                        mittente=_determine_mittente(h["from_addr"], settings),
                                        testo=b, message_id=mid, data_ora=h["date"],
                                    ))
                                except Exception:
                                    pass
                            db.commit()
                            processed_threads += 1
                            logger.info("[FULL-L0] form → #%d %s", pren.id, client_email)
                        _update_state(processed=job_state.get("processed", 0) + 1 if job_state else 0)
                        continue

                # ── Find first customer message ──
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
                    # L2 — append new messages to existing thread
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

                # L1.5 — camping content check (before wasting Ollama)
                first_body = bodies.get(first_cust_id, "")
                if not _has_camping_content(subject, first_body):
                    logger.info("[FULL-L1.5] no camping keywords: %s — %s", customer_email, subject[:60])
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
