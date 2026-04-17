import email as email_lib
import imaplib
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)


def _fetch_real_message_id(settings: dict, subject: str) -> str | None:
    """After sending via SMTP, fetch the real Message-ID from Sent folder.
    Aruba SMTP rewrites Message-IDs, so we need the actual one."""
    try:
        server = settings.get("imap_server", "")
        port = int(settings.get("imap_port", "993"))
        user = settings.get("imap_user", "")
        password = settings.get("imap_password", "")

        conn = imaplib.IMAP4_SSL(server, port, timeout=15)
        conn.login(user, password)

        # Find Sent folder
        sent_folder = None
        _, folders = conn.list()
        for f in (folders or []):
            decoded = f.decode("utf-8", errors="replace") if isinstance(f, bytes) else str(f)
            if "sent" in decoded.lower() or "invia" in decoded.lower():
                import re
                m = re.search(r'"([^"]+)"\s*$', decoded) or re.search(r"(\S+)\s*$", decoded)
                if m:
                    name = m.group(1).strip('"')
                    if name in ("INBOX.Sent", "Sent"):
                        sent_folder = name
                        break
                    if not sent_folder:
                        sent_folder = name

        if not sent_folder:
            conn.logout()
            return None

        conn.select(sent_folder, readonly=True)
        _, data = conn.search(None, "ALL")
        uids = data[0].split() if data[0] else []
        if not uids:
            conn.logout()
            return None

        # Check last 3 messages
        for uid in reversed(uids[-3:]):
            _, hdata = conn.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT)])")
            if hdata and isinstance(hdata[0], tuple):
                msg = email_lib.message_from_bytes(hdata[0][1])
                msg_subj = msg.get("Subject", "")
                msg_mid = msg.get("Message-ID", "").strip().strip("<>")
                if subject and subject[:30] in str(msg_subj) and msg_mid:
                    conn.logout()
                    logger.info("Real Message-ID from Sent: %s", msg_mid)
                    return msg_mid

        conn.logout()
    except Exception as ex:
        logger.warning("Could not fetch real Message-ID from Sent: %s", ex)
    return None


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    settings: dict,
    reply_to_message_id: str | None = None,
) -> str:
    """Send an email via SMTP with TLS.

    *settings* must contain smtp_server, smtp_port, smtp_user, smtp_password,
    email_mittente.

    Returns the new Message-ID of the sent email.
    Raises on failure so callers can handle errors explicitly.
    """
    smtp_server = settings.get("smtp_server", "")
    smtp_port = int(settings.get("smtp_port", "587"))
    smtp_user = settings.get("smtp_user", "")
    smtp_password = settings.get("smtp_password", "")
    from_addr = settings.get("email_mittente", smtp_user)

    msg = MIMEMultipart("alternative")
    new_message_id = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")
    msg["Message-ID"] = new_message_id
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)

    # Threading headers
    if reply_to_message_id:
        msg["In-Reply-To"] = reply_to_message_id
        msg["References"] = reply_to_message_id

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Port 465 = SSL diretto (Aruba), port 587 = STARTTLS
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())

    logger.info("Mail inviata a %s — %s (local ID: %s)", to_addr, subject, new_message_id)

    # Wait briefly then fetch real Message-ID from Sent folder
    # (Aruba SMTP rewrites Message-IDs)
    time.sleep(2)
    real_mid = _fetch_real_message_id(settings, subject)
    if real_mid:
        return real_mid

    # Fallback to our generated ID (stripped of angle brackets)
    return new_message_id.strip("<>")


def test_smtp(settings: dict) -> dict:
    """Test SMTP connection. Returns {"ok": True} or {"ok": False, "error": "..."}."""
    try:
        smtp_server = settings.get("smtp_server", "")
        smtp_port = int(settings.get("smtp_port", "587"))
        smtp_user = settings.get("smtp_user", "")
        smtp_password = settings.get("smtp_password", "")

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_password)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_password)

        return {"ok": True}
    except Exception as e:
        logger.error("Test SMTP fallito: %s", e)
        return {"ok": False, "error": str(e)}


def test_imap(settings: dict) -> dict:
    """Test IMAP connection. Returns {"ok": True} or {"ok": False, "error": "..."}."""
    try:
        imap_server = settings.get("imap_server", "")
        imap_port = int(settings.get("imap_port", "993"))
        imap_user = settings.get("imap_user", "")
        imap_password = settings.get("imap_password", "")

        conn = imaplib.IMAP4_SSL(imap_server, imap_port)
        conn.login(imap_user, imap_password)
        conn.logout()

        return {"ok": True}
    except Exception as e:
        logger.error("Test IMAP fallito: %s", e)
        return {"ok": False, "error": str(e)}
